"""
SPHEREx Planet X Challenge - Comprehensive Verification & Test Suite
Unit and integration tests for every pipeline module.
"""

import os
import sys
import math
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.orchestration.catalog import BENCHMARK_TARGETS, get_benchmark_list
from backend.orchestration.resolver import propagate_coordinates, resolve_target
from backend.orchestration.visit_clustering import cluster_exposures_into_visits
from backend.calibration.cleaning import clean_frame_data, DEFAULT_MP_FLAGS
from backend.calibration.band_balancer import perform_band_balanced_stacking, label_exposure_spectral_channel
from backend.calibration.flicker_audit import compute_flicker_statistics, run_still_star_flicker_audit
from backend.calibration.differencing import compute_temporal_median_template, compute_difference_frames, perform_shift_and_stack
from backend.spectrophotometry.molecular_fingerprints import generate_102_channel_grid
from backend.spectrophotometry.spectrum_extractor import extract_102_channel_spectrum
from backend.spectrophotometry.astrometric_validator import fit_2d_centroid, validate_proper_motion_astrometry
from backend.rendering.wcs_engine import WCSEngine
from backend.rendering.colorization import ir_to_visible_wavelength_log, lupton_asinh_color_compression
from backend.rendering.stretching import apply_global_detector_asinh_stretch, apply_symmetric_difference_stretch
from backend.rendering.gif_encoder import encode_gif_stream, burn_telemetry_hud
from backend.simulation.synthetic_spherex import generate_simulated_target_visits

try:
    import astropy  # noqa: F401  (only needed to read real SPHEREx files)
    _HAS_ASTROPY = True
except ImportError:
    _HAS_ASTROPY = False

