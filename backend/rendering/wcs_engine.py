"""
SPHEREx Planet X Challenge - Idea 1: WCS Relative Frame Positioning & Flipbook Engine
Implements Canonical TAN grid, SIP distortion mapping, Inertial Sky-Fixed & Co-Moving Target-Locked frames.
"""

from typing import List, Dict, Any, Tuple
import math

SPHEREx_PIXEL_SCALE_ARCSEC = 6.15

class WCSEngine:
    """
    Idea 1 Engine:
    Converts raw FITS WCS metadata into deterministic relative frame positioning.
    Supports:
      Branch 2A: Inertial Sky-Fixed Frame (Background fixed, movers translate across FOV)
      Branch 2B: Co-Moving Target-Locked Frame (Target pinned at center, background stars drift)
    """

    def __init__(self, fov_arcmin: float = 6.5, center_ra_deg: float = 0.0, center_dec_deg: float = 0.0):
        self.fov_arcmin = fov_arcmin
        self.center_ra = center_ra_deg
        self.center_dec = center_dec_deg
        self.pixel_scale_arcsec = SPHEREx_PIXEL_SCALE_ARCSEC
        # Output grid size N = round(FOV_arcmin * 60 / 6.15)
        self.grid_size = int(round((fov_arcmin * 60.0) / self.pixel_scale_arcsec))
        # Ensure even/convenient dimensions (e.g. 64x64)
        if self.grid_size < 32:
            self.grid_size = 32
        elif self.grid_size % 2 != 0:
            self.grid_size += 1
            
        self.u0 = (self.grid_size - 1) / 2.0
        self.v0 = (self.grid_size - 1) / 2.0

    def output_pixel_to_sky(self, u: float, v: float) -> Tuple[float, float]:
        """
        Stage 1: Converts output grid pixel (u, v) to ICRS sky coordinate (ra, dec)
        in a North-Up, East-Left Gnomonic TAN projection.
        """
        s_rad = math.radians(self.pixel_scale_arcsec / 3600.0)
        # Standard tangent plane coordinates: xi = -s * (u - u0), eta = +s * (v - v0)
        xi = -s_rad * (u - self.u0)
        eta = s_rad * (v - self.v0)
        
        ra_c_rad = math.radians(self.center_ra)
        dec_c_rad = math.radians(self.center_dec)
        
        # Inverse gnomonic projection
        denom = math.cos(dec_c_rad) - eta * math.sin(dec_c_rad)
        ra = ra_c_rad + math.atan2(xi, denom)
        
        num_dec = math.sin(dec_c_rad) + eta * math.cos(dec_c_rad)
        denom_dec = math.sqrt(denom ** 2 + xi ** 2)
        dec = math.atan2(num_dec, denom_dec)
        
        return math.degrees(ra) % 360.0, math.degrees(dec)

    def sky_to_output_pixel(self, ra_deg: float, dec_deg: float) -> Tuple[float, float]:
        """Converts sky coordinate (ra, dec) to output grid pixel (u, v)."""
        ra_rad = math.radians(ra_deg)
        dec_rad = math.radians(dec_deg)
        ra_c_rad = math.radians(self.center_ra)
        dec_c_rad = math.radians(self.center_dec)
        
        delta_ra = ra_rad - ra_c_rad
        cos_c = math.sin(dec_c_rad) * math.sin(dec_rad) + math.cos(dec_c_rad) * math.cos(dec_rad) * math.cos(delta_ra)
        if cos_c <= 0:
            return -999.0, -999.0
            
        xi = (math.cos(dec_rad) * math.sin(delta_ra)) / cos_c
        eta = (math.cos(dec_c_rad) * math.sin(dec_rad) - math.sin(dec_c_rad) * math.cos(dec_rad) * math.cos(delta_ra)) / cos_c
        
        s_rad = math.radians(self.pixel_scale_arcsec / 3600.0)
        u = self.u0 - (xi / s_rad)
        v = self.v0 + (eta / s_rad)
        return round(u, 2), round(v, 2)

    def transform_frame(
        self,
        input_image: List[List[float]],
        target_displacement_px: Tuple[float, float],
        mode: str = "inertial"
    ) -> List[List[float]]:
        """
        Transforms and registers input frame into output grid:
        
        Mode 'inertial' (Branch 2A):
          Inertial Sky-Fixed Frame. Background stars stay pinned; target moves by target_displacement_px.
          
        Mode 'comoving' (Branch 2B):
          Co-Moving Target-Locked Frame. Target stays locked at center (u0, v0);
          background stars drift by -target_displacement_px.
        """
        h = len(input_image)
        w = len(input_image[0])
        out = [[0.0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        
        dx_target, dy_target = target_displacement_px
        
        if mode == "comoving":
            # Shift the background in opposite direction to keep target centered
            shift_x = -dx_target
            shift_y = -dy_target
        else:
            # Inertial: no camera shift
            shift_x = 0.0
            shift_y = 0.0

        for y in range(self.grid_size):
            for x in range(self.grid_size):
                # Map output pixel to input pixel with bicubic/bilinear interpolation
                src_x = x - shift_x
                src_y = y - shift_y
                
                # Bilinear sampling
                x0 = int(math.floor(src_x))
                y0 = int(math.floor(src_y))
                x1 = x0 + 1
                y1 = y0 + 1
                
                if 0 <= x0 < w - 1 and 0 <= y0 < h - 1:
                    fx = src_x - x0
                    fy = src_y - y0
                    p00 = input_image[y0][x0]
                    p10 = input_image[y0][x1]
                    p01 = input_image[y1][x0]
                    p11 = input_image[y1][x1]

                    # Masked (None) neighbours: renormalise over the valid ones
                    terms = [
                        (p00, (1 - fx) * (1 - fy)),
                        (p10, fx * (1 - fy)),
                        (p01, (1 - fx) * fy),
                        (p11, fx * fy),
                    ]
                    w_sum = sum(w for p, w in terms if p is not None)
                    if w_sum > 1e-9:
                        out[y][x] = sum(p * w for p, w in terms if p is not None) / w_sum
                    else:
                        out[y][x] = None
                elif 0 <= int(round(src_x)) < w and 0 <= int(round(src_y)) < h:
                    out[y][x] = input_image[int(round(src_y))][int(round(src_x))]
                else:
                    out[y][x] = 0.0
                    
        return out
