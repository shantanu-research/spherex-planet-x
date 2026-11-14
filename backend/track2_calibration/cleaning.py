"""
SPHEREx Planet X Challenge - Instrumental Cleaning & Dynamic Bitmasking
Dynamic MP_* flag bitmasking (preserving SOURCE) + ZODI subtraction + 3-sigma background pedestal removal.
"""

from typing import List, Dict, Any, Tuple
import math

# Default SPHEREx Level-2 MP_* flag bits from spherex_flag_bits.csv
DEFAULT_MP_FLAGS = {
    "MP_TRANSIENT": 1 << 0,
    "MP_OVERFLOW": 1 << 1,
    "MP_SUR_ERROR": 1 << 2,
    "MP_PHANTOM": 1 << 4,
    "MP_REFERENCE": 1 << 5,
    "MP_NONFUNC": 1 << 6,
    "MP_DICHROIC": 1 << 7,     # Critical for D3/D4 (>50% transmission drop)
    "MP_MISSING_DATA": 1 << 9,
    "MP_HOT": 1 << 10,
    "MP_COLD": 1 << 11,
    "MP_PERSIST": 1 << 17,
    "MP_SOURCE": 1 << 21      # PRESERVED: Benign cataloged real celestial source
}

def parse_header_flags(header: Dict[str, Any]) -> Dict[str, int]:
    """Dynamically parse MP_* flag bit values from FITS FLAGS header."""
    flag_map = {}
    for k, v in header.items():
        if k.startswith("MP_") and isinstance(v, int):
            flag_map[k] = 1 << v
    if not flag_map:
        return DEFAULT_MP_FLAGS.copy()
    return flag_map

def clean_frame_data(
    image: List[List[float]],
    flags: List[List[int]],
    variance: List[List[float]],
    zodi: List[List[float]],
    flag_map: Dict[str, int] = None
) -> Tuple[List[List[float]], List[List[float]], Dict[str, Any]]:
    """
    Cleans a 2D calibrated exposure:
    1. Dynamic MP_* masking: All hazards masked to None (NaN), MP_SOURCE preserved.
    2. Subtracts physical zodiacal light model pixel-by-pixel.
    3. Subtracts 3-sigma clipped residual spatial background pedestal.
    """
    if flag_map is None:
        flag_map = DEFAULT_MP_FLAGS

    # Compute hazard mask (all bits EXCEPT MP_SOURCE)
    hazard_bitmask = 0
    for name, bit in flag_map.items():
        if name != "MP_SOURCE":
            hazard_bitmask |= bit

    height = len(image)
    width = len(image[0]) if height > 0 else 0
    
    cleaned_image = [[0.0 for _ in range(width)] for _ in range(height)]
    weights = [[0.0 for _ in range(width)] for _ in range(height)]
    
    valid_pixels = []
    masked_count = 0
    
    for y in range(height):
        for x in range(width):
            flag_val = flags[y][x]
            # If hazard bit is set, mask pixel
            if (flag_val & hazard_bitmask) != 0:
                cleaned_image[y][x] = None
                weights[y][x] = 0.0
                masked_count += 1
                continue
                
            raw_val = image[y][x]
            zodi_val = zodi[y][x] if zodi else 0.0
            var_val = variance[y][x] if variance else 1.0
            
            # Zodi subtraction
            subtracted = raw_val - zodi_val
            cleaned_image[y][x] = subtracted
            valid_pixels.append(subtracted)
            
            if var_val > 0.0:
                weights[y][x] = 1.0 / var_val
            else:
                weights[y][x] = 1.0

    # 3-sigma clipped median background pedestal subtraction
    pedestal = 0.0
    if valid_pixels:
        valid_pixels.sort()
        n = len(valid_pixels)
        median_val = valid_pixels[n // 2]
        
        # Approximate std dev via interquartile range (IQR / 1.349)
        q25 = valid_pixels[int(0.25 * n)]
        q75 = valid_pixels[int(0.75 * n)]
        sigma = max(0.0001, (q75 - q25) / 1.349)
        
        # 3-sigma clip
        clipped = [p for p in valid_pixels if abs(p - median_val) <= 3.0 * sigma]
        if clipped:
            clipped.sort()
            pedestal = clipped[len(clipped) // 2]
            
        # Subtract residual background pedestal
        for y in range(height):
            for x in range(width):
                if cleaned_image[y][x] is not None:
                    cleaned_image[y][x] -= pedestal

    stats = {
        "total_pixels": height * width,
        "masked_pixels": masked_count,
        "masked_fraction_pct": round((masked_count / max(1, height * width)) * 100.0, 2),
        "zodi_subtracted": bool(zodi),
        "background_pedestal_mjy_sr": round(pedestal, 4)
    }

    return cleaned_image, weights, stats


def clean_visit_exposures(
    visits: List[Dict[str, Any]],
    flag_map: Dict[str, int] = None,
) -> Dict[str, Any]:
    """
    Runs clean_frame_data on every exposure of every visit, in place.

    Each exposure gains `cleaned_image` (hazard pixels = None, ZODI and background
    pedestal removed) and `cleaned_weight`. Band-balanced stacking then uses these.
    Returns a small summary (exposures cleaned, pixels masked).
    """
    n_exposures = 0
    n_masked = 0
    for visit in visits:
        for exp in visit.get("exposures", []):
            clean_img, clean_wt, stats = clean_frame_data(
                exp["image"], exp["flags"], exp.get("variance"), exp.get("zodi"), flag_map
            )
            exp["cleaned_image"] = clean_img
            exp["cleaned_weight"] = clean_wt
            n_exposures += 1
            n_masked += stats.get("masked_pixels", 0)
    return {"n_exposures_cleaned": n_exposures, "n_pixels_masked": n_masked}
