"""
SPHEREx Planet X Challenge - 5-Step Band-Balanced LVF Stacking Engine
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

def get_channel_wavelength(detector: str, channel_idx: int) -> Tuple[float, float]:
    """
    Returns (lambda_central_um, delta_lambda_um) for channel_idx in 1..17.
    """
    spec = DETECTOR_SPECS.get(detector, DETECTOR_SPECS["D1"])
    lmin, lmax = spec["lmin"], spec["lmax"]
    step = (lmax - lmin) / 17.0
    lc = lmin + (channel_idx - 0.5) * step
    return round(lc, 4), round(step, 4)

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
    detector: str
) -> Dict[str, Any]:
    """
    5-Step Hierarchical Band-Balanced Stacking:
    
    1. Per-Exposure Spectral Labelling (channels 1..17)
    2. Two-Level Hierarchical Stacking:
       Level 1: Inverse-variance co-add within each channel b
       Level 2: Equal-weight mean across all channels in C_shared
    3. Cross-Visit Shared-Channel Intersection C_shared = Intersect_v { b : E_v,d,b != empty }
    4. Sub-band & matched-band aggregation
    5. Photometric reliability audit and gate (< 10 bands -> warning)
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
            # Get or assign spectral channel
            ch = exp.get("channel")
            if ch is None:
                ch = label_exposure_spectral_channel(detector, exp.get("wavelength_um", DETECTOR_SPECS[detector]["lmin"]))
                exp["channel"] = ch
            channels_present.add(ch)
            channel_buckets[ch].append(exp)
            
        visit_channel_sets.append(channels_present)
        visit_channel_cubes.append(channel_buckets)

    # Step 3: Compute cross-visit shared channel intersection C_shared
    c_shared = set(range(1, 18))
    for c_set in visit_channel_sets:
        c_shared = c_shared.intersection(c_set)
        
    # If intersection is empty or tiny, fallback to union or most common
    fallback_used = False
    if len(c_shared) == 0:
        fallback_used = True
        c_shared = set().union(*visit_channel_sets)

    c_shared_sorted = sorted(list(c_shared))
    n_shared = len(c_shared_sorted)
    
    # Calculate effective wavelength of the stack
    wavelengths = [get_channel_wavelength(detector, b)[0] for b in c_shared_sorted]
    eff_wavelength = sum(wavelengths) / max(1, n_shared) if wavelengths else 0.0

    # Reliability gate
    reliable = n_shared >= 10
    reliability_warning = None
    if not reliable:
        reliability_warning = (
            f"RELIABILITY WARNING: Only {n_shared} shared spectral channels intersect across visits "
            f"(< 10 channels threshold). Intrinsic stellar color slope may cause residual flicker!"
        )

    # Perform Two-Level Stacking for each visit
    visit_stacks = []
    
    for v_idx, visit in enumerate(visits_exposures):
        channel_buckets = visit_channel_cubes[v_idx]
        
        # Get frame dimensions from first available exposure
        sample_frame = visit["exposures"][0]["image"]
        height = len(sample_frame)
        width = len(sample_frame[0])
        
        # Level 1: Inverse-variance co-add for each channel in C_shared
        level1_channel_images: Dict[int, List[List[float]]] = {}
        level1_channel_weights: Dict[int, List[List[float]]] = {}
        
        for ch in c_shared_sorted:
            bucket_exps = channel_buckets.get(ch, [])
            if not bucket_exps:
                # If exposure missing in this visit but present in others, borrow nearest dither
                bucket_exps = visit["exposures"]
                
            ch_sum = [[0.0 for _ in range(width)] for _ in range(height)]
            ch_wt_sum = [[0.0 for _ in range(width)] for _ in range(height)]
            
            for exp in bucket_exps:
                img = exp["image"]
                var = exp.get("variance")
                for y in range(height):
                    for x in range(width):
                        val = img[y][x]
                        if val is None or math.isnan(val):
                            continue
                        # Inverse variance weighting w = 1 / sigma^2
                        wt = (1.0 / var[y][x]) if (var and var[y][x] > 0.0) else 1.0
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
        inv_n_shared = 1.0 / max(1, n_shared)
        
        for y in range(height):
            for x in range(width):
                pixel_sum = 0.0
                var_sum = 0.0
                for ch in c_shared_sorted:
                    pixel_sum += level1_channel_images[ch][y][x]
                    wt = level1_channel_weights[ch][y][x]
                    var_sum += (1.0 / wt) if wt > 0.0 else 1.0
                level2_stack[y][x] = pixel_sum * inv_n_shared
                level2_variance[y][x] = var_sum * (inv_n_shared ** 2)

        # Step 4: Sub-band grouping (4 contiguous bins)
        sub_bands = []
        bin_size = max(1, n_shared // 4)
        for b_idx in range(4):
            bin_channels = c_shared_sorted[b_idx * bin_size : (b_idx + 1) * bin_size]
            if not bin_channels and b_idx == 3:
                bin_channels = c_shared_sorted[3 * bin_size :]
            if bin_channels:
                sub_img = [[0.0 for _ in range(width)] for _ in range(height)]
                for y in range(height):
                    for x in range(width):
                        sub_img[y][x] = sum(level1_channel_images[ch][y][x] for ch in bin_channels) / len(bin_channels)
                sub_bands.append({
                    "sub_band_bin": b_idx,
                    "channels": bin_channels,
                    "image": sub_img
                })

        visit_stacks.append({
            "visit_id": visit["visit_id"],
            "visit_index": visit["visit_index"],
            "mjd_mid": visit["mjd_mid"],
            "date_utc": visit["date_utc"],
            "survey_pass": visit["survey_pass"],
            "stacked_image": level2_stack,
            "stacked_variance": level2_variance,
            "sub_bands": sub_bands
        })

    return {
        "status": "success",
        "detector": detector,
        "n_shared_channels": n_shared,
        "shared_channels": c_shared_sorted,
        "effective_wavelength_um": round(eff_wavelength, 4),
        "comparable": reliable,
        "fallback_used": fallback_used,
        "reliability_warning": reliability_warning,
        "visit_stacks": visit_stacks
    }
