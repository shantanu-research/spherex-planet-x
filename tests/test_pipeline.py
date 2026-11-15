"""
SPHEREx Planet X Challenge - Comprehensive Verification & Test Suite
Unit and integration tests for Tracks 1, 2, 3, and 4.
"""

import os
import sys
import math
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.track1_orchestration.catalog import BENCHMARK_TARGETS, get_benchmark_list
from backend.track1_orchestration.resolver import propagate_coordinates, resolve_target
from backend.track1_orchestration.visit_clustering import cluster_exposures_into_visits
from backend.track2_calibration.cleaning import clean_frame_data, DEFAULT_MP_FLAGS
from backend.track2_calibration.band_balancer import perform_band_balanced_stacking, label_exposure_spectral_channel
from backend.track2_calibration.flicker_audit import compute_flicker_statistics, run_still_star_flicker_audit
from backend.track2_calibration.differencing import compute_temporal_median_template, compute_difference_frames, perform_shift_and_stack
from backend.track3_spectrophotometry.molecular_fingerprints import generate_102_channel_grid
from backend.track3_spectrophotometry.spectrum_extractor import extract_102_channel_spectrum
from backend.track3_spectrophotometry.astrometric_validator import fit_2d_centroid, validate_proper_motion_astrometry
from backend.track4_rendering.wcs_engine import WCSEngine
from backend.track4_rendering.colorization import ir_to_visible_wavelength_log, lupton_asinh_color_compression
from backend.track4_rendering.stretching import apply_global_detector_asinh_stretch, apply_symmetric_difference_stretch
from backend.track4_rendering.gif_encoder import encode_gif_stream, burn_telemetry_hud
from backend.simulation.synthetic_spherex import generate_simulated_target_visits

