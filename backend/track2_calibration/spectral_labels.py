"""
Track 2 Step 1: label every shot with its colour.

For a real SPHEREx Level-2 spectral image (multi-extension FITS with IMAGE, FLAGS,
VARIANCE, ZODI, PSF, WCS-WAVE), following the IRSA SPHEREx tutorials:

  1. Find the target's pixel with the sky WCS:      WCS(header).world_to_pixel(...)
  2. Read that pixel's wavelength from the second (spectral) WCS, which points at the
     WCS-WAVE lookup table:                         WCS(header, fobj=hdul, key="W")
     with SIP distortion switched off (sip = None), then pixel_to_world(x, y)
     -> (central wavelength, bandwidth) in um.
  3. Record which of the detector's 17 channels ("bands") that wavelength falls in,
     using the channel table from the SPHEREx Explanatory Supplement (Tables 29-34,
     data/reference/spherex_spectral_channels.csv).

Channel ranges in the supplement overlap slightly (and officially channels are defined by
position on the detector), so a wavelength is assigned to the channel with the NEAREST
central wavelength among channels 1-17. That is unambiguous and agrees with the table
everywhere except within the small overlaps.

The same table drives the simulator and the stacker, so simulated and real shots are
labelled identically. astropy is only needed for reading real FITS files.

Command line (prints the labels for one real file):
    python -m backend.track2_calibration.spectral_labels FILE.fits RA_DEG DEC_DEG
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import csv
import functools
import math
import os
import sys

CHANNEL_TABLE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "reference", "spherex_spectral_channels.csv")
)
NOMINAL_CHANNELS = range(1, 18)


def _detector_number(detector: Union[str, int]) -> int:
    """'D6', 'd6', 6 or '6' -> 6."""
    if isinstance(detector, int):
        return detector
    text = str(detector).strip().upper().lstrip("D")
    return int(text)


@functools.lru_cache(maxsize=1)
def load_channel_table(path: str = CHANNEL_TABLE_PATH) -> Dict[int, Dict[int, Dict[str, float]]]:
    """{detector: {channel: {lambda_c, lambda_min, lambda_max, width, R}}} for channels 0-18."""
    table: Dict[int, Dict[int, Dict[str, float]]] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        rows = csv.DictReader(line for line in fh if not line.startswith("#"))
        for row in rows:
            det, ch = int(row["detector"]), int(row["channel"])
            lo, hi = float(row["lambda_min_um"]), float(row["lambda_max_um"])
            table.setdefault(det, {})[ch] = {
                "lambda_c": float(row["lambda_c_um"]),
                "lambda_min": lo,
                "lambda_max": hi,
                "width": hi - lo,
                "R": float(row["R"]),
            }
    return table


def channel_info(detector: Union[str, int], channel: int) -> Dict[str, float]:
    """Centre, range, width and R of one channel (0-18) of one detector."""
    return load_channel_table()[_detector_number(detector)][channel]


def band_from_wavelength(detector: Union[str, int], wavelength_um: float) -> Dict[str, Any]:
    """
    Nearest-centre channel (1-17) for a wavelength seen on `detector`.
    `in_nominal_range` is False if the wavelength lies outside channels 1-17's coverage
    (it then falls in edge channel 0 or 18 and should be treated with care).
    """
    chans = load_channel_table()[_detector_number(detector)]
    band = min(NOMINAL_CHANNELS, key=lambda c: abs(chans[c]["lambda_c"] - wavelength_um))
    in_range = chans[1]["lambda_min"] <= wavelength_um <= chans[17]["lambda_max"]
    return {
        "band": band,
        "band_lambda_c": chans[band]["lambda_c"],
        "offset_from_centre_um": round(wavelength_um - chans[band]["lambda_c"], 5),
        "in_nominal_range": in_range,
    }


def wavelength_from_band_position(detector: Union[str, int], position: float) -> float:
    """
    Wavelength for a fractional position along the 17 channels: position k + 0.5 is the
    centre of channel k + 1 (k = 0..16), and k + 1.0 is halfway between two centres.
    Interpolates linearly between table centres (extrapolates over the outer half-channels).
    Used by the simulator so simulated shots follow the real, non-uniform channel spacing.
    """
    chans = load_channel_table()[_detector_number(detector)]
    centres = [chans[c]["lambda_c"] for c in NOMINAL_CHANNELS]
    u = position - 0.5  # 0 -> centre of channel 1, 16 -> centre of channel 17
    i = int(math.floor(u))
    i = max(0, min(len(centres) - 2, i))
    f = u - i
    return centres[i] + f * (centres[i + 1] - centres[i])


def label_spherex_shot(
    fits_file: Any,
    ra_deg: float,
    dec_deg: float,
) -> Dict[str, Any]:
    """
    Step 1 for one real SPHEREx Level-2 file (path or an open astropy HDUList).

    Returns detector, the target's pixel (0-based, astropy convention), whether it is on
    the image, lambda_at_target and bandwidth (um) from the spectral WCS, and the band.
    """
    try:
        import astropy.units as u
        from astropy.coordinates import SkyCoord
        from astropy.io import fits
        from astropy.wcs import WCS
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "Reading real SPHEREx wavelengths needs astropy: pip install astropy"
        ) from exc

    close = False
    hdul = fits_file
    if not hasattr(fits_file, "__getitem__") or isinstance(fits_file, (str, os.PathLike)):
        hdul = fits.open(fits_file)
        close = True
    try:
        header = hdul["IMAGE"].header

        # 1. Target pixel from the sky WCS
        spatial_wcs = WCS(header)
        x, y = spatial_wcs.world_to_pixel(SkyCoord(ra=ra_deg, dec=dec_deg, unit="deg", frame="icrs"))
        x, y = float(x), float(y)
        nx, ny = header.get("NAXIS1", 0), header.get("NAXIS2", 0)
        on_image = -0.5 <= x <= nx - 0.5 and -0.5 <= y <= ny - 0.5

        # 2. Wavelength at that pixel from the spectral WCS (WCS-WAVE lookup table)
        spectral_wcs = WCS(header, fobj=hdul, key="W")
        spectral_wcs.sip = None  # SIP distortion must be off for the spectral WCS
        wl, bw = spectral_wcs.pixel_to_world(x, y)
        lam = float(wl.to_value(u.um)) if hasattr(wl, "to_value") else float(wl)
        bandwidth = float(bw.to_value(u.um)) if hasattr(bw, "to_value") else float(bw)

        # 3. Band from the Explanatory Supplement channel table
        detector = header.get("DETECTOR")
        if detector is None:
            raise ValueError("IMAGE header has no DETECTOR keyword")
        band = band_from_wavelength(detector, lam)

        mjd = None
        for key in ("MJD-AVG", "MJD-OBS", "MJD", "MJD-BEG"):
            if key in header:
                mjd = float(header[key])
                break

        return {
            "detector": f"D{_detector_number(detector)}",
            "obsid": header.get("OBSID"),
            "mjd": mjd,
            "x_px": round(x, 3),
            "y_px": round(y, 3),
            "on_image": on_image,
            "lambda_at_target": round(lam, 5),
            "bandwidth_um": round(bandwidth, 5),
            **band,
        }
    finally:
        if close:
            hdul.close()


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print("usage: python -m backend.track2_calibration.spectral_labels FILE.fits RA_DEG DEC_DEG")
        return 2
    path, ra, dec = argv[0], float(argv[1]), float(argv[2])
    info = label_spherex_shot(path, ra, dec)
    print(
        f"{os.path.basename(path)}: {info['detector']}  target at pixel ({info['x_px']:.1f}, {info['y_px']:.1f})"
        f"{'' if info['on_image'] else '  [OFF IMAGE]'}\n"
        f"  lambda = {info['lambda_at_target']:.4f} um (bandwidth {info['bandwidth_um']:.4f} um), "
        f"band {info['band']} of 17 (centre {info['band_lambda_c']:.3f} um)"
        f"{'' if info['in_nominal_range'] else '  [outside channels 1-17]'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
