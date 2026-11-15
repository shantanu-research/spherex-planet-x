"""
SPHEREx Planet X Challenge - Master Backend Server & REST API
High-performance multithreaded HTTP server orchestrating Tracks 1, 2, 3, and 4.
Decoupled architecture delegating domain workflows to backend.pipeline.
Compliant with NASA Space Apps 2026 Master Technical Architecture & Execution Plan.
"""

import os
import sys
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Dict, Any, List

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.track1_orchestration.catalog import get_benchmark_list, get_target_by_query
from backend.track1_orchestration.resolver import resolve_target, SPHEREx_PIXEL_SCALE_ARCSEC
from backend.track1_orchestration.cache import cache_instance, CACHE_DIR
from backend.track2_calibration.band_balancer import DETECTOR_SPECS
from backend.track3_spectrophotometry.spectrum_extractor import extract_102_channel_spectrum
from backend.track3_spectrophotometry.astrometric_validator import query_live_gaia_overlay
from backend.simulation.synthetic_spherex import generate_simulated_target_visits
from backend.pipeline import execute_pipeline, generate_gif_export
from backend.data_loader import target_catalog

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
VALIDATION_SUMMARY_FILE = os.path.join(PROJECT_ROOT, "backend", "cache", "validation_summary.json")
GAIA_OVERLAY_MEMORY_CACHE: Dict[str, List[Dict[str, Any]]] = {}


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class SpherexApiHandler(SimpleHTTPRequestHandler):
    """
    HTTP Request Handler serving both the static Frontend single-page app
    and the clean REST API microservices for the SPHEREx Planet X discovery platform.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2 if status != 200 else None).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_binary(self, binary_data: bytes, content_type: str = "image/gif", filename: str = None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(binary_data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if filename:
            self.send_header("Content-Disposition", f'inline; filename="{filename}"')
        self.end_headers()
        self.wfile.write(binary_data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        try:
            self._handle_get()
        except ValueError as exc:
            self._send_json({"status": "error", "message": str(exc)}, status=400)

    def _handle_get(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # -------------------------------------------------------------
        # Endpoint 1: Health Check (Section 9.2)
        # -------------------------------------------------------------
        if path == "/api/health":
            health_data = {
                "status": "online",
                "archive_status": "not checked",
                "cache_metrics": {
                    "memory_entries": len(cache_instance._memory_cache),
                    "max_memory_entries": cache_instance._max_memory,
                    "disk_cache_dir": CACHE_DIR,
                    "status": "available"
                },
                "instrument_constants": {
                    "pixel_scale_arcsec": SPHEREx_PIXEL_SCALE_ARCSEC,
                    "detectors": list(DETECTOR_SPECS.keys()),
                    "channels_per_detector": 17,
                    "total_spectral_channels": 102,
                    "wavelength_range_um": [0.744, 5.002]
                }
            }
            self._send_json(health_data)
            return

        # -------------------------------------------------------------
        # Endpoint 2: List Verified Benchmark Targets (Section 9.2)
        # -------------------------------------------------------------
        if path == "/api/targets":
            benchmarks = get_benchmark_list()
            archive_targets = target_catalog.list_available_targets()
            for b in benchmarks:
                b["has_real_fits"] = target_catalog.has_real_data(b.get("common_name", "")) or target_catalog.has_real_data(b.get("name", ""))
            self._send_json({
                "status": "success",
                "targets": benchmarks,
                "archive_targets": archive_targets
            })
            return

        # -------------------------------------------------------------
        # Endpoint 3: Target Astrometric Resolver & Stale Epoch Guard
        # -------------------------------------------------------------
        if path == "/api/resolve":
            target_q = query.get("q", ["WISE 0855-0714"])[0]
            epoch = float(query.get("epoch", [2025.8])[0])
            resolved = resolve_target(target_q, target_epoch=epoch)
            self._send_json(resolved)
            return

        # -------------------------------------------------------------
        # Endpoint 4: Discovered Observations & Visits (Section 9.2)
        # -------------------------------------------------------------
        if path == "/api/observations":
            from backend.track1.archive import search
            from backend.track1.visits import group_visits, summarize
            try:
                target_q = query.get("q", ["WISE 0855-0714"])[0]
                fov = float(query.get("fov", [6.5])[0])
                if not 0 < fov <= 15:
                    raise ValueError("Field of view must be between 0 and 15 arcminutes")
                if "ra" in query and "dec" in query:
                    ra, dec = float(query["ra"][0]), float(query["dec"][0])
                else:
                    resolved = resolve_target(target_q)
                    position = resolved["epoch_propagation"]
                    ra, dec = position["ra_prop_deg"], position["dec_prop_deg"]
                exposures = group_visits(search(ra, dec, size_deg=fov / 60))
                visits = summarize(exposures)
                self._send_json({"status": "success", "source": "IRSA", "visits": visits,
                                 "n_visits_found": len(visits), "n_exposures": len(exposures)})
            except ValueError as exc:
                self._send_json({"status": "error", "message": str(exc)}, status=400)
            except Exception:
                self._send_json({"status": "unavailable", "message": "IRSA observation discovery failed."}, status=503)
            return

        # -------------------------------------------------------------
        # Endpoint 5: FrameStack Manifest & Rendered Frames (Section 9.1 & 9.2)
        # Endpoints /api/frames and /api/pipeline/run
        # -------------------------------------------------------------
        if path in ("/api/frames", "/api/pipeline/run"):
            target_key = query.get("q", query.get("target", ["WISE 0855-0714"]))[0]
            detector = query.get("det", query.get("detector", ["D6"]))[0].upper()
            mode = query.get("mode", ["visit_blink"])[0].lower()
            frame_mode = query.get("frame_mode", [None])[0]
            color_mode = query.get("color_mode", [None])[0]
            process_mode = query.get("process_mode", [None])[0]
            stretch = query.get("stretch", ["asinh"])[0].lower()
            fov = float(query.get("fov", [6.5])[0])
            source = query.get("source", ["auto"])[0].lower()
            fov_mode = query.get("fov_mode", [None])[0]
            blink_mode = query.get("blink_mode", [None])[0]

            result = execute_pipeline(
                target_key=target_key,
                detector=detector,
                mode=mode,
                frame_mode=frame_mode,
                color_mode=color_mode,
                process_mode=process_mode,
                stretch=stretch,
                fov_arcmin=fov,
                source_mode=source,
                fov_mode=fov_mode,
                blink_mode=blink_mode
            )
            self._send_json(result)
            return

        # -------------------------------------------------------------
        # Endpoint 6: 102-Channel Spectrophotometry Array (Section 9.2)
        # -------------------------------------------------------------
        if path == "/api/spectrum":
            target_q = query.get("q", query.get("target", ["WISE 0855-0714"]))[0]
            source_mode = query.get("source", ["auto"])[0].lower()
            target = get_target_by_query(target_q)
            spectrum_data = extract_102_channel_spectrum(target, source_mode=source_mode)
            self._send_json(spectrum_data)
            return

        # -------------------------------------------------------------
        # Endpoint 7: Catalog Overlays & Solar-System Vectors (Section 9.2)
        # -------------------------------------------------------------
        if path == "/api/overlay/catalogs":
            target_q = query.get("q", ["WISE 0855-0714"])[0]
            mjd = float(query.get("mjd", [60810.0])[0])
            fov = float(query.get("fov", [6.5])[0])

            # Propagate target coordinates to target MJD to center cone search
            target_epoch = 2000.0 + (mjd - 51544.5) / 365.25
            resolved = resolve_target(target_q, target_epoch=target_epoch)
            target = resolved["target"]
            prop = resolved["epoch_propagation"]
            center_ra = prop["ra_prop_deg"]
            center_dec = prop["dec_prop_deg"]

            # In-memory caching for live Gaia DR3 queries
            cache_key = f"{target['id']}_{round(mjd, 1)}_{round(fov, 2)}"
            gaia_stars = GAIA_OVERLAY_MEMORY_CACHE.get(cache_key)
            is_live_gaia = True

            if gaia_stars is None:
                try:
                    gaia_stars = query_live_gaia_overlay(
                        ra_deg=center_ra,
                        dec_deg=center_dec,
                        fov_arcmin=fov,
                        target_mjd=mjd,
                        grid_size=64,
                        pixscale_arcsec=SPHEREx_PIXEL_SCALE_ARCSEC
                    )
                    if gaia_stars:
                        GAIA_OVERLAY_MEMORY_CACHE[cache_key] = gaia_stars
                except Exception as ex:
                    print(f"[/api/overlay/catalogs] Live Gaia DR3 query failed: {ex}")
                    gaia_stars = []

            if not gaia_stars and query.get("source", ["real"])[0] in ("simulation", "simulated", "synthetic"):
                is_live_gaia = False
                sim_data = generate_simulated_target_visits(target_key=target["common_name"], detector="D6", grid_size=64)
                gaia_stars = []
                for s in sim_data["field_stars"]:
                    gaia_stars.append({
                        "source_id": f"Gaia DR3 {2026000000 + s['id']}",
                        "pixel_x": round(s["x"], 2),
                        "pixel_y": round(s["y"], 2),
                        "g_mag": round(14.5 + (s["id"] % 6) * 0.8, 2),
                        "teff_k": round(s["teff"], 0),
                        "ruwe": round(1.02 + (s["id"] % 5) * 0.05, 2),
                        "is_variable": False
                    })

            if not gaia_stars:
                is_live_gaia = False

            skybot_objects = []
            if "Planet X" in target["common_name"] and query.get("source", ["real"])[0] in ("simulation", "simulated", "synthetic"):
                skybot_objects.append({
                    "object_name": "Asteroid (2026 PX-Candidate)",
                    "pixel_x": 32.0,
                    "pixel_y": 32.0,
                    "motion_rate_arcsec_hr": 1.45,
                    "position_angle_deg": 242.0
                })

            payload = {
                "status": "success",
                "target": target["common_name"],
                "epoch_mjd": mjd,
                "center_ra_deg": center_ra,
                "center_dec_deg": center_dec,
                "source": "ESA Gaia DR3 (Live TAP + Proper Motion Propagated)" if is_live_gaia else ("Simulated Field Stars" if gaia_stars else "unavailable"),
                "is_live_gaia": is_live_gaia,
                "gaia_dr3": gaia_stars,
                "catwise": [],
                "skybot": skybot_objects
            }
            self._send_json(payload)
            return

        # -------------------------------------------------------------
        # Endpoint 8: Benchmark Scientific Validation Summary
        # -------------------------------------------------------------
        if path == "/api/validation":
            if os.path.exists(VALIDATION_SUMMARY_FILE):
                try:
                    with open(VALIDATION_SUMMARY_FILE, "r", encoding="utf-8") as f:
                        val_data = json.load(f)
                    self._send_json(val_data)
                    return
                except Exception as ex:
                    print(f"[/api/validation] Failed to read validation summary: {ex}")

            self._send_json({
                "status": "error",
                "message": "Validation summary not found on disk"
            }, status=404)
            return

        # -------------------------------------------------------------
        # Endpoint 9: Export Animated GIF & MP4 (Section 9.2)
        # -------------------------------------------------------------
        if path in ("/api/export/gif", "/api/export.gif", "/api/export/mp4", "/api/export.mp4"):
            target_key = query.get("q", query.get("target", ["WISE 0855-0714"]))[0]
            detector = query.get("det", query.get("detector", ["D6"]))[0].upper()
            mode = query.get("mode", ["visit_blink"])[0].lower()
            fps = max(1, min(15, int(query.get("fps", [4])[0])))
            source_mode = query.get("source", ["auto"])[0]
            fov_mode = query.get("fov_mode", query.get("fov", [None]))[0]
            blink_mode = query.get("blink_mode", query.get("blink", [None]))[0]

            gif_bytes = generate_gif_export(
                target_key,
                detector,
                mode,
                fps,
                source_mode=source_mode,
                fov_mode=fov_mode,
                blink_mode=blink_mode,
            )
            fov_suffix = f"_{fov_mode}" if fov_mode else ""
            filename = f"spherex_{target_key.replace(' ', '_').lower()}_{detector}_{mode}{fov_suffix}.gif"
            if path.endswith("mp4"):
                from backend.media import gif_to_mp4
                self._send_binary(gif_to_mp4(gif_bytes), "video/mp4", filename[:-4] + ".mp4")
            else:
                self._send_binary(gif_bytes, "image/gif", filename)
            return

        # Fallback to static file server (frontend HTML, CSS, JS)
        super().do_GET()

    # Backwards compatibility proxies
    @staticmethod
    def execute_pipeline_v2(*args, **kwargs) -> Dict[str, Any]:
        """Backwards compatibility proxy delegating to backend.pipeline.execute_pipeline."""
        return execute_pipeline(*args, **kwargs)

    @staticmethod
    def generate_gif_export_v2(*args, **kwargs) -> bytes:
        """Backwards compatibility proxy delegating to backend.pipeline.generate_gif_export."""
        return generate_gif_export(*args, **kwargs)


def run_server(port: int = 8080):
    server_address = ("", port)
    httpd = ThreadedHTTPServer(server_address, SpherexApiHandler)
    print("=================================================================")
    print(" SPHEREx 'Planet X' Discovery & Visualization Mission Control    ")
    print(" Architecture: Compliant with NASA Space Apps 2026 Master Plan   ")
    print(f" Running at: http://localhost:{port}/                          ")
    print("=================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8080"))
    run_server(port)
