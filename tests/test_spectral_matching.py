from types import SimpleNamespace
import numpy as np
import pytest
from backend.spectral_matching import matched_baseline


def fixtures():
    images = [np.ones((3, 3)), np.ones((3, 3)) * 2]
    meta = [(SimpleNamespace(visit=i, t_start_mjd=60000 + i * 180), '', '') for i in range(2)]
    spectra = [(np.ones((3, 3)) * 4.5, np.ones((3, 3)) * .04) for _ in range(2)]
    return images, meta, spectra


def test_masks_mismatched_pixels_without_altering_flux():
    images, meta, spectra = fixtures()
    spectra[1][0][0, 0] = 4.8
    out, _, _ = matched_baseline(images, meta, spectra)
    assert np.isnan(out[0][0, 0])
    assert out[0][1, 1] == 1 and out[1][1, 1] == 2


def test_rejects_target_wavelength_mismatch():
    images, meta, spectra = fixtures()
    spectra[1][0][:] = 4.8
    with pytest.raises(ValueError, match='matching wavelength'):
        matched_baseline(images, meta, spectra)


def test_rejects_single_visit():
    images, meta, spectra = fixtures()
    meta[1][0].visit = 0
    with pytest.raises(ValueError):
        matched_baseline(images, meta, spectra)
