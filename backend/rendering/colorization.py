"""
SPHEREx Planet X Challenge - Idea 2: Infrared-to-Visible Spectral Superposition Engine
Bijections near-IR light (0.744 - 5.002 um) to human visible hues (380 - 750 nm) with Lupton (2004) asinh color compression.
"""

from typing import List, Dict, Any, Tuple
import math

# SPHEREx IR Wavelength Boundaries
LAMBDA_IR_MIN = 0.744
LAMBDA_IR_MAX = 5.002

def ir_to_visible_wavelength_log(lambda_ir_um: float) -> float:
    """
    Step 1: Constant-Resolving-Power Logarithmic Superposition Bijection
    Phi: [0.744 um, 5.002 um] -> [380 nm, 750 nm]
    lambda_vis = 380 + 370 * ln(lambda_ir / 0.744) / ln(5.002 / 0.744)
    """
    l_ir = max(LAMBDA_IR_MIN, min(LAMBDA_IR_MAX, lambda_ir_um))
    ratio = math.log(l_ir / LAMBDA_IR_MIN) / math.log(LAMBDA_IR_MAX / LAMBDA_IR_MIN)
    lambda_vis_nm = 380.0 + 370.0 * ratio
    return round(lambda_vis_nm, 2)

def visible_nm_to_cie_rgb(lambda_nm: float) -> Tuple[float, float, float]:
    """
    Approximates standard CIE 1931 color matching function projection to linear RGB.
    Produces physical rainbow spectrum across 380 - 750 nm.
    """
    w = max(380.0, min(750.0, lambda_nm))
    r, g, b = 0.0, 0.0, 0.0

    if 380.0 <= w < 440.0:
        r = -(w - 440.0) / (440.0 - 380.0)
        g = 0.0
        b = 1.0
    elif 440.0 <= w < 490.0:
        r = 0.0
        g = (w - 440.0) / (490.0 - 440.0)
        b = 1.0
    elif 490.0 <= w < 510.0:
        r = 0.0
        g = 1.0
        b = -(w - 510.0) / (510.0 - 490.0)
    elif 510.0 <= w < 580.0:
        r = (w - 510.0) / (580.0 - 510.0)
        g = 1.0
        b = 0.0
    elif 580.0 <= w < 645.0:
        r = 1.0
        g = -(w - 645.0) / (645.0 - 580.0)
        b = 0.0
    elif 645.0 <= w <= 750.0:
        r = 1.0
        g = 0.0
        b = 0.0

    # Vision intensity falloff near human limits (380-420 nm & 700-750 nm)
    factor = 1.0
    if 380.0 <= w < 420.0:
        factor = 0.3 + 0.7 * (w - 380.0) / (420.0 - 380.0)
    elif 700.0 < w <= 750.0:
        factor = 0.3 + 0.7 * (750.0 - w) / (750.0 - 700.0)

    return r * factor, g * factor, b * factor

# Precomputed RGB weights for SPHEREx 6 detectors based on spectral superposition
DETECTOR_SUPERPOSITION_WEIGHTS = {
    # D1: 0.744 - 1.116 um -> 380 - 455 nm -> Violet to Royal Blue
    "D1": (0.35, 0.05, 0.95),
    # D2: 1.099 - 1.651 um -> 452 - 531 nm -> Blue to Cyan
    "D2": (0.05, 0.75, 0.90),
    # D3: 1.636 - 2.421 um -> 528 - 604 nm -> Cyan to Green
    "D3": (0.15, 0.95, 0.20),
    # D4: 2.423 - 3.822 um -> 604 - 685 nm -> Green to Orange
    "D4": (0.95, 0.60, 0.05),
    # D5: 3.809 - 4.420 um -> 684 - 717 nm -> Orange to Deep Red
    "D5": (0.95, 0.15, 0.05),
    # D6: 4.412 - 5.002 um -> 717 - 750 nm -> Far-IR Deep Ruby Red
    "D6": (0.85, 0.00, 0.25)
}

