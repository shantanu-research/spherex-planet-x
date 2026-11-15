"""
SPHEREx Planet X Challenge - Master Backend Server & REST API
High-performance multithreaded HTTP server orchestrating the integrated pipeline.
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

from backend.orchestration.catalog import get_benchmark_list, get_target_by_query
from backend.orchestration.resolver import resolve_target, SPHEREx_PIXEL_SCALE_ARCSEC
from backend.orchestration.cache import cache_instance, CACHE_DIR
from backend.calibration.band_balancer import DETECTOR_SPECS
from backend.spectrophotometry.spectrum_extractor import extract_102_channel_spectrum
from backend.spectrophotometry.astrometric_validator import query_live_gaia_overlay
from backend.simulation.synthetic_spherex import generate_simulated_target_visits
from backend.pipeline import execute_pipeline, generate_gif_export
from backend.data_loader import target_catalog
from backend.targets import resolve as resolve_metadata
from backend.real_pipeline import load as load_real, local_paths, spectrum as real_spectrum

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
VALIDATION_SUMMARY_FILE = os.path.join(PROJECT_ROOT, "docs", "validation.json")
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
        body = json.dumps(data, allow_nan=False, indent=2 if status != 200 else None).encode("utf-8")
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
        except Exception as exc:
            import traceback
            traceback.print_exc()
            sys.stderr.flush()
            name = type(exc).__name__
            if name in ("HTTPStatusError", "ConnectError", "ConnectTimeout", "ReadTimeout", "RemoteProtocolError", "TimeoutException"):
                detail = getattr(getattr(exc, "response", None), "status_code", None)
                message = ("The NASA/IPAC archive (IRSA) did not respond" + (f" (HTTP {detail})" if detail else "")
                           + ". Live archive searches depend on that service; try again shortly, or choose a test-target preset, which uses installed observations.")
            else:
                message = f"Processing failed ({name}). Please retry or select another target."
            self._send_json({"status": "unavailable", "message": message}, status=503)

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
                b["has_real_fits"] = bool(local_paths(resolve_metadata(b["name"])))
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
            from backend.science import position
            from astropy.time import Time
            target = resolve_metadata(target_q)
            ra, dec = position(target, Time(epoch,format='jyear').mjd)
            resolved = {'target':target,'epoch':epoch,'ra_deg':ra,'dec_deg':dec,'note':'Catalogue linear proper motion; no annual parallax correction.'}
            self._send_json(resolved)
            return

        # -------------------------------------------------------------
        # Endpoint 4: Discovered Observations & Visits (Section 9.2)
        # -------------------------------------------------------------
        if path == "/api/observations":
            target_q = query.get("q", ["Barnard's Star"])[0]
            if "ra" in query and "dec" in query:
                target_q = query["ra"][0] + "," + query["dec"][0]
            target = resolve_metadata(target_q)
            exposures, _, _, errors, provenance = load_real(target, query.get("det",["D6"])[0], float(query.get("fov",[6.5])[0]))
            observations=[]
            for v in sorted({e.visit for e in exposures}):
                members=[e for e in exposures if e.visit==v]
                from astropy.time import Time
                observations.append({"visit":v,"n_exposures":len(members),
                                     "first":Time(min(e.mjd for e in members),format="mjd").isot,
                                     "mjd_mid":sum(e.mjd for e in members)/len(members),
                                     "detectors":sorted({e.detector for e in members})})
            self._send_json({"status":"success","visits":observations,"n_visits_found":len(observations),
                             "source":provenance,"errors":errors})
            return

        # -------------------------------------------------------------
        # Endpoint 5: FrameStack Manifest & Rendered Frames (Section 9.1 & 9.2)
        # Endpoints /api/frames and /api/pipeline/run
        # -------------------------------------------------------------
        if path in ("/api/frames", "/api/pipeline/run"):
            target_key = query.get("q", query.get("target", ["WISE 0855-0714"]))[0]
            if "ra" in query and "dec" in query:
                target_key = query["ra"][0] + "," + query["dec"][0]
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
            target = resolve_metadata(target_q)
            if source_mode in ("auto", "real"):
                spectrum_data = real_spectrum(load_real(target, "D6", float(query.get("fov", [6.5])[0]))[0])
            else:
                spectrum_data = extract_102_channel_spectrum(target, source_mode=source_mode)
            self._send_json(spectrum_data)
            return

        # -------------------------------------------------------------
        # Endpoint 7: Catalog Overlays & Solar-System Vectors (Section 9.2)
        # -------------------------------------------------------------
        if path == "/api/overlay/catalogs":
            from backend.catalog_overlays import overlays
            target = resolve_metadata(query.get("q", ["WISE 0855-0714"])[0])
            self._send_json(overlays(target, float(query.get("mjd", [61000])[0]), float(query.get("fov", [6.5])[0])))
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
            if "ra" in query and "dec" in query:
                target_key = query["ra"][0] + "," + query["dec"][0]
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
                fov_arcmin=float(query.get("fov", [6.5])[0]),
                frame_mode=query.get("frame_mode", [None])[0],
                color_mode=query.get("color_mode", [None])[0],
                stretch=query.get("stretch", ["asinh"])[0],
            )
            fov_suffix = f"_{fov_mode}" if fov_mode else ""
            filename = f"spherex_{detector}_{mode}.gif"
            if path.endswith("mp4"):
                from backend.media import gif_to_mp4
                self._send_binary(gif_to_mp4(gif_bytes), "video/mp4", filename[:-4] + ".mp4")
            else:
                self._send_binary(gif_bytes, "image/gif", filename)
            return

        # Byte ranges for video, so browsers (Safari in particular) can play and seek the demo
        rng = self.headers.get("Range", "")
        if path.endswith(".mp4") and rng.startswith("bytes="):
            fp = self.translate_path(path)
            if os.path.isfile(fp):
                size = os.path.getsize(fp)
                a, _, b = rng[6:].split(",")[0].partition("-")
                start = int(a) if a else max(0, size - int(b or 0))
                end = min(size - 1, int(b)) if (a and b) else size - 1
                if start >= size or start > end:
                    self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.end_headers()
                    return
                with open(fp, "rb") as f:
                    f.seek(start); body = f.read(end - start + 1)
                self.send_response(206)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
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
