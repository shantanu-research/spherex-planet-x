"""
SPHEREx Planet X Challenge - Akhilesh's 5-Step Band-Balanced LVF Stacking Engine
Eliminates artificial 20-30% brightness flicker caused by stepped Linear Variable Filter (LVF) pointings.
"""

from typing import List, Dict, Any, Tuple, Optional
import math

# SPHEREx Detector Bandpass Definitions (Table 2.1)
DETECTOR_SPECS = {
    "D1": {"name": "SPHEREx-D1", "lmin": 0.744, "lmax": 1.116, "R": 39, "dichroic_pair": "D4"},
    "D2": {"name": "SPHEREx-D2", "lmin": 1.099, "lmax": 1.651, "R": 41, "dichroic_pair": "D5"},
    "D3": {"name": "SPHEREx-D3", "lmin": 1.636, "lmax": 2.421, "R": 41, "dichroic_pair": "D6"},
    "D4": {"name": "SPHEREx-D4", "lmin": 2.423, "lmax": 3.822, "R": 35, "dichroic_pair": "D1"},
    "D5": {"name": "SPHEREx-D5", "lmin": 3.809, "lmax": 4.420, "R": 112, "dichroic_pair": "D2"},
    "D6": {"name": "SPHEREx-D6", "lmin": 4.412, "lmax": 5.002, "R": 128, "dichroic_pair": "D3"}
}

N_BANDS = 17
# PDF Step 3: fewer shared bands than this -> comparison marked unreliable
MIN_SHARED_BANDS = 10
# PDF Step 4: sub-band stacks group about this many neighbouring bands
SUB_BAND_SIZE = 4


def split_into_sub_bands(bands: List[int], size: int = SUB_BAND_SIZE) -> List[List[int]]:
    """Splits sorted bands into round(n/size) contiguous groups of near-equal size (~size each)."""
    n = len(bands)
    if n == 0:
        return []
    n_groups = max(1, int(round(n / float(size))))
    groups, start = [], 0
    for g in range(n_groups):
        stop = start + (n - start) // (n_groups - g)
        groups.append(bands[start:stop])
        start = stop
    return [grp for grp in groups if grp]

def get_channel_wavelength(detector: str, channel_idx: int) -> Tuple[float, float]:
    """
    Returns (lambda_central_um, delta_lambda_um) for channel_idx in 1..17.
    """
    spec = DETECTOR_SPECS.get(detector, DETECTOR_SPECS["D1"])
    lmin, lmax = spec["lmin"], spec["lmax"]
    step = (lmax - lmin) / 17.0
    lc = lmin + (channel_idx - 0.5) * step
    return round(lc, 4), round(step, 4)

def register_shot(
    image: List[List[Optional[float]]],
    variance: Optional[List[List[float]]],
    shift_x: float,
    shift_y: float,
) -> Tuple[List[List[Optional[float]]], Optional[List[List[Optional[float]]]]]:
    """
    Level 0: align one shot onto the visit's common pixel grid.

    A shot whose pointing is offset by (shift_x, shift_y) pixels shows a sky source at
    (x + shift_x, y + shift_y). Resampling out(x, y) = in(x + shift_x, y + shift_y) with
    bilinear interpolation puts every shot on the same grid before co-adding, so a star's
    light falls in the same pixels in every visit stack.

    Masked (None) neighbours are skipped and the weights renormalised; pixels with no
    valid neighbours (or that fall off the image) become None.
    Variance is propagated as sum(w * var), which keeps aperture-sum errors right
    (interpolation correlates neighbouring pixels, so per-pixel sum(w^2 * var) would
    understate the noise of any sum over several pixels).
    """
    height = len(image)
    width = len(image[0]) if height else 0
    if abs(shift_x) < 1e-9 and abs(shift_y) < 1e-9:
        return image, variance

    # The shift is the same for every pixel, so the four bilinear weights are constants.
    ix, iy = int(math.floor(shift_x)), int(math.floor(shift_y))
    fx, fy = shift_x - ix, shift_y - iy
    taps = [
        (iy, ix, (1.0 - fx) * (1.0 - fy)),
        (iy, ix + 1, fx * (1.0 - fy)),
        (iy + 1, ix, (1.0 - fx) * fy),
        (iy + 1, ix + 1, fx * fy),
    ]
    taps = [t for t in taps if t[2] > 0.0]
    nan_free = all(
        v is not None and not (isinstance(v, float) and math.isnan(v)) for row in image for v in row
    )

    out: List[List[Optional[float]]] = []
    out_var: Optional[List[List[Optional[float]]]] = [] if variance is not None else None
    for y in range(height):
        rows = [(image[y + dy] if 0 <= y + dy < height else None, dx, w) for dy, dx, w in taps]
        vrows = (
            [(variance[y + dy] if 0 <= y + dy < height else None) for dy, _, _ in taps]
            if variance is not None else None
        )
        o_row: List[Optional[float]] = [None] * width
        v_row: List[Optional[float]] = [None] * width
        for x in range(width):
            acc = acc_var = w_sum = 0.0
            for k, (row, dx, w) in enumerate(rows):
                xx = x + dx
                if row is None or not (0 <= xx < width):
                    continue
                val = row[xx]
                if not nan_free and (val is None or (isinstance(val, float) and math.isnan(val))):
                    continue
                acc += w * val
                if vrows is not None:
                    acc_var += w * vrows[k][xx]
                w_sum += w
            if w_sum > 0.5:  # need at least half the interpolation weight to be real data
                o_row[x] = acc / w_sum
                v_row[x] = acc_var / w_sum
        out.append(o_row)
        if out_var is not None:
            out_var.append(v_row)
    return out, out_var


