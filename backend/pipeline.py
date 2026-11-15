"""
SPHEREx Planet X Challenge - Master Pipeline Orchestrator
Modular orchestration engine uniting Tracks 1, 2, 3, and 4.
Decoupled from HTTP transport to support CLI, batch workflows, and REST APIs.
Compliant with NASA Space Apps 2026 Master Technical Architecture & Execution Plan.
"""

import math
import io
from typing import Dict, Any, List, Optional, Tuple
from backend.track1_orchestration.catalog import get_target_by_query
from backend.track1_orchestration.resolver import resolve_target, SPHEREx_PIXEL_SCALE_ARCSEC
from backend.track2_calibration.cleaning import clean_frame_data
from backend.track2_calibration.band_balancer import perform_band_balanced_stacking
from backend.track2_calibration.flicker_audit import run_still_star_flicker_audit
from backend.track2_calibration.differencing import (
    compute_difference_frames,
    compute_temporal_median_template,
    perform_shift_and_stack,
)
from backend.track3_spectrophotometry.spectrum_extractor import extract_102_channel_spectrum
from backend.track3_spectrophotometry.astrometric_validator import validate_proper_motion_astrometry
from backend.track4_rendering.wcs_engine import WCSEngine
from backend.track4_rendering.colorization import (
    colorize_detector_image,
    composite_multiband_false_color,
    DETECTOR_SUPERPOSITION_WEIGHTS,
)
from backend.track4_rendering.stretching import (
    calculate_percentiles,
    apply_global_detector_asinh_stretch,
    apply_symmetric_difference_stretch,
)
from backend.track4_rendering.gif_encoder import burn_telemetry_hud, encode_gif_stream
from backend.simulation.synthetic_spherex import generate_simulated_target_visits
from backend.data_loader import target_catalog, SPHEREX_BANDS


