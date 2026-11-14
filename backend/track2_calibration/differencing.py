"""
SPHEREx Planet X Challenge - Temporal Median Templates, Difference Imaging & Shift-and-Stack
Isolates sub-pixel moving objects via negative-positive spatial dipoles & boosts SNR via digital tracking.
"""

from typing import List, Dict, Any, Tuple
import math

def compute_temporal_median_template(visit_images: List[List[List[float]]]) -> List[List[float]]:
    """
    Computes static template T_d(x,y) = median_{v=1..M} F_{v,d}(x,y).
    Moving objects vanish from the median template; stationary stars are preserved.
    """
    n_visits = len(visit_images)
    if n_visits == 0:
        return []
    height = len(visit_images[0])
    width = len(visit_images[0][0])
    
    template = [[0.0 for _ in range(width)] for _ in range(height)]
    
    for y in range(height):
        for x in range(width):
            vals = []
            for v in range(n_visits):
                pix = visit_images[v][y][x]
                if pix is not None and not math.isnan(pix):
                    vals.append(pix)
            if vals:
                vals.sort()
                template[y][x] = vals[len(vals) // 2]
            else:
                template[y][x] = 0.0
                
    return template

def compute_difference_frames(
    visit_stacks: List[Dict[str, Any]],
    template: List[List[float]] = None
) -> List[Dict[str, Any]]:
    """
    Computes D_{v,d}(x,y) = F_{v,d}(x,y) - T_d(x,y).
    Proper-motion movers appear as high-contrast negative-to-positive dipoles.
    """
    images = [v["stacked_image"] for v in visit_stacks]
    if template is None:
        template = compute_temporal_median_template(images)
        
    height = len(template)
    width = len(template[0])
    diff_stacks = []
    
    for v in visit_stacks:
        img = v["stacked_image"]
        diff_img = [[0.0 for _ in range(width)] for _ in range(height)]
        for y in range(height):
            for x in range(width):
                pix = img[y][x]
                # Masked (None) pixels stay masked in the difference image
                diff_img[y][x] = None if pix is None else pix - template[y][x]
                
        diff_stacks.append({
            "visit_id": v["visit_id"],
            "visit_index": v["visit_index"],
            "mjd_mid": v["mjd_mid"],
            "date_utc": v["date_utc"],
            "difference_image": diff_img
        })
        
    return diff_stacks

def perform_shift_and_stack(
    visit_stacks: List[Dict[str, Any]],
    velocity_px_per_visit: Tuple[float, float],
    ref_visit_idx: int = 0
) -> List[List[float]]:
    """
    Digital Shift-and-Stack:
    Shifts each visit v by -velocity * (v - ref_v) prior to co-addition.
    Moving object integrates coherently, boosting SNR by sqrt(N_visits) while smearing stationary stars.
    """
    n_visits = len(visit_stacks)
    if n_visits == 0:
        return []
    height = len(visit_stacks[0]["stacked_image"])
    width = len(visit_stacks[0]["stacked_image"][0])
    
    shifted_sum = [[0.0 for _ in range(width)] for _ in range(height)]
    shifted_count = [[0 for _ in range(width)] for _ in range(height)]
    
    vx, vy = velocity_px_per_visit
    
    for v_idx, v in enumerate(visit_stacks):
        dt = v_idx - ref_visit_idx
        dx = -vx * dt
        dy = -vy * dt
        img = v["stacked_image"]
        
        for y in range(height):
            for x in range(width):
                # Integer + fractional sampling
                src_x = int(round(x - dx))
                src_y = int(round(y - dy))
                if 0 <= src_x < width and 0 <= src_y < height:
                    pix = img[src_y][src_x]
                    if pix is None:
                        continue  # masked pixel: skip, other visits still contribute
                    shifted_sum[y][x] += pix
                    shifted_count[y][x] += 1
                    
    result = [[0.0 for _ in range(width)] for _ in range(height)]
    for y in range(height):
        for x in range(width):
            cnt = shifted_count[y][x]
            if cnt > 0:
                result[y][x] = shifted_sum[y][x] / cnt
                
    return result