def fill_missing_bands(
    vals: List[float], wts: List[float]
) -> Optional[Tuple[List[float], List[float], bool]]:
    """
    One pixel, one value per band (in band order) with its Level-1 weight (0 = no data).
    Bands with no data are interpolated from the nearest valid bands below and above, so
    every band keeps its equal vote. Returns (vals, wts, was_filled) or None if no band
    has data.
    """
    valid = [i for i, w in enumerate(wts) if w > 0.0]
    if not valid:
        return None
    if len(valid) == len(wts):
        return vals, wts, False
    vals, wts = list(vals), list(wts)
    for i in range(len(wts)):
        if wts[i] > 0.0:
            continue
        lo = max((j for j in valid if j < i), default=None)
        hi = min((j for j in valid if j > i), default=None)
        if lo is not None and hi is not None:
            f = (i - lo) / (hi - lo)
            vals[i] = vals[lo] * (1.0 - f) + vals[hi] * f
            wts[i] = 1.0 / ((1.0 - f) / wts[lo] + f / wts[hi])
        else:
            j = lo if lo is not None else hi
            vals[i] = vals[j]
            wts[i] = wts[j]
    return vals, wts, True


def label_exposure_spectral_channel(detector: str, target_wavelength_um: float) -> int:
    """
    Step 1: Spectral Labelling
    Maps target central wavelength to discrete channel index b in {1..17}.
    """
    spec = DETECTOR_SPECS.get(detector, DETECTOR_SPECS["D1"])
    lmin, lmax = spec["lmin"], spec["lmax"]
    if target_wavelength_um <= lmin:
        return 1
    if target_wavelength_um >= lmax:
        return 17
    channel = 1 + int(((target_wavelength_um - lmin) / (lmax - lmin)) * 17.0)
    return max(1, min(17, channel))