def lupton_asinh_color_compression(
    r_lin: float,
    g_lin: float,
    b_lin: float,
    Q: float = 8.0,
    stretch_a: float = 0.05
) -> Tuple[int, int, int]:
    """
    Step 4 & 5: Lupton (2004) Chromaticity-Preserving Asinh Compression + sRGB Companding.
    Preserves exact astrophysical color ratios (hue) without saturating star cores to plain white!
    """
    # Clip negative background noise to zero
    r = max(0.0, r_lin)
    g = max(0.0, g_lin)
    b = max(0.0, b_lin)
    
    # Total intensity
    intensity = (r + g + b) / 3.0
    if intensity <= 1e-9:
        return 0, 0, 0
        
    # Asinh intensity scaling factor
    # f(I) = asinh(I * Q) / asinh(Q) / I
    f_int = math.asinh(intensity * Q) / (math.asinh(Q) * intensity)
    
    r_scaled = r * f_int
    g_scaled = g * f_int
    b_scaled = b * f_int
    
    # IEC 61966-2-1 sRGB gamma companding
    def srgb_gamma(c: float) -> int:
        c_clamped = min(1.0, max(0.0, c))
        if c_clamped <= 0.0031308:
            val = 12.92 * c_clamped
        else:
            val = 1.055 * (c_clamped ** (1.0 / 2.4)) - 0.055
        return int(round(val * 255.0))
        
    return srgb_gamma(r_scaled), srgb_gamma(g_scaled), srgb_gamma(b_scaled)

def colorize_detector_image(
    image: List[List[float]],
    detector: str,
    vmin: float = 0.0,
    vmax: float = 1.0
) -> List[List[Tuple[int, int, int]]]:
    """
    Applies Idea 2: Infrared-to-Visible Spectral Superposition to a single detector frame.
    Color is uniquely mapped to that detector's exact physical infrared bandpass!
    """
    height = len(image)
    width = len(image[0])
    rw, gw, bw = DETECTOR_SUPERPOSITION_WEIGHTS.get(detector, (1.0, 1.0, 1.0))
    
    dv = max(1e-6, vmax - vmin)
    rgb_grid = []
    
    for y in range(height):
        row = []
        for x in range(width):
            val = image[y][x]
            if val is None or math.isnan(val):
                row.append((0, 0, 0))
                continue
                
            norm = (val - vmin) / dv
            r_lin = norm * rw
            g_lin = norm * gw
            b_lin = norm * bw
            
            rgb = lupton_asinh_color_compression(r_lin, g_lin, b_lin)
            row.append(rgb)
        rgb_grid.append(row)
        
    return rgb_grid

def composite_multiband_false_color(
    d_blue_img: List[List[float]],   # e.g. D1 or D2 (Near-IR 0.8 - 1.5 um)
    d_green_img: List[List[float]],  # e.g. D3 or D4 (Mid-IR 2.0 - 3.5 um)
    d_red_img: List[List[float]],    # e.g. D5 or D6 (Far-IR 4.0 - 5.0 um)
    vmin: float = 0.0,
    vmax: float = 1.0
) -> List[List[Tuple[int, int, int]]]:
    """
    Synthesizes full multi-band 3-channel false-color infrared image
    combining blue, green, and red infrared wavelength channels with Lupton asinh companding.
    """
    height = len(d_blue_img)
    width = len(d_blue_img[0])
    dv = max(1e-6, vmax - vmin)
    
    rgb_grid = []
    for y in range(height):
        row = []
        for x in range(width):
            b_val = max(0.0, (d_blue_img[y][x] - vmin) / dv)
            g_val = max(0.0, (d_green_img[y][x] - vmin) / dv)
            r_val = max(0.0, (d_red_img[y][x] - vmin) / dv)
            
            rgb = lupton_asinh_color_compression(r_val, g_val, b_val)
            row.append(rgb)
        rgb_grid.append(row)
        
    return rgb_grid
