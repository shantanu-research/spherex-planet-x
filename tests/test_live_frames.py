import tempfile
from pathlib import Path
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from backend.live_frames import aligned_image


def test_wcs_alignment_and_mask_preservation():
    w = WCS(naxis=2)
    w.wcs.ctype = ['RA---TAN', 'DEC--TAN']
    w.wcs.crval = [20, 30]
    w.wcs.crpix = [5, 5]
    w.wcs.cdelt = [-.001, .001]
    data = np.full((9, 9), 12.)
    flags = np.zeros((9, 9), dtype=np.int32)
    flags[4, 4] = 1
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'fixture.fits'
        fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(data, header=w.to_header(), name='IMAGE'),
                      fits.ImageHDU(flags, name='FLAGS'), fits.ImageHDU(np.full((9, 9), 2.), name='ZODI')]).writeto(path)
        result, _, _ = aligned_image(path, w, (9, 9))
    assert np.isnan(result[4, 4])
    assert np.allclose(result[2:4, 2:4], 10.)
