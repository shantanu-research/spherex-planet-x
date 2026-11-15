"""
Builds a small SPHEREx-like Level-2 spectral image (multi-extension FITS) for tests.

Same structure as the real files (IMAGE, FLAGS, VARIANCE, ZODI, PSF, WCS-WAVE), with a
sky WCS and a spectral "W" WCS that points at the WCS-WAVE lookup table (FITS -TAB).
Wavelength rises linearly along y, as the linear variable filter does on the detector.
Needs astropy and numpy.
"""

import numpy as np
from astropy.io import fits
from astropy.table import Table

def make_fake_spherex_mef(path, ra0=135.0, dec0=-7.0, detector=6, n=64, lam_lo=4.45, lam_hi=4.95, bw=0.037):
    """SPHEREx-like Level-2 MEF: IMAGE (TAN sky WCS + 'W' WAVE-TAB WCS), FLAGS, VARIANCE, ZODI, PSF, WCS-WAVE.
    Wavelength rises linearly with y (LVF runs along one detector axis); bandwidth constant."""
    h = fits.Header()
    h["EXTNAME"] = "IMAGE"; h["DETECTOR"] = detector; h["MJD-AVG"] = 60810.5; h["OBSID"] = "FAKE_0001"
    h["BUNIT"] = "MJy / sr"
    h["WCSAXES"] = 2
    h["CTYPE1"], h["CTYPE2"] = "RA---TAN", "DEC--TAN"
    h["CRPIX1"], h["CRPIX2"] = (n + 1) / 2.0, (n + 1) / 2.0
    h["CRVAL1"], h["CRVAL2"] = ra0, dec0
    h["CDELT1"], h["CDELT2"] = -6.15 / 3600.0, 6.15 / 3600.0
    h["CUNIT1"], h["CUNIT2"] = "deg", "deg"
    # Spectral WCS 'W': 2 world coords (wavelength, bandwidth) from one -TAB coordinate array
    h["WCSAXESW"] = 2
    h["WCSNAMEW"] = "Approximated per-pixel wavelength and bandwidth"
    h["CTYPE1W"], h["CTYPE2W"] = "WAVE-TAB", "WAVE-TAB"
    h["CUNIT1W"], h["CUNIT2W"] = "um", "um"
    h["CRPIX1W"], h["CRPIX2W"] = 0.0, 0.0
    h["CRVAL1W"], h["CRVAL2W"] = 0.0, 0.0
    h["CDELT1W"], h["CDELT2W"] = 1.0, 1.0
    h["PS1_0W"], h["PS1_1W"], h["PS1_2W"], h["PV1_3W"] = "WCS-WAVE", "VALUES", "X", 1
    h["PS2_0W"], h["PS2_1W"], h["PS2_2W"], h["PV2_3W"] = "WCS-WAVE", "VALUES", "Y", 2
    xs = np.linspace(1, n, 9).round().astype(np.int32)
    ys = xs.copy()
    vals = np.zeros((9, 9, 2), dtype=np.float32)  # numpy order (y, x, m) == FITS TDIM (2, 9, 9)
    for j, yv in enumerate(ys):
        lam = lam_lo + (lam_hi - lam_lo) * (yv - 1) / (n - 1)
        vals[j, :, 0] = lam
        vals[j, :, 1] = bw
    img = np.zeros((n, n), dtype=np.float32)
    hdus = [fits.PrimaryHDU(), fits.ImageHDU(img, header=h)]
    for name in ("FLAGS", "VARIANCE", "ZODI"):
        hdus.append(fits.ImageHDU(np.zeros((n, n), dtype=np.float32), name=name))
    hdus.append(fits.ImageHDU(np.zeros((3, 5, 5), dtype=np.float32), name="PSF"))
    t = fits.BinTableHDU.from_columns([
        fits.Column(name="X", format="9J", array=xs[None, :]),
        fits.Column(name="Y", format="9J", array=ys[None, :]),
        fits.Column(name="VALUES", format="162E", dim="(2,9,9)", array=vals[None, ...]),
    ], name="WCS-WAVE")
    hdus.append(t)
    fits.HDUList(hdus).writeto(path, overwrite=True)
    return lam_lo, lam_hi, n