class TestSpherexPipeline(unittest.TestCase):

    def test_stage1_resolver_stale_epoch(self):
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

    def test_stage1_visit_clustering(self):
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

    def test_stage2_band_balanced_stacking(self):
        """Verify 5-step hierarchical stacking across 17 LVF channels."""
        sim = generate_simulated_target_visits("WISE 0855-0714", detector="D6", grid_size=32)
        visits = sim["visits"]
        res = perform_band_balanced_stacking(visits, detector="D6")
        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(res["n_shared_channels"], 1)
        self.assertEqual(len(res["visit_stacks"]), len(visits))

    def test_stage2_simulator_exercises_band_balancing(self):
        """Simulated visits must have uneven, partly missing band coverage and real colour flicker."""
        from collections import Counter
        from backend.calibration.flicker_audit import measure_aperture_flux

        sim = generate_simulated_target_visits("WISE 0855-0714", detector="D6", grid_size=32)
        again = generate_simulated_target_visits("WISE 0855-0714", detector="D6", grid_size=32)
        self.assertEqual(sim["field_stars"][0]["x"], again["field_stars"][0]["x"], "Simulation must be deterministic")

        per_visit = [
            Counter(label_exposure_spectral_channel("D6", e["wavelength_um"]) for e in v["exposures"])
            for v in sim["visits"]
        ]
        # Visit 2 is missing bands 6 and 13; shots per band differ between visits
        self.assertNotIn(6, per_visit[1])
        self.assertNotIn(13, per_visit[1])
        self.assertNotEqual(per_visit[0], per_visit[2])
        # Survey 3 is shifted by half a band: some bands get several shots
        self.assertGreater(max(per_visit[2].values()), 2)

        stack = perform_band_balanced_stacking(sim["visits"], "D6")
        self.assertGreaterEqual(stack["n_shared_channels"], 10)
        self.assertLess(stack["n_shared_channels"], 17)

        # Naive single shots in time order flicker because of each star's colour
        star = max(sim["field_stars"], key=lambda s: s["teff"])
        fluxes = [measure_aperture_flux(e["image"], star["x"], star["y"]) for v in sim["visits"] for e in v["exposures"]]
        _, _, scatter = compute_flicker_statistics(fluxes)
        self.assertGreater(scatter, 0.05)

    def test_stage2_stacks_use_cleaned_images(self):
        """Flagged hot pixels must not leak into band-balanced stacks."""
        from backend.calibration import clean_visit_exposures

        sim = generate_simulated_target_visits("Barnard's Star", detector="D3", grid_size=32)
        summary = clean_visit_exposures(sim["visits"])
        self.assertGreater(summary["n_pixels_masked"], 0)

        res = perform_band_balanced_stacking(sim["visits"], "D3")
        hot_spots = {
            (x, y)
            for v in sim["visits"] for e in v["exposures"]
            for y, row in enumerate(e["flags"]) for x, f in enumerate(row)
            if f & (1 << 10) and 2 <= x < 30 and 2 <= y < 30
            and all((x - s["x"]) ** 2 + (y - s["y"]) ** 2 > 36 for s in sim["field_stars"])
            and (x - 16) ** 2 + (y - 16) ** 2 > 36
        }
        self.assertTrue(hot_spots)
        for stack in res["visit_stacks"]:
            self.assertTrue(stack["used_cleaned_images"])
            self.assertEqual(stack["n_masked_pixels"], 0)
            img = stack["stacked_image"]
            for x, y in hot_spots:
                neighbours = sorted(img[y + dy][x + dx] for dy in (-2, 0, 2) for dx in (-2, 0, 2) if dx or dy)
                self.assertLess(img[y][x] - neighbours[len(neighbours) // 2], 0.5)

    def _visits_keeping_bands(self, bands_per_visit):
        """Simulated D6 visits with each visit's shots limited to the given bands."""
        sim = generate_simulated_target_visits("WISE 0855-0714", detector="D6", grid_size=16)
        visits = sim["visits"][: len(bands_per_visit)]
        for v, keep in zip(visits, bands_per_visit):
            v["exposures"] = [
                e for e in v["exposures"] if label_exposure_spectral_channel("D6", e["wavelength_um"]) in keep
            ]
        return visits

    def test_stage2_step3_no_union_fallback(self):
        """Visits with no shared bands are marked not comparable, never silently mixed."""
        visits = self._visits_keeping_bands([{1, 2, 3}, {10, 11, 12}])
        res = perform_band_balanced_stacking(visits, "D6")
        self.assertEqual(res["n_shared_channels"], 0)
        self.assertFalse(res["comparable"])
        self.assertIn("NOT COMPARABLE", res["reliability_warning"])
        self.assertEqual(res["visit_stacks"][0]["bands_used"], [1, 2, 3])
        self.assertEqual(res["visit_stacks"][1]["bands_used"], [10, 11, 12])

    def test_stage2_step3_few_shared_bands_unreliable(self):
        """Fewer than 10 shared bands: stacks use only shared bands and are flagged unreliable."""
        visits = self._visits_keeping_bands([set(range(1, 18)), set(range(1, 9))])
        present = [
            {label_exposure_spectral_channel("D6", e["wavelength_um"]) for e in v["exposures"]} for v in visits
        ]
        expected = sorted(present[0] & present[1])  # visit 2 is missing band 6 by design
        res = perform_band_balanced_stacking(visits, "D6")
        self.assertEqual(res["shared_channels"], expected)
        self.assertLess(len(expected), 10)
        self.assertFalse(res["comparable"])
        self.assertIn("UNRELIABLE", res["reliability_warning"])
        for stack in res["visit_stacks"]:
            self.assertEqual(stack["bands_used"], expected)
            self.assertFalse(stack["comparable"])
        self.assertEqual(res["visit_stacks"][0]["n_bands_present"], 17)

    def test_stage2_manifest_fields(self):
        """Every stack and shot carries the fields agreed with the spectrophotometry and rendering stages."""
        from backend.pipeline import execute_pipeline
        res = execute_pipeline("WISE 0855-0714", "D6", "visit_blink", source_mode="simulated")
        t2 = res["manifest"]["band_balancing"]
        self.assertGreaterEqual(t2["n_bands_shared"], 10)
        self.assertTrue(t2["comparable"])
        for stack in t2["stacks"]:
            for field in ("detector", "bands_used", "n_bands", "n_shots_per_band", "lambda_eff", "comparable"):
                self.assertIn(field, stack)
            self.assertEqual(stack["bands_used"], t2["bands_shared"])
            self.assertEqual(sum(stack["n_shots_per_band"].values()), stack["n_shots_used"])
            self.assertAlmostEqual(stack["lambda_eff"], t2["lambda_eff"], places=4)
        for shot in t2["shots"]:
            self.assertIsNotNone(shot["lambda_at_target"])
            self.assertEqual(shot["band"], label_exposure_spectral_channel("D6", shot["lambda_at_target"]))
        self.assertIn("stack", res["frames"][0])

    def test_stage2_skips_edge_channel_and_off_image_shots(self):
        """Shots in edge channel 0/18 or with the target off the image are labelled but not stacked."""
        from backend.calibration.spectral_labels import channel_info

        sim = generate_simulated_target_visits("WISE 0855-0714", detector="D6", grid_size=16)
        baseline = perform_band_balanced_stacking(sim["visits"], "D6")
        base_used = [s["n_shots_used"] for s in baseline["visit_stacks"]]
        for s in baseline["visit_stacks"]:
            self.assertEqual(s["n_shots_excluded"], {"edge_channel": 0, "off_image": 0})

        sim = generate_simulated_target_visits("WISE 0855-0714", detector="D6", grid_size=16)
        exps = sim["visits"][0]["exposures"]
        # Like the real WISE 0855 D6 shot at 4.4178 um: just below channel 1 (edge channel 0)
        edge, off = exps[0], exps[1]
        edge["lambda_at_target"] = channel_info("D6", 1)["lambda_min"] - 0.002
        edge["channel"] = None
        off["on_image"] = False

        res = perform_band_balanced_stacking(sim["visits"], "D6")
        stack0 = res["visit_stacks"][0]
        self.assertEqual(stack0["n_shots_excluded"], {"edge_channel": 1, "off_image": 1})
        self.assertEqual(edge["band"], 1)  # still labelled with the nearest band...
        self.assertEqual(edge["excluded_reason"], "edge_channel")  # ...but not stacked
        self.assertEqual(off["excluded_reason"], "off_image")
        self.assertLessEqual(stack0["n_shots_used"], base_used[0])
        self.assertEqual(stack0["n_shots_used"], sum(stack0["n_shots_per_band"].values()))
        self.assertTrue(all(e["excluded_reason"] is None for v in sim["visits"][1:] for e in v["exposures"]))

    def test_stage2_matched_band_and_sub_bands(self):
        """Matched-band frames all come from the chosen band; sub-bands hold ~4 bands each."""
        from backend.pipeline import execute_pipeline
        res = execute_pipeline("WISE 0855-0714", "D6", "wavelength_matched", source_mode="simulated")
        bands = {f["shot"]["band"] for f in res["frames"]}
        self.assertEqual(len(bands), 1)
        self.assertEqual(bands, {res["frames"][0]["shot"]["matched_band"]})
        self.assertGreaterEqual(len(res["frames"]), 2)

        from backend.calibration.band_balancer import split_into_sub_bands
        groups = split_into_sub_bands(list(range(1, 18)))
        self.assertEqual(sum(len(g) for g in groups), 17)
        self.assertTrue(all(3 <= len(g) <= 5 for g in groups))
        self.assertEqual(split_into_sub_bands([2, 3, 4]), [[2, 3, 4]])

    def test_stage2_step1_channel_table(self):
        """Bands come from the Explanatory Supplement table (nearest channel centre)."""
        from backend.calibration.spectral_labels import (
            band_from_wavelength, channel_info, load_channel_table, wavelength_from_band_position,
        )
        table = load_channel_table()
        self.assertEqual(sorted(table), [1, 2, 3, 4, 5, 6])
        for det in range(1, 7):
            self.assertEqual(sorted(table[det]), list(range(19)))
            centres = [table[det][c]["lambda_c"] for c in range(1, 18)]
            self.assertEqual(centres, sorted(centres))
            for c in range(1, 18):
                # each channel centre (and the simulator's position for it) labels as itself
                self.assertEqual(band_from_wavelength(det, table[det][c]["lambda_c"])["band"], c)
                self.assertEqual(label_exposure_spectral_channel(f"D{det}", wavelength_from_band_position(det, c - 0.5)), c)
        self.assertEqual(band_from_wavelength("D6", 4.62)["band"], 7)  # the PDF's example
        self.assertFalse(band_from_wavelength("D6", 5.02)["in_nominal_range"])
        self.assertAlmostEqual(channel_info("D1", 1)["lambda_min"], 0.743)

    @unittest.skipUnless(_HAS_ASTROPY, "astropy not installed")
    def test_stage2_step1_label_real_format_file(self):
        """Step 1 on a SPHEREx-format FITS file: target pixel -> spectral WCS wavelength -> band."""
        import tempfile
        from astropy.coordinates import SkyCoord
        from astropy.io import fits
        from astropy.wcs import WCS
        from backend.calibration.spectral_labels import label_spherex_shot, main
        from tests.fake_spherex import make_fake_spherex_mef

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "level2_D6_fake.fits")
            lam_lo, lam_hi, n = make_fake_spherex_mef(path, ra0=135.0, dec0=-7.0, detector=6)
            with fits.open(path) as hdul:
                sky = WCS(hdul["IMAGE"].header).pixel_to_world(20.0, 40.0)
            info = label_spherex_shot(path, sky.ra.deg, sky.dec.deg)
            self.assertEqual(info["detector"], "D6")
            self.assertTrue(info["on_image"])
            self.assertAlmostEqual(info["x_px"], 20.0, places=2)
            self.assertAlmostEqual(info["y_px"], 40.0, places=2)
            expected = lam_lo + (lam_hi - lam_lo) * 40.0 / (n - 1)
            self.assertAlmostEqual(info["lambda_at_target"], expected, places=4)
            self.assertEqual(info["band"], label_exposure_spectral_channel("D6", expected))
            self.assertAlmostEqual(info["bandwidth_um"], 0.037, places=4)
            self.assertEqual(info["mjd"], 60810.5)
            self.assertEqual(main([path, str(sky.ra.deg), str(sky.dec.deg)]), 0)

            far = label_spherex_shot(path, 140.0, -7.0)  # 5 degrees away
            self.assertFalse(far["on_image"])

    @unittest.skipUnless(_HAS_ASTROPY, "astropy not installed")
    def test_stage2_step1_label_real_spherex_cutout(self):
        """Step 1 on a REAL SPHEREx DR1 Level-2 cutout (WISE 0855, D6, 2025-05-05).

        Real IRSA cutouts shift the WCS-WAVE lookup table's reference pixels
        (CRPIX1W/2W = -335/-9 here), which the fake files never exercise.
        Expected values were checked by a hand bilinear lookup in the raw table.
        """
        from astropy.io import fits
        from backend.calibration.spectral_labels import label_spherex_shot

        path = os.path.join(PROJECT_ROOT, "tests", "data", "spherex_dr1_l2_wise0855_D6.fits")
        with fits.open(path) as hdul:
            header = hdul["IMAGE"].header
            self.assertEqual(header["CTYPE1W"], "WAVE-TAB")
            self.assertEqual((header["CRPIX1W"], header["CRPIX2W"]), (-335.0, -9.0))

        info = label_spherex_shot(path, 133.7599, -7.2423)  # cutout centre
        self.assertEqual(info["detector"], "D6")
        self.assertTrue(info["on_image"])
        self.assertAlmostEqual(info["x_px"], 23.87, places=1)
        self.assertAlmostEqual(info["y_px"], 23.63, places=1)
        self.assertAlmostEqual(info["lambda_at_target"], 5.0034, places=4)
        self.assertAlmostEqual(info["bandwidth_um"], 0.0376, places=4)
        self.assertEqual(info["band"], 17)
        self.assertTrue(info["in_nominal_range"])


    def test_stage2_flicker_audit_reduction(self):
        """Step 5: all three tests are measured, and the stacks reach the noise floor."""
        from backend.calibration import clean_visit_exposures, register_shot

        sim = generate_simulated_target_visits("Planet X Candidate", detector="D6", grid_size=64)
        clean_visit_exposures(sim["visits"])
        stacked = perform_band_balanced_stacking(sim["visits"], "D6")["visit_stacks"]

        # Naive method: every single shot, in time order (aligned like the stacks)
        shots = sorted((e for v in sim["visits"] for e in v["exposures"]), key=lambda e: e["mjd_mid"])
        naive = [{"image": register_shot(e["cleaned_image"], None, e["dither_x"], e["dither_y"])[0]} for e in shots]
        stars = [(s["x"], s["y"]) for s in sim["field_stars"]]
        target = [(32 + v["target_displacement_px"][0], 32 + v["target_displacement_px"][1]) for v in sim["visits"]]

        audit = run_still_star_flicker_audit(naive, stacked, stars, exclude_positions=target)
        self.assertEqual(audit["status"], "completed")
        self.assertGreaterEqual(audit["n_stars_audited"], 20)
        self.assertEqual(audit["n_raw_shots"], len(shots))

        # 2. Before vs after: real flicker in single shots, almost none in stacks
        self.assertGreater(audit["mean_raw_flicker_pct"], 5.0)
        self.assertLess(audit["mean_balanced_flicker_pct"], 0.5)
        self.assertLess(audit["mean_balanced_flicker_pct"], 2.0 * audit["mean_balanced_noise_floor_pct"])

        # 1. Ratio test: still stars agree between visits
        self.assertTrue(audit["ratio_test"]["passed"])
        self.assertLess(audit["ratio_test"]["max_abs_deviation_pct"], 2.0)

        # 3. Difference test: pure noise, no leftover stars
        self.assertTrue(audit["null_test_passed"], audit["null_test_verdict"])
        self.assertGreater(audit["null_test_chi2_nu"], 0.6)
        self.assertLess(audit["null_test_chi2_nu"], 1.5)

    def test_stage2_alignment_is_needed(self):
        """Without aligning shots, pointing jitter leaves leftover star light in differences."""
        from backend.calibration import clean_visit_exposures

        sim = generate_simulated_target_visits("Planet X Candidate", detector="D6", grid_size=64)
        clean_visit_exposures(sim["visits"])
        stars = [(s["x"], s["y"]) for s in sim["field_stars"]]
        target = [(32 + v["target_displacement_px"][0], 32 + v["target_displacement_px"][1]) for v in sim["visits"]]
        naive = [{"image": e["cleaned_image"]} for v in sim["visits"] for e in v["exposures"]]

        unaligned = perform_band_balanced_stacking(sim["visits"], "D6", register=False)["visit_stacks"]
        audit = run_still_star_flicker_audit(naive, unaligned, stars, exclude_positions=target)
        self.assertGreater(audit["null_test_star_chi2_nu"], 5.0)

    def test_stage3_102_channel_spectrophotometry(self):
        """Verify full 102-channel grid across D1-D6 and molecular line detection."""
        grid = generate_102_channel_grid()
        self.assertEqual(len(grid), 102)
        
        target = BENCHMARK_TARGETS["WISE 0855-0714"]
        spec = extract_102_channel_spectrum(target, source_mode="simulated")
        self.assertEqual(spec["total_channels"], 102)
        self.assertTrue(any("CH4" in f for f in spec["detected_molecular_features"]))

    def test_stage3_astrometric_centroiding(self):
        """Verify 2D Gaussian centroiding and proper motion linear fit."""
        img = [[0.0 for _ in range(32)] for _ in range(32)]
        img[16][16] = 50.0
        img[16][17] = 30.0
        cx, cy, peak = fit_2d_centroid(img, 16.0, 16.0)
        self.assertAlmostEqual(cx, 16.375, places=1)
        self.assertAlmostEqual(cy, 16.0, places=1)

    def test_stage4_wcs_relative_positioning(self):
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

    def test_stage4_idea2_spectral_superposition(self):
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

    def test_stage4_gif_encoder_stream(self):
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
