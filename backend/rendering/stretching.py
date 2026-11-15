"""
SPHEREx Planet X Challenge - Global Detector-Locked Asinh Stretch & Symmetric Diff Scaling
Eliminates per-frame auto-scaling flicker across the temporal sequence.
"""

from typing import List, Dict, Any, Tuple
import math

def calculate_percentiles(all_pixel_values: List[float], p_low: float = 0.5, p_high: float = 99.5) -> Tuple[float, float]:
    """Calculates robust percentile cutoffs across an entire multi-visit sequence."""
    clean = [p for p in all_pixel_values if p is not None and not math.isnan(p)]
    if not clean:
        return 0.0, 1.0
    clean.sort()
    n = len(clean)
    idx_low = int((p_low / 100.0) * n)
    idx_high = min(n - 1, int((p_high / 100.0) * n))
    return clean[idx_low], clean[idx_high]

def apply_global_detector_asinh_stretch(
    image: List[List[float]],
    vmin: float,
    vmax: float,
    a: float = 0.05
) -> List[List[float]]:
    """
    Applies global detector-locked asinh stretch:
    u = (I - vmin) / (vmax - vmin)
    S = asinh(u / a) / asinh(1 / a)
    """
    dv = max(1e-6, vmax - vmin)
    norm_factor = 1.0 / math.asinh(1.0 / a)
    height = len(image)
    width = len(image[0])
    
    stretched = [[0.0 for _ in range(width)] for _ in range(height)]
    for y in range(height):
        for x in range(width):
            val = image[y][x]
            if val is None or math.isnan(val):
                stretched[y][x] = 0.0
                continue
            u = max(0.0, min(1.0, (val - vmin) / dv))
            stretched[y][x] = math.asinh(u / a) * norm_factor
            
    return stretched

def apply_symmetric_difference_stretch(
    diff_image: List[List[float]],
    vmax_abs: float = None
) -> Tuple[List[List[Tuple[int, int, int]]], float]:
    """
    Applies symmetric zero-centered difference color mapping [-Vmax, +Vmax].
    Zero difference (static stars) = neutral dark gray (40, 40, 40).
    Negative dipoles (disappeared from previous epoch) = deep electric cyan.
    Positive dipoles (appeared at new epoch) = blazing orange/red.
    """
    height = len(diff_image)
    width = len(diff_image[0])
    
    if vmax_abs is None:
        abs_vals = []
        for y in range(height):
            for x in range(width):
                val = diff_image[y][x]
                if val is not None and not math.isnan(val):
                    abs_vals.append(abs(val))
        if abs_vals:
            abs_vals.sort()
            vmax_abs = abs_vals[int(0.995 * len(abs_vals))]
        else:
            vmax_abs = 1.0
            
    vmax_abs = max(1e-4, vmax_abs)
    
    rgb_grid = []
    for y in range(height):
        row = []
        for x in range(width):
            val = diff_image[y][x]
            if val is None or math.isnan(val):
                row.append((40, 40, 40))
                continue
            # Scaled [-1.0, +1.0]
            norm = max(-1.0, min(1.0, val / vmax_abs))
            
            if norm >= 0.0:
                # Positive dipole: new object position -> Orange/Red
                # Transitions from gray (40,40,40) to red (255, 60, 20)
                r = int(40 + (255 - 40) * norm)
                g = int(40 + (60 - 40) * norm)
                b = int(40 + (20 - 40) * (1.0 - norm))
            else:
                # Negative dipole: old object position -> Electric Cyan
                # Transitions from gray (40,40,40) to cyan (20, 180, 255)
                n = abs(norm)
                r = int(40 + (20 - 40) * n)
                g = int(40 + (180 - 40) * n)
                b = int(40 + (255 - 40) * n)
                
            row.append((r, g, b))
        rgb_grid.append(row)
        
    return rgb_grid, round(vmax_abs, 4)