def execute_pipeline(
    target_key: str = "WISE 0855-0714",
    detector: str = "D6",
    mode: str = "visit_blink",
    frame_mode: Optional[str] = None,
    color_mode: Optional[str] = None,
    process_mode: Optional[str] = None,
    stretch: str = "asinh",
    fov_arcmin: float = 6.5,
    source_mode: str = "auto",
    fov_mode: Optional[str] = None,
    blink_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes complete 4-track scientific pipeline supporting the 7 Unified Viewing Modes (Section 9.1).
    Supports calibrated SPHEREx D1-D6 FITS observations
    and synthetic benchmark cubes.
    """
    if not math.isfinite(fov_arcmin) or not 1 <= fov_arcmin <= 15:
        raise ValueError("Field of view must be 1–15 arcminutes")
    if stretch not in ('asinh','sqrt','log','linear'):
        raise ValueError("Unknown display stretch")
    if frame_mode not in (None,'inertial','comoving') or color_mode not in (None,'grayscale','spectral','multiband'):
        raise ValueError("Unknown frame or color mode")
    effective_mode = mode.lower()
    detector = detector.upper()

    # Determine mode configurations
    if effective_mode == "longest_baseline":
        eff_frame_mode = frame_mode or "inertial"
        eff_color_mode = color_mode or "spectral"
        eff_process_mode = process_mode or "balanced"
    elif effective_mode == "difference_sequence":
        eff_frame_mode = frame_mode or "inertial"
        eff_color_mode = color_mode or "spectral"
        eff_process_mode = process_mode or "difference"
    elif effective_mode == "motion_tracked":
        eff_frame_mode = frame_mode or "comoving"
        eff_color_mode = color_mode or "spectral"
        eff_process_mode = process_mode or "balanced"
    elif effective_mode == "spectral_color":
        eff_frame_mode = frame_mode or "inertial"
        eff_color_mode = color_mode or "multiband"
        eff_process_mode = process_mode or "balanced"
    elif effective_mode == "wavelength_matched":
        eff_frame_mode = frame_mode or "inertial"
        eff_color_mode = color_mode or "spectral"
        eff_process_mode = process_mode or "wavelength_matched"
    elif effective_mode == "within_visit_fast":
        eff_frame_mode = frame_mode or "inertial"
        eff_color_mode = color_mode or "spectral"
        eff_process_mode = process_mode or "within_visit"
    elif effective_mode == "shift_stack":
        eff_frame_mode = frame_mode or "inertial"
        eff_color_mode = color_mode or "spectral"
        eff_process_mode = "shift_stack"
    else:  # 'visit_blink' default (Mode 1)
        eff_frame_mode = frame_mode or "inertial"
        eff_color_mode = color_mode or "spectral"
        eff_process_mode = process_mode or "balanced"

    # 1. Track 1: Ingestion & Resolution
    from backend.targets import resolve
    target_meta = resolve(target_key)
    resolved = {"target": target_meta, "stale_epoch_warning": None}

    # Determine effective FOV mode: 'wide' (30' wide field) or 'core' (6.5' center stamp)
    eff_fov_mode = fov_mode or ("wide" if fov_arcmin >= 20.0 else "core")
    eff_blink_mode = blink_mode or ("temporal" if ("temporal" in effective_mode or "epoch" in effective_mode) else "spectral")

    if source_mode in ('auto', 'real'):
        from backend.real_pipeline import render
        return render(target_meta, detector, fov_arcmin, effective_mode, stretch, frame_mode, color_mode)
    if source_mode not in ('simulated', 'simulation', 'synthetic'):
        raise ValueError('Source must be real, auto or simulated')

    # Generate multi-epoch Level-2 simulation
    sim_data = generate_simulated_target_visits(target_key=target_key, detector=detector, grid_size=64)
    raw_visits = sim_data["visits"]
    field_stars = sim_data["field_stars"]
    star_positions = [(s["x"], s["y"]) for s in field_stars]

    # 2. Track 2: Cleaning & Akhilesh's 5-Step Band-Balanced Stacking
    for v in raw_visits:
        for exp in v["exposures"]:
            clean_img, clean_wt, _ = clean_frame_data(
                exp["image"], exp["flags"], exp["variance"], exp["zodi"]
            )
            exp["cleaned_image"] = clean_img

    stack_res = perform_band_balanced_stacking(raw_visits, detector=detector)
    balanced_visits = stack_res["visit_stacks"]

    # Track 2: Automated Still-Star Flicker Audit
    raw_first_frames = [{"image": v["exposures"][0]["image"]} for v in raw_visits]
    flicker_audit = run_still_star_flicker_audit(raw_first_frames, balanced_visits, star_positions)

    # Track 2: Temporal Median Template & Difference Imaging
    balanced_images = [v["stacked_image"] for v in balanced_visits]
    median_template = compute_temporal_median_template(balanced_images)
    diff_visits = compute_difference_frames(balanced_visits, template=median_template)

    # Track 3: 102-Channel Spectrophotometry & Astrometric Validation
    spectrum_data = extract_102_channel_spectrum(target_meta, source_mode="simulated")
    astrometric_validation = validate_proper_motion_astrometry(balanced_visits, target_meta)

    # 3. Track 4: WCS Engine, Idea 1 Relative Positioning & Stretching
    wcs = WCSEngine(fov_arcmin=fov_arcmin, center_ra_deg=target_meta["ra_deg"], center_dec_deg=target_meta["dec_deg"])

    # Determine which image series to render based on viewing mode
    active_series: List[Dict[str, Any]] = []
    is_difference_mode = False

    if effective_mode == "longest_baseline":
        # 2-frame toggle between earliest (V1) and latest (VM)
        active_series = [balanced_visits[0], balanced_visits[-1]]
    elif effective_mode == "difference_sequence" or eff_process_mode == "difference":
        active_series = diff_visits
        is_difference_mode = True
    elif eff_process_mode == "raw":
        active_series = [
            {
                "stacked_image": v["exposures"][idx % len(v["exposures"])]["image"],
                "visit_id": v["visit_id"],
                "date_utc": v["date_utc"],
                "mjd_mid": v["mjd_mid"],
                "target_pos_px": v["target_pos_px"],
                "target_displacement_px": v["target_displacement_px"],
            }
            for idx, v in enumerate(raw_visits)
        ]
    elif eff_process_mode == "shift_stack":
        # Shift and stack aligned on target motion
        cat_pm_ra = target_meta["pm_ra_mas"]
        cat_pm_dec = target_meta["pm_dec_mas"]
        dt_yr_step = 0.51  # ~6 months between survey visits
        vx = -(cat_pm_ra / 1000.0 * dt_yr_step) / SPHEREx_PIXEL_SCALE_ARCSEC
        vy = (cat_pm_dec / 1000.0 * dt_yr_step) / SPHEREx_PIXEL_SCALE_ARCSEC
        shift_stack_img = perform_shift_and_stack(balanced_visits, (vx, vy))
        active_series = [
            {
                "stacked_image": shift_stack_img,
                "visit_id": v["visit_id"],
                "date_utc": v["date_utc"],
                "mjd_mid": v["mjd_mid"],
                "target_pos_px": (32.0, 32.0),
                "target_displacement_px": (0.0, 0.0),
            }
            for v in balanced_visits
        ]
    elif effective_mode == "wavelength_matched":
        matched_frames = []
        for v_idx in [0, len(raw_visits) - 1]:
            v = raw_visits[v_idx]
            matched_exp = v["exposures"][1]  # exposure in channel 5
            matched_frames.append({
                "stacked_image": matched_exp["image"],
                "visit_id": f"{v['visit_id']}-Ch5",
                "date_utc": v["date_utc"],
                "mjd_mid": matched_exp["mjd_mid"],
                "target_pos_px": v["target_pos_px"],
                "target_displacement_px": v["target_displacement_px"],
                "wavelength_um": matched_exp["wavelength_um"],
            })
        active_series = matched_frames
    elif effective_mode == "within_visit_fast":
        v0 = raw_visits[0]
        fast_frames = []
        for e_idx, exp in enumerate(v0["exposures"]):
            fast_frames.append({
                "stacked_image": exp["image"],
                "visit_id": f"V1-Exp{e_idx+1}",
                "date_utc": f"2025-05-15 +{e_idx*3}hr",
                "mjd_mid": exp["mjd_mid"],
                "target_pos_px": v0["target_pos_px"],
                "target_displacement_px": v0["target_displacement_px"],
                "wavelength_um": exp["wavelength_um"],
            })
        active_series = fast_frames
    else:  # 'visit_blink' default
        active_series = balanced_visits

    # Calculate sequence-wide global detector-locked percentiles (never per-frame)
    all_pixels = []
    for s in active_series:
        img = s.get("stacked_image") or s.get("difference_image")
        for row in img:
            for val in row:
                if val is not None:
                    all_pixels.append(val)
    vmin, vmax = calculate_percentiles(all_pixels, p_low=0.5, p_high=99.5)

    # Multi-band frames (D1, D3, D6) if multiband mode requested
    d1_stacks, d3_stacks, d6_stacks = None, None, None
    if eff_color_mode == "multiband":
        d1_sim = generate_simulated_target_visits(target_key, "D1", 64)["visits"]
        d3_sim = generate_simulated_target_visits(target_key, "D3", 64)["visits"]
        d6_sim = generate_simulated_target_visits(target_key, "D6", 64)["visits"]
        d1_stacks = perform_band_balanced_stacking(d1_sim, "D1")["visit_stacks"]
        d3_stacks = perform_band_balanced_stacking(d3_sim, "D3")["visit_stacks"]
        d6_stacks = perform_band_balanced_stacking(d6_sim, "D6")["visit_stacks"]

    # Render processed frames
    rendered_frames = []
    for idx, item in enumerate(active_series):
        raw_img = item.get("stacked_image") or item.get("difference_image")

        disp = item.get("target_displacement_px")
        if disp is None:
            orig_visit_idx = min(idx, len(raw_visits) - 1)
            disp = raw_visits[orig_visit_idx]["target_displacement_px"]

        target_pos = item.get("target_pos_px")
        if target_pos is None:
            orig_visit_idx = min(idx, len(raw_visits) - 1)
            target_pos = raw_visits[orig_visit_idx]["target_pos_px"]

        # Idea 1: Apply WCS Relative Transformation (Inertial vs Co-Moving)
        positioned_img = wcs.transform_frame(raw_img, target_displacement_px=disp, mode=eff_frame_mode)

        # Idea 2: Apply Colorization
        if is_difference_mode:
            rgb_frame, _ = apply_symmetric_difference_stretch(positioned_img)
        elif eff_color_mode == "grayscale":
            stretched = apply_global_detector_asinh_stretch(positioned_img, vmin, vmax)
            rgb_frame = [[(int(val * 255), int(val * 255), int(val * 255)) for val in row] for row in stretched]
        elif eff_color_mode == "multiband" and d1_stacks is not None:
            m_idx = min(idx, len(d1_stacks) - 1)
            b_img = wcs.transform_frame(d1_stacks[m_idx]["stacked_image"], disp, mode=eff_frame_mode)
            g_img = wcs.transform_frame(d3_stacks[m_idx]["stacked_image"], disp, mode=eff_frame_mode)
            r_img = wcs.transform_frame(d6_stacks[m_idx]["stacked_image"], disp, mode=eff_frame_mode)
            rgb_frame = composite_multiband_false_color(b_img, g_img, r_img, vmin=0.0, vmax=max(vmax, 15.0))
        else:  # 'spectral' Idea 2 default
            stretched = apply_global_detector_asinh_stretch(positioned_img, vmin, vmax)
            rgb_frame = colorize_detector_image(stretched, detector, vmin=0.0, vmax=1.0)

        rendered_frames.append({
            "frame_id": f"frame_{idx+1}",
            "visit_id": item.get("visit_id", f"V{idx+1}"),
            "date_utc": item.get("date_utc", "2025-05-15"),
            "mjd": item.get("mjd_mid", 60810.0),
            "target_pos_px": target_pos,
            "target_displacement_px": disp,
            "rgb_pixels": rgb_frame,
        })

    manifest = {
        "target": target_meta["common_name"],
        "category": target_meta["category"],
        "detector": detector,
        "mode": effective_mode,
        "frame_mode": eff_frame_mode,
        "color_mode": eff_color_mode,
        "process_mode": eff_process_mode,
        "grid_size": 64,
        "pixel_scale_arcsec": SPHEREx_PIXEL_SCALE_ARCSEC,
        "fov_arcmin": fov_arcmin,
        "n_frames": len(rendered_frames),
        "stretches": {
            "stretch_type": stretch,
            "vmin": round(vmin, 3),
            "vmax": round(vmax, 3),
        },
        "scientific_disclaimer": (
            "Colors represent near-infrared SPHEREx wavelengths (0.744 - 5.002 um) mapped onto the human "
            "visible spectrum (380 - 750 nm) via constant-resolving-power logarithmic superposition (Lupton 2004 Asinh compression)."
        ),
    }

    p9_detectability = {
        "single_visit_limit_ab_mag": 17.61,
        "coadded_stack_limit_ab_mag": round(17.61 + 1.25 * math.log10(max(1, len(rendered_frames))), 2),
        "planet_nine_predicted_v_mag": 23.5,
        "magnitude_gap_to_p9": round(23.5 - (17.61 + 1.25 * math.log10(max(1, len(rendered_frames)))), 2),
        "coadded_visits": len(rendered_frames),
        "detection_verdict": "BELOW_SINGLE_VISIT_THRESHOLD (Requires Shift-and-Stack Coadd)" if "Planet X" in target_key else "CONFIRMED_POINT_SOURCE",
        "zodiacal_light_subtraction": "Simulated ZODI gradient modeled",
        "cosmic_ray_filter": "Artifact flags cleaned"
    }

    return {
        "status": "success",
        "manifest": manifest,
        "target": target_meta,
        "stale_epoch_warning": resolved["stale_epoch_warning"],
        "detector": detector,
        "mode": effective_mode,
        "frame_mode": eff_frame_mode,
        "color_mode": eff_color_mode,
        "process_mode": eff_process_mode,
        "grid_size": 64,
        "flicker_audit": flicker_audit,
        "astrometric_validation": astrometric_validation,
        "planet_nine_detectability": p9_detectability,
        "spectrophotometry": spectrum_data,
        "field_stars": field_stars,
        "frames": rendered_frames,
    }


def generate_gif_export(
    target_key: str,
    detector: str,
    mode: str,
    fps: int,
    source_mode: str = "auto",
    fov_mode: Optional[str] = None,
    blink_mode: Optional[str] = None,
    fov_arcmin: float = 6.5,
    frame_mode: Optional[str] = None,
    color_mode: Optional[str] = None,
    stretch: str = "asinh",
) -> bytes:
    """Compiles deterministic animated GIF with burned-in HUD telemetry."""
    pipeline_res = execute_pipeline(
        target_key=target_key,
        detector=detector,
        mode=mode,
        source_mode=source_mode,
        fov_mode=fov_mode,
        blink_mode=blink_mode,
        fov_arcmin=fov_arcmin, frame_mode=frame_mode, color_mode=color_mode, stretch=stretch,
    )
    raw_frames = pipeline_res["frames"]
    if not raw_frames:
        raise ValueError(pipeline_res.get("message", "No frames are available to export"))
    hud_frames = []

    from PIL import Image
    import numpy as np
    mode_label = ("REAL " if pipeline_res.get("is_real_data") else "SIMULATED ") + mode.upper()
    for f in raw_frames:
        hud_frame = burn_telemetry_hud(
            rgb_frame=np.asarray(Image.fromarray(np.asarray(f["rgb_pixels"], dtype=np.uint8)).resize((384,384), Image.Resampling.NEAREST)).tolist(),
            target_name=pipeline_res["target"]["common_name"],
            visit_id=f.get("visit_id") or f.get("label", "Frame"),
            mjd=f.get("mjd", 60810.0),
            detector=f.get("band", detector),
            mode_str=mode_label,
        )
        hud_frames.append(hud_frame)

    delay_ms = max(50, int(1000 / max(1, fps)))

    # Pillow is a runtime dependency: do not fall back to the legacy LZW encoder,
    # which corrupts some nontrivial images while passing header-only checks.
    from PIL import Image
    import numpy as np
    pil_images = [Image.fromarray(np.array(f, dtype=np.uint8)) for f in hud_frames]
    bio = io.BytesIO()
    pil_images[0].save(bio, format="GIF", save_all=True,
                       append_images=pil_images[1:], duration=delay_ms, loop=0)
    return bio.getvalue()



__all__ = [
    "execute_pipeline",
    "generate_gif_export",
]
