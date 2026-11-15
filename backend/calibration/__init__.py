"""
Data Calibration, Cleaning, 5-Step Stacking, and Flicker Audit
"""

from .cleaning import clean_frame_data, DEFAULT_MP_FLAGS
from .band_balancer import (
    perform_band_balanced_stacking,
    label_exposure_spectral_channel,
    DETECTOR_SPECS,
    get_channel_wavelength,
)
from .flicker_audit import (
    run_still_star_flicker_audit,
    compute_flicker_statistics,
)
from .differencing import (
    compute_difference_frames,
    compute_temporal_median_template,
    perform_shift_and_stack,
)

__all__ = [
    "clean_frame_data",
    "DEFAULT_MP_FLAGS",
    "perform_band_balanced_stacking",
    "label_exposure_spectral_channel",
    "DETECTOR_SPECS",
    "get_channel_wavelength",
    "run_still_star_flicker_audit",
    "compute_flicker_statistics",
    "compute_difference_frames",
    "compute_temporal_median_template",
    "perform_shift_and_stack",
]
