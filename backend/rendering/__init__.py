"""
WCS Transformations, Idea 1 Relative Positioning, Idea 2 Spectral Superposition,
Global Asinh Display Stretching, and Deterministic GIF/MP4 Compilation
"""

from .wcs_engine import WCSEngine
from .colorization import (
    colorize_detector_image,
    composite_multiband_false_color,
    ir_to_visible_wavelength_log,
    visible_nm_to_cie_rgb,
    lupton_asinh_color_compression,
)
from .stretching import (
    calculate_percentiles,
    apply_global_detector_asinh_stretch,
    apply_symmetric_difference_stretch,
)
from .gif_encoder import burn_telemetry_hud, encode_gif_stream

__all__ = [
    "WCSEngine",
    "colorize_detector_image",
    "composite_multiband_false_color",
    "ir_to_visible_wavelength_log",
    "visible_nm_to_cie_rgb",
    "lupton_asinh_color_compression",
    "calculate_percentiles",
    "apply_global_detector_asinh_stretch",
    "apply_symmetric_difference_stretch",
    "burn_telemetry_hud",
    "encode_gif_stream",
]