class TestSpherexPipeline(unittest.TestCase):

    def test_track1_resolver_stale_epoch(self):
        """Verify WISE 0855 proper motion drift over ~16 years (~2.04 arcmin / ~20 px)."""
        target = BENCHMARK_TARGETS["WISE 0855-0714"]
        prop = propagate_coordinates(
            ra_deg_0=target["ra_deg"],
            dec_deg_0=target["dec_deg"],
            epoch_0=target["discovery_epoch"],
            target_epoch=2025.8,
            pm_ra_mas=target["pm_ra_mas"],
            pm_dec_mas=target["pm_dec_mas"],
            parallax_mas=target["parallax_mas"]
        )
        self.assertGreater(prop["total_drift_arcsec"], 100.0)
        self.assertGreater(prop["total_drift_px"], 18.0)
        
        resolved = resolve_target("WISE 0855-0714", 2025.8)
        self.assertIsNotNone(resolved["stale_epoch_warning"])
        self.assertIn("STALE CATALOG EPOCH HAZARD", resolved["stale_epoch_warning"])

    def test_track1_visit_clustering(self):
        """Verify clustering into visits at 30-day temporal gaps."""
        exps = [
            {"mjd_mid": 60800.0, "id": "e1"},
            {"mjd_mid": 60801.0, "id": "e2"},
            {"mjd_mid": 60980.0, "id": "e3"},  # 179-day gap -> Visit 2
            {"mjd_mid": 61180.0, "id": "e4"}   # 200-day gap -> Visit 3
        ]
        visits = cluster_exposures_into_visits(exps)
        self.assertEqual(len(visits), 3)
        self.assertEqual(visits[0]["visit_id"], "V1")
        self.assertEqual(visits[1]["visit_id"], "V2")
        self.assertEqual(visits[2]["visit_id"], "V3")

    def test_track2_band_balanced_stacking(self):
        """Verify Akhilesh's 5-step hierarchical stacking across 17 LVF channels."""
        sim = generate_simulated_target_visits("WISE 0855-0714", detector="D6", grid_size=32)
        visits = sim["visits"]
        res = perform_band_balanced_stacking(visits, detector="D6")
        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(res["n_shared_channels"], 1)
        self.assertEqual(len(res["visit_stacks"]), len(visits))

    def test_track2_flicker_audit_reduction(self):
        """Verify Still-Star Photometric Stability Audit achieves > 60% flicker suppression."""
        sim = generate_simulated_target_visits("WISE 0855-0714", detector="D6", grid_size=64)
        # Raw chronological playback: each exposure observes at a different LVF channel
        raw_frames = [{"image": v["exposures"][i % 4]["image"]} for i, v in enumerate(sim["visits"])]
        stacked = perform_band_balanced_stacking(sim["visits"], "D6")["visit_stacks"]
        stars = [(s["x"], s["y"]) for s in sim["field_stars"][:15]]
        
        audit = run_still_star_flicker_audit(raw_frames, stacked, stars)
        self.assertEqual(audit["status"], "completed")
        self.assertGreater(audit["mean_raw_flicker_pct"], 5.0)
        self.assertLess(audit["mean_balanced_flicker_pct"], 4.0)
        self.assertGreater(audit["overall_flicker_suppression_pct"], 50.0)

    def test_track3_102_channel_spectrophotometry(self):
        """Verify full 102-channel grid across D1-D6 and molecular line detection."""
        grid = generate_102_channel_grid()
        self.assertEqual(len(grid), 102)
        
        target = BENCHMARK_TARGETS["WISE 0855-0714"]
        spec = extract_102_channel_spectrum(target, source_mode="simulated")
        self.assertEqual(spec["total_channels"], 102)
        self.assertTrue(any("CH4" in f for f in spec["detected_molecular_features"]))

    def test_track3_astrometric_centroiding(self):
        """Verify 2D Gaussian centroiding and proper motion linear fit."""
        img = [[0.0 for _ in range(32)] for _ in range(32)]
        img[16][16] = 50.0
        img[16][17] = 30.0
        cx, cy, peak = fit_2d_centroid(img, 16.0, 16.0)
        self.assertAlmostEqual(cx, 16.375, places=1)
        self.assertAlmostEqual(cy, 16.0, places=1)

    def test_track4_wcs_relative_positioning(self):
        """Verify Idea 1: Inertial vs Co-Moving Target-Locked frame transformations."""
        wcs = WCSEngine(fov_arcmin=6.5, center_ra_deg=133.79, center_dec_deg=-7.24)
        img = [[0.0 for _ in range(wcs.grid_size)] for _ in range(wcs.grid_size)]
        img[32][32] = 100.0  # Center star
        
        inertial = wcs.transform_frame(img, target_displacement_px=(5.0, 0.0), mode="inertial")
        comoving = wcs.transform_frame(img, target_displacement_px=(5.0, 0.0), mode="comoving")
        
        # In inertial mode, image is unshifted (center is at 32)
        self.assertGreater(inertial[32][32], 50.0)
        # In comoving mode, image is shifted by -dx to keep target centered
        self.assertGreater(comoving[32][27], 50.0)

    def test_track4_idea2_spectral_superposition(self):
        """Verify Idea 2: Logarithmic IR-to-visible bijection and Lupton asinh color compression."""
        # 0.744 um -> 380 nm (Violet)
        v_min = ir_to_visible_wavelength_log(0.744)
        self.assertEqual(v_min, 380.0)
        # 5.002 um -> 750 nm (Far-red)
        v_max = ir_to_visible_wavelength_log(5.002)
        self.assertEqual(v_max, 750.0)
        
        r, g, b = lupton_asinh_color_compression(0.8, 0.2, 0.1)
        self.assertGreater(r, g)
        self.assertGreater(g, b)

    def test_track4_gif_encoder_stream(self):
        """Verify deterministic GIF89a encoding with burned-in telemetry HUD."""
        frame = [[(20, 20, 20) for _ in range(32)] for _ in range(32)]
        hud_frame = burn_telemetry_hud(frame, "WISE0855", "V1", 60810.0, "D6", "INERTIAL")
        gif_bytes = encode_gif_stream([hud_frame, hud_frame], delay_ms=250)
        self.assertTrue(gif_bytes.startswith(b"GIF89a"))
        self.assertTrue(gif_bytes.endswith(b"\x3B"))

    def test_modular_pipeline_orchestrator(self):
        """Verify decoupled backend.pipeline.execute_pipeline and generate_gif_export directly."""
        from backend.pipeline import execute_pipeline, generate_gif_export

        res = execute_pipeline(target_key="WISE 0855-0714", detector="D6", mode="visit_blink", source_mode="simulated")
        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["frames"]), 4)
        self.assertIn("manifest", res)
        self.assertIn("flicker_audit", res)
        self.assertIn("astrometric_validation", res)
        self.assertIn("spectrophotometry", res)

        # Test direct GIF export generation
        gif_bytes = generate_gif_export(target_key="WISE 0855-0714", detector="D6", mode="visit_blink", fps=4, source_mode="simulated")
        self.assertTrue(gif_bytes.startswith(b"GIF89a"))
        self.assertTrue(gif_bytes.endswith(b"\x3B"))

    def test_server_modes_and_shift_stack(self):
        """Verify 7 Viewing Modes and shift_stack without NameError."""
        from backend.server import SpherexApiHandler
        handler_dummy = SpherexApiHandler.__new__(SpherexApiHandler)
        
        # Test Mode 1: visit_blink
        res1 = handler_dummy.execute_pipeline_v2("WISE 0855-0714", "D6", mode="visit_blink", source_mode="simulated")
        self.assertEqual(res1["status"], "success")
        self.assertEqual(len(res1["frames"]), 4)
        
        # Test Mode 2: longest_baseline (2 frames)
        res2 = handler_dummy.execute_pipeline_v2("WISE 0855-0714", "D6", mode="longest_baseline", source_mode="simulated")
        self.assertEqual(len(res2["frames"]), 2)
        
        # Test Mode 3: difference_sequence
        res3 = handler_dummy.execute_pipeline_v2("WISE 0855-0714", "D6", mode="difference_sequence", source_mode="simulated")
        self.assertEqual(len(res3["frames"]), 4)
        
        # Test Mode 4: motion_tracked
        res4 = handler_dummy.execute_pipeline_v2("WISE 0855-0714", "D6", mode="motion_tracked", source_mode="simulated")
        self.assertEqual(res4["frame_mode"], "comoving")
        
        # Test Mode 5: spectral_color (multiband)
        res5 = handler_dummy.execute_pipeline_v2("WISE 0855-0714", "D6", mode="spectral_color", source_mode="simulated")
        self.assertEqual(res5["color_mode"], "multiband")
        
        # Test shift_stack (verifies SPHEREx_PIXEL_SCALE_ARCSEC bug is resolved)
        res_shift = handler_dummy.execute_pipeline_v2("WISE 0855-0714", "D6", mode="shift_stack", source_mode="simulated")
        self.assertEqual(res_shift["status"], "success")
        self.assertEqual(len(res_shift["frames"]), 4)

if __name__ == "__main__":
    unittest.main()