def perform_band_balanced_stacking(
    visits_exposures: List[Dict[str, Any]],
    detector: str,
    use_cleaned: bool = True,
    register: bool = True,
) -> Dict[str, Any]:
    """
    Akhilesh's 5-Step Hierarchical Band-Balanced Stacking:
    
    1. Per-Exposure Spectral Labelling (channels 1..17)
    2. Two-Level Hierarchical Stacking:
       Level 1: Inverse-variance co-add within each channel b
       Level 2: Equal-weight mean across all channels in C_shared
    3. Cross-Visit Shared-Channel Intersection C_shared = Intersect_v { b : E_v,d,b != empty }
    4. Sub-band & matched-band aggregation
    5. Photometric reliability audit and gate (< 10 bands -> warning)

    Input images: each exposure's `cleaned_image` (flags masked to None, ZODI and
    background removed, see cleaning.clean_frame_data) is used when present and
    `use_cleaned` is True; otherwise the raw `image`.

    Alignment (Level 0): when `register` is True, each shot is first resampled onto
    the visit's common grid using its pointing offset (`dither_x`, `dither_y` in pixels;
    for real data this comes from each shot's WCS). Without this, the ~0.5 px pointing
    jitter between shots smears stars differently in each visit, which leaves a ~1%
    fake brightness change even after band balancing.

    Masked pixels: a masked pixel simply drops out of its band's Level-1 average.
    If EVERY shot of a shared band is masked at a pixel, that band's value there is
    interpolated from the nearest valid shared bands, so the equal band mix is kept
    (counted in `n_band_filled_pixels`). Only if no band is valid is the pixel None.
    """
    n_visits = len(visits_exposures)
    if n_visits == 0:
        return {"status": "error", "message": "No visits provided"}

    # Track channel occupancy per visit
    visit_channel_sets = []
    visit_channel_cubes = []

    for v_idx, visit in enumerate(visits_exposures):
        exps = visit.get("exposures", [])
        channels_present = set()
        channel_buckets: Dict[int, List[Dict[str, Any]]] = {b: [] for b in range(1, 18)}
        
        for exp in exps:
            # Step 1: every shot carries lambda_at_target and band (manifest fields)
            lam = exp.get("lambda_at_target", exp.get("wavelength_um"))
            ch = exp.get("channel")
            if ch is None:
                ch = label_exposure_spectral_channel(detector, lam if lam is not None else DETECTOR_SPECS[detector]["lmin"])
                exp["channel"] = ch
            exp["band"] = ch
            if lam is not None:
                exp["lambda_at_target"] = lam
            channels_present.add(ch)
            channel_buckets[ch].append(exp)
            
        visit_channel_sets.append(channels_present)
        visit_channel_cubes.append(channel_buckets)

    # Step 3: bands shared by every visit. All visits are stacked from exactly these
    # bands so the colour mix is identical. There is no fallback to "all bands": if few
    # or no bands are shared, the comparison is marked unreliable instead (PDF Step 3).
    c_shared = set(range(1, 18))
    for c_set in visit_channel_sets:
        c_shared = c_shared.intersection(c_set)
    c_shared_sorted = sorted(c_shared)
    n_shared = len(c_shared_sorted)
    no_shared_bands = n_shared == 0

    # Effective wavelength of the shared mix (average of the band centres that went in)
    wavelengths = [get_channel_wavelength(detector, b)[0] for b in c_shared_sorted]
    eff_wavelength = sum(wavelengths) / n_shared if n_shared else None

    # Reliability gate: fewer than MIN_SHARED_BANDS shared bands -> not comparable
    reliable = n_shared >= MIN_SHARED_BANDS
    reliability_warning = None
    if no_shared_bands:
        reliability_warning = (
            "NOT COMPARABLE: the visits share no spectral bands, so each visit is stacked from "
            "its own bands and brightness differences between visits may be colour effects."
        )
    elif not reliable:
        reliability_warning = (
            f"UNRELIABLE: only {n_shared} of 17 bands are shared by every visit "
            f"(need {MIN_SHARED_BANDS}). Brightness changes between visits may be colour effects."
        )

    # Perform Two-Level Stacking for each visit
    visit_stacks = []
    
    for v_idx, visit in enumerate(visits_exposures):
        channel_buckets = visit_channel_cubes[v_idx]
        # Normally the shared bands; with no shared bands at all each visit uses its own
        # (and the result is flagged not comparable above).
        bands_used = c_shared_sorted if not no_shared_bands else sorted(visit_channel_sets[v_idx])
        n_bands_used = len(bands_used)
        
        # Get frame dimensions from first available exposure
        sample_frame = visit["exposures"][0]["image"]
        height = len(sample_frame)
        width = len(sample_frame[0])
        
        # Level 1: Inverse-variance co-add for each channel in C_shared
        level1_channel_images: Dict[int, List[List[float]]] = {}
        level1_channel_weights: Dict[int, List[List[float]]] = {}
        
        for ch in bands_used:
            bucket_exps = channel_buckets.get(ch, [])

            ch_sum = [[0.0 for _ in range(width)] for _ in range(height)]
            ch_wt_sum = [[0.0 for _ in range(width)] for _ in range(height)]
            
            for exp in bucket_exps:
                img = exp.get("cleaned_image") if use_cleaned else None
                if img is None:
                    img = exp["image"]
                var = exp.get("variance")
                if register:
                    cache_key = "registered_cleaned" if img is exp.get("cleaned_image") else "registered_raw"
                    if cache_key not in exp:
                        exp[cache_key] = register_shot(
                            img, var, float(exp.get("dither_x", 0.0)), float(exp.get("dither_y", 0.0))
                        )
                    img, var = exp[cache_key]
                for y in range(height):
                    for x in range(width):
                        val = img[y][x]
                        if val is None or math.isnan(val):
                            continue
                        # Inverse variance weighting w = 1 / sigma^2
                        v_pix = var[y][x] if var else None
                        wt = (1.0 / v_pix) if (v_pix is not None and v_pix > 0.0) else 1.0
                        ch_sum[y][x] += val * wt
                        ch_wt_sum[y][x] += wt
                        
            # Normalize Level 1 channel image
            l1_img = [[0.0 for _ in range(width)] for _ in range(height)]
            l1_wt = [[0.0 for _ in range(width)] for _ in range(height)]
            for y in range(height):
                for x in range(width):
                    if ch_wt_sum[y][x] > 0.0:
                        l1_img[y][x] = ch_sum[y][x] / ch_wt_sum[y][x]
                        l1_wt[y][x] = ch_wt_sum[y][x]
                    else:
                        l1_img[y][x] = 0.0
                        l1_wt[y][x] = 0.0
            level1_channel_images[ch] = l1_img
            level1_channel_weights[ch] = l1_wt

        # Level 2: Across-Channel Equal-Weight Mean
        # One equal vote per channel, regardless of how many raw exposures were in each channel!
        level2_stack = [[0.0 for _ in range(width)] for _ in range(height)]
        level2_variance = [[0.0 for _ in range(width)] for _ in range(height)]
        inv_n_shared = 1.0 / max(1, n_bands_used)
        
        # Masked pixels: if every shot of a band is masked at a pixel, fill that band's
        # value there by interpolating between the nearest valid shared bands below and
        # above (spectra are smooth across neighbouring bands). This keeps one equal vote
        # per band, which the PDF's nanmean-over-remaining-bands would not.
        n_band_filled_pixels = 0
        n_incomplete_pixels = 0

        for y in range(height):
            for x in range(width):
                filled = fill_missing_bands(
                    [level1_channel_images[ch][y][x] for ch in bands_used],
                    [level1_channel_weights[ch][y][x] for ch in bands_used],
                )
                if filled is None:
                    level2_stack[y][x] = None
                    level2_variance[y][x] = None
                    n_incomplete_pixels += 1
                    continue
                vals, wts, was_filled = filled
                if was_filled:
                    n_band_filled_pixels += 1
                level2_stack[y][x] = sum(vals) * inv_n_shared
                level2_variance[y][x] = sum(1.0 / w for w in wts) * (inv_n_shared ** 2)

        # Step 4: sub-band stacks, groups of ~4 neighbouring bands (equal vote per band inside)
        sub_bands = []
        for b_idx, bin_channels in enumerate(split_into_sub_bands(bands_used)):
            if bin_channels:
                sub_img = [[0.0 for _ in range(width)] for _ in range(height)]
                for y in range(height):
                    for x in range(width):
                        filled = fill_missing_bands(
                            [level1_channel_images[ch][y][x] for ch in bin_channels],
                            [level1_channel_weights[ch][y][x] for ch in bin_channels],
                        )
                        sub_img[y][x] = None if filled is None else sum(filled[0]) / len(bin_channels)
                sub_wl = [get_channel_wavelength(detector, b)[0] for b in bin_channels]
                sub_bands.append({
                    "sub_band_bin": b_idx,
                    "channels": bin_channels,
                    "lambda_eff_um": round(sum(sub_wl) / len(sub_wl), 4),
                    "image": sub_img
                })

        # Manifest fields for this stack (agreed with Tracks 3 and 4)
        n_shots_per_band = {b: len(channel_buckets.get(b, [])) for b in bands_used}
        bands_present = sorted(visit_channel_sets[v_idx])
        lam_eff = (
            sum(get_channel_wavelength(detector, b)[0] for b in bands_used) / n_bands_used
            if n_bands_used else None
        )
        # Same mix, but from where the target actually landed in each shot (equal weight per
        # band, averaged within band): shows any within-band offset, e.g. surveys 3-4.
        measured = []
        for b in bands_used:
            lams = [e["lambda_at_target"] for e in channel_buckets.get(b, []) if e.get("lambda_at_target") is not None]
            if lams:
                measured.append(sum(lams) / len(lams))
        lam_eff_measured = sum(measured) / len(measured) if len(measured) == n_bands_used and measured else None

        visit_stacks.append({
            "visit_id": visit["visit_id"],
            "detector": detector,
            "bands_used": list(bands_used),
            "n_bands": n_bands_used,
            "n_shots_per_band": n_shots_per_band,
            "lambda_eff": round(lam_eff, 4) if lam_eff is not None else None,
            "lambda_eff_measured": round(lam_eff_measured, 4) if lam_eff_measured is not None else None,
            "comparable": reliable,
            "bands_present": bands_present,
            "n_bands_present": len(bands_present),
            "n_shots": len(visit.get("exposures", [])),
            "n_shots_used": sum(n_shots_per_band.values()),
            "visit_index": visit["visit_index"],
            "mjd_mid": visit["mjd_mid"],
            "date_utc": visit["date_utc"],
            "survey_pass": visit["survey_pass"],
            "stacked_image": level2_stack,
            "stacked_variance": level2_variance,
            "n_band_filled_pixels": n_band_filled_pixels,
            "n_masked_pixels": n_incomplete_pixels,
            "registered_shots": register,
            "used_cleaned_images": use_cleaned and any(
                e.get("cleaned_image") is not None for e in visit["exposures"]
            ),
            "sub_bands": sub_bands
        })

    return {
        "status": "success",
        "detector": detector,
        "n_shared_channels": n_shared,
        "shared_channels": c_shared_sorted,
        "effective_wavelength_um": round(eff_wavelength, 4) if eff_wavelength is not None else None,
        "comparable": reliable,
        "min_shared_bands": MIN_SHARED_BANDS,
        "reliability_warning": reliability_warning,
        "visit_stacks": visit_stacks
    }
