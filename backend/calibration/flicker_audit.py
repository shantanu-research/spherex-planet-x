"""
SPHEREx Planet X Challenge - Band-balancing Step 5: prove the band-balanced stacks work.

Three measured tests (Track2_Colour_Shift_Solution.pdf, Step 5):
  1. Still-star ratio test: each still star's brightness in visit v divided by visit 1
     should be ~1, within its measured noise.
  2. Before vs after: brightness scatter of the same stars using the naive method
     (every single shot in time order) versus the band-balanced visit stacks.
  3. Difference test: subtracting two visit stacks should leave pure noise, i.e.
     chi2/nu ~ 1 using the propagated stack variances, with no leftover stars.

Nothing here is hard-coded: every number in the output is computed from the images.
"""

from typing import List, Dict, Any, Tuple, Optional
import math

APERTURE_RADIUS_PX = 2.5
ANNULUS_INNER_PX = APERTURE_RADIUS_PX + 1.5
ANNULUS_OUTER_PX = APERTURE_RADIUS_PX + 3.5


def aperture_photometry(
    image: List[List[Optional[float]]],
    cx: float,
    cy: float,
    variance: Optional[List[List[Optional[float]]]] = None,
    radius: float = APERTURE_RADIUS_PX,
) -> Dict[str, float]:
    """
    Circular-aperture flux with background-annulus subtraction.

    Returns {"flux", "flux_err", "n_masked"}:
      - flux_err comes from the variance image (aperture + background term), or 0 if none.
      - n_masked counts None/NaN pixels inside the aperture; a shot with masked
        aperture pixels under-measures the star, so callers should skip it.
    """
    height = len(image)
    width = len(image[0])
    r2 = radius * radius
    annulus_in2 = (radius + 1.5) ** 2
    annulus_out2 = (radius + 3.5) ** 2

    ap_sum = 0.0
    ap_var = 0.0
    ap_n = 0
    n_masked = 0
    bg_vals: List[float] = []
    bg_var_sum = 0.0

    min_x = max(0, int(cx - radius - 4))
    max_x = min(width - 1, int(cx + radius + 4))
    min_y = max(0, int(cy - radius - 4))
    max_y = min(height - 1, int(cy + radius + 4))

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            dist2 = (x - cx) ** 2 + (y - cy) ** 2
            in_ap = dist2 <= r2
            in_bg = annulus_in2 <= dist2 <= annulus_out2
            if not (in_ap or in_bg):
                continue
            val = image[y][x]
            if val is None or (isinstance(val, float) and math.isnan(val)):
                if in_ap:
                    n_masked += 1
                continue
            var = None
            if variance is not None:
                var = variance[y][x]
            if in_ap:
                ap_sum += val
                ap_n += 1
                if var is not None:
                    ap_var += var
            else:
                bg_vals.append(val)
                if var is not None:
                    bg_var_sum += var

    n_bg = len(bg_vals)
    bg_level = (sum(bg_vals) / n_bg) if n_bg else 0.0
    flux = ap_sum - bg_level * ap_n
    # Error of (aperture sum - n_ap * mean background)
    bg_mean_var = (bg_var_sum / (n_bg * n_bg)) if n_bg else 0.0
    flux_var = ap_var + (ap_n ** 2) * bg_mean_var
    return {"flux": flux, "flux_err": math.sqrt(max(0.0, flux_var)), "n_masked": n_masked}


def measure_aperture_flux(image: List[List[float]], cx: float, cy: float, radius: float = APERTURE_RADIUS_PX) -> float:
    """Calculates circular aperture flux around (cx, cy) with background annulus subtraction."""
    return max(0.0, aperture_photometry(image, cx, cy, radius=radius)["flux"])


def compute_flicker_statistics(flux_series: List[float]) -> Tuple[float, float, float]:
    """Returns (mean_flux, std_flux, fractional_scatter_sigma_over_mean)."""
    valid = [f for f in flux_series if f > 0.0]
    if len(valid) < 2:
        return 0.0, 0.0, 0.0
    mean_val = sum(valid) / len(valid)
    variance = sum((f - mean_val) ** 2 for f in valid) / (len(valid) - 1)
    std_val = math.sqrt(variance)
    fractional_scatter = (std_val / mean_val) if mean_val > 0.0 else 0.0
    return round(mean_val, 4), round(std_val, 4), round(fractional_scatter, 4)


def _near(x: float, y: float, points: List[Tuple[float, float]], radius: float) -> bool:
    r2 = radius * radius
    return any((x - px) ** 2 + (y - py) ** 2 <= r2 for px, py in points)


def select_still_stars(
    star_positions: List[Tuple[float, float]],
    width: int,
    height: int,
    exclude_positions: Optional[List[Tuple[float, float]]] = None,
    exclude_radius_px: float = 8.0,
) -> Tuple[List[Tuple[int, float, float]], Dict[str, int]]:
    """
    Keeps stars whose aperture and background annulus fit on the image and that are not
    near a moving object (the target). Returns ([(index, x, y)], skip counts).
    """
    margin = ANNULUS_OUTER_PX + 1.0
    exclude_positions = exclude_positions or []
    kept: List[Tuple[int, float, float]] = []
    skipped = {"edge": 0, "near_mover": 0}
    for i, (sx, sy) in enumerate(star_positions):
        if not (margin <= sx <= width - 1 - margin and margin <= sy <= height - 1 - margin):
            skipped["edge"] += 1
        elif _near(sx, sy, exclude_positions, exclude_radius_px):
            skipped["near_mover"] += 1
        else:
            kept.append((i, sx, sy))
    return kept, skipped


def run_difference_test(
    stack_a: Dict[str, Any],
    stack_b: Dict[str, Any],
    star_positions: List[Tuple[float, float]],
    exclude_positions: Optional[List[Tuple[float, float]]] = None,
    exclude_radius_px: float = 8.0,
    block_px: int = 3,
) -> Dict[str, Any]:
    """
    Difference test: D = B - A should be pure noise for a field with no movers.

    - Field: D is summed in block_px x block_px blocks (away from stars and movers) and
      each block sum is divided by its propagated noise. chi2/nu ~ 1 means pure noise.
      Blocks are used because aligning shots correlates neighbouring pixels.
    - Stars: aperture photometry on D at every still star; (leftover flux / error)^2
      averaged over stars. ~1 means no leftover stars.
    Pixels near movers (e.g. the target) are excluded.
    """
    img_a, img_b = stack_a["stacked_image"], stack_b["stacked_image"]
    var_a, var_b = stack_a.get("stacked_variance"), stack_b.get("stacked_variance")
    if var_a is None or var_b is None:
        return {"status": "not_run", "reason": "Stacks carry no variance images"}

    height, width = len(img_a), len(img_a[0])
    exclude_positions = exclude_positions or []
    diff = [[None] * width for _ in range(height)]
    diff_var = [[None] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            a, b, va, vb = img_a[y][x], img_b[y][x], var_a[y][x], var_b[y][x]
            if a is None or b is None or va is None or vb is None:
                continue
            diff[y][x] = b - a
            diff_var[y][x] = va + vb

    # Field: block sums away from stars (within annulus radius) and movers
    star_keep_out = ANNULUS_OUTER_PX + 1.0
    chi2_field, n_blocks = 0.0, 0
    for by in range(0, height - block_px + 1, block_px):
        for bx in range(0, width - block_px + 1, block_px):
            cx, cy = bx + (block_px - 1) / 2.0, by + (block_px - 1) / 2.0
            if _near(cx, cy, star_positions, star_keep_out) or _near(cx, cy, exclude_positions, exclude_radius_px):
                continue
            vals = [diff[y][x] for y in range(by, by + block_px) for x in range(bx, bx + block_px)]
            vars_ = [diff_var[y][x] for y in range(by, by + block_px) for x in range(bx, bx + block_px)]
            if any(v is None for v in vals) or any(v is None for v in vars_):
                continue
            v_sum = sum(vars_)
            if v_sum <= 0.0:
                continue
            chi2_field += sum(vals) ** 2 / v_sum
            n_blocks += 1

    # Stars: leftover aperture flux in the difference image
    star_terms = []
    for sx, sy in star_positions:
        if _near(sx, sy, exclude_positions, exclude_radius_px):
            continue
        phot = aperture_photometry(diff, sx, sy, diff_var)
        if phot["n_masked"] or phot["flux_err"] <= 0.0:
            continue
        star_terms.append((phot["flux"] / phot["flux_err"]) ** 2)

    chi2_nu_field = chi2_field / n_blocks if n_blocks else None
    chi2_nu_stars = sum(star_terms) / len(star_terms) if star_terms else None
    return {
        "status": "completed",
        "visits": [stack_a.get("visit_id"), stack_b.get("visit_id")],
        "chi2_nu_field": round(chi2_nu_field, 3) if chi2_nu_field is not None else None,
        "n_field_blocks": n_blocks,
        "chi2_nu_star_apertures": round(chi2_nu_stars, 3) if chi2_nu_stars is not None else None,
        "n_stars": len(star_terms),
    }


def run_still_star_flicker_audit(
    raw_visit_frames: List[Dict[str, Any]],
    balanced_visit_frames: List[Dict[str, Any]],
    field_star_positions: List[Tuple[float, float]],
    exclude_positions: Optional[List[Tuple[float, float]]] = None,
    exclude_radius_px: float = 8.0,
    ratio_tolerance: float = 0.05,
    difference_chi2_range: Tuple[float, float] = (0.7, 1.5),
    star_residual_chi2_max: float = 3.0,
) -> Dict[str, Any]:
    """
    Step 5 audit.

    raw_visit_frames: the naive series, i.e. EVERY single shot in time order
        (each {"image": ...}, preferably the cleaned image).
    balanced_visit_frames: the band-balanced visit stacks (with stacked_variance).
    field_star_positions: still (catalogued, non-moving) star positions in pixels.
    exclude_positions: positions of moving objects (e.g. the target in each visit),
        kept out of every test.
    """
    if not raw_visit_frames or not balanced_visit_frames:
        return {"status": "not_run", "reason": "No frames supplied"}

    sample = balanced_visit_frames[0]["stacked_image"]
    height, width = len(sample), len(sample[0])
    stars, skipped = select_still_stars(
        field_star_positions, width, height, exclude_positions, exclude_radius_px
    )

    star_audit_results = []
    raw_scatters: List[float] = []
    balanced_scatters: List[float] = []
    noise_floors: List[float] = []
    ratio_devs: List[float] = []
    ratio_chi2_terms: List[float] = []
    n_shots_skipped_masked = 0

    for star_idx, sx, sy in stars:
        # 1. Naive: every single shot in time order (skip shots with masked aperture pixels)
        raw_fluxes = []
        for frame in raw_visit_frames:
            phot = aperture_photometry(frame["image"], sx, sy)
            if phot["n_masked"]:
                n_shots_skipped_masked += 1
                continue
            raw_fluxes.append(phot["flux"])
        r_mean, _, r_scatter = compute_flicker_statistics(raw_fluxes)

        # 2. Band-balanced visit stacks, with propagated noise
        bal = [
            aperture_photometry(v["stacked_image"], sx, sy, v.get("stacked_variance"))
            for v in balanced_visit_frames
        ]
        bal_fluxes = [p["flux"] for p in bal]
        b_mean, _, b_scatter = compute_flicker_statistics(bal_fluxes)
        if r_mean <= 0.0 or b_mean <= 0.0:
            skipped.setdefault("no_flux", 0)
            skipped["no_flux"] += 1
            continue

        # Expected scatter from noise alone (what's left if the colour flicker is gone)
        noise_floor = (sum(p["flux_err"] for p in bal) / len(bal)) / b_mean

        # 3. Ratio test vs visit 1
        f1, e1 = bal[0]["flux"], bal[0]["flux_err"]
        ratios = []
        for p in bal[1:]:
            ratio = p["flux"] / f1 if f1 > 0.0 else 0.0
            ratios.append(round(ratio, 4))
            ratio_devs.append(abs(ratio - 1.0))
            denom = math.sqrt(p["flux_err"] ** 2 + e1 ** 2)
            if denom > 0.0:
                ratio_chi2_terms.append(((p["flux"] - f1) / denom) ** 2)

        raw_scatters.append(r_scatter)
        balanced_scatters.append(b_scatter)
        noise_floors.append(noise_floor)

        pct_reduction = round(((r_scatter - b_scatter) / r_scatter) * 100.0, 1) if r_scatter > 0.0 else 0.0
        star_audit_results.append({
            "star_index": star_idx + 1,
            "x_px": sx,
            "y_px": sy,
            "raw_mean_flux": r_mean,
            "raw_scatter_pct": round(r_scatter * 100.0, 2),
            "n_raw_shots": len(raw_fluxes),
            "balanced_mean_flux": b_mean,
            "balanced_scatter_pct": round(b_scatter * 100.0, 2),
            "balanced_noise_floor_pct": round(noise_floor * 100.0, 2),
            "flicker_reduction_pct": pct_reduction,
            "ratio_to_visit1": ratios,
            "raw_fluxes": [round(f, 3) for f in raw_fluxes],
            "balanced_fluxes": [round(f, 3) for f in bal_fluxes],
        })

    n = len(star_audit_results)
    if n == 0:
        return {"status": "not_run", "reason": "No usable still stars", "stars_skipped": skipped}

    mean_raw = sum(raw_scatters) / n
    mean_bal = sum(balanced_scatters) / n
    mean_noise = sum(noise_floors) / n
    overall_reduction = ((mean_raw - mean_bal) / mean_raw) * 100.0 if mean_raw > 0 else 0.0

    # Ratio test summary
    mean_ratio_dev = sum(ratio_devs) / len(ratio_devs) if ratio_devs else 0.0
    max_ratio_dev = max(ratio_devs) if ratio_devs else 0.0
    ratio_chi2_nu = sum(ratio_chi2_terms) / len(ratio_chi2_terms) if ratio_chi2_terms else None
    ratio_pass = max_ratio_dev <= ratio_tolerance

    # Difference test: every consecutive pair of visit stacks
    star_xy = [(sx, sy) for _, sx, sy in stars]
    diff_tests = [
        run_difference_test(a, b, star_xy, exclude_positions, exclude_radius_px)
        for a, b in zip(balanced_visit_frames[:-1], balanced_visit_frames[1:])
    ]
    diff_done = [d for d in diff_tests if d["status"] == "completed"]
    if diff_done:
        chi2_field = sum(d["chi2_nu_field"] for d in diff_done) / len(diff_done)
        star_vals = [d["chi2_nu_star_apertures"] for d in diff_done if d["chi2_nu_star_apertures"] is not None]
        chi2_star = sum(star_vals) / len(star_vals) if star_vals else None
        lo, hi = difference_chi2_range
        field_ok = lo <= chi2_field <= hi
        stars_ok = chi2_star is None or chi2_star <= star_residual_chi2_max
        diff_pass = field_ok and stars_ok
        verdict = (
            f"{'PASS' if diff_pass else 'FAIL'}: field chi2/nu = {chi2_field:.2f} "
            f"(pure noise = 1, allowed {lo}-{hi}); inside star apertures chi2/nu = "
            f"{chi2_star:.2f} (allowed <= {star_residual_chi2_max})"
            if chi2_star is not None else
            f"{'PASS' if diff_pass else 'FAIL'}: field chi2/nu = {chi2_field:.2f}"
        )
    else:
        chi2_field = chi2_star = None
        diff_pass = None
        verdict = "NOT RUN: " + (diff_tests[0].get("reason", "fewer than 2 visits") if diff_tests else "fewer than 2 visits")

    return {
        "status": "completed",
        "n_stars_audited": n,
        "stars_skipped": skipped,
        "n_raw_shots": len(raw_visit_frames),
        "n_raw_shots_skipped_masked": n_shots_skipped_masked,
        # 2. Before vs after
        "mean_raw_flicker_pct": round(mean_raw * 100.0, 2),
        "max_raw_flicker_pct": round(max(raw_scatters) * 100.0, 2),
        "mean_balanced_flicker_pct": round(mean_bal * 100.0, 2),
        "mean_balanced_noise_floor_pct": round(mean_noise * 100.0, 2),
        "overall_flicker_suppression_pct": round(overall_reduction, 1),
        # 1. Ratio test
        "ratio_test": {
            "mean_abs_deviation_pct": round(mean_ratio_dev * 100.0, 2),
            "max_abs_deviation_pct": round(max_ratio_dev * 100.0, 2),
            "chi2_nu": round(ratio_chi2_nu, 2) if ratio_chi2_nu is not None else None,
            "tolerance_pct": ratio_tolerance * 100.0,
            "passed": ratio_pass,
        },
        # 3. Difference test
        "null_test_chi2_nu": round(chi2_field, 2) if chi2_field is not None else None,
        "null_test_star_chi2_nu": round(chi2_star, 2) if chi2_star is not None else None,
        "null_test_passed": diff_pass,
        "null_test_verdict": verdict,
        "difference_tests": diff_tests,
        "stars": star_audit_results,
    }
