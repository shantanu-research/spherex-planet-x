"""Match real exposures using their per-pixel wavelength and bandwidth WCS."""
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS


def wavelength_grid(path, output_wcs, shape):
    with fits.open(path) as hdus:
        header = hdus['IMAGE'].header
        yy, xx = np.indices(shape)
        ra, dec = output_wcs.pixel_to_world_values(xx, yy)
        sx, sy = WCS(header).celestial.world_to_pixel_values(ra, dec)
        spectral = WCS(header, fobj=hdus, key='W')
        # SIP describes the celestial solution, not the alternate spectral WCS.
        spectral.sip = None
        wavelength, bandwidth = spectral.all_pix2world(sx, sy, 0)
        if spectral.world_axis_units != ['um', 'um']:
            raise ValueError('Unsupported spectral WCS units')
        return np.asarray(wavelength), np.asarray(bandwidth)


def matched_baseline(images, metadata, spectra):
    """Choose the longest cross-visit pair with target-centre spectral overlap.

    Mask individual pixels whose spectral responses do not overlap. This is a
    matched single-exposure comparison, not a detector-wide co-add.
    """
    best = None
    cy, cx = np.array(images[0].shape) // 2
    for i in range(len(images)):
        for j in range(i + 1, len(images)):
            a, b = metadata[i][0], metadata[j][0]
            if a.visit == b.visit or spectra[i] is None or spectra[j] is None:
                continue
            wi, bi = spectra[i]
            wj, bj = spectra[j]
            valid = (np.isfinite(wi) & np.isfinite(wj) & (bi > 0) & (bj > 0)
                     & (abs(wi - wj) <= .5 * np.minimum(bi, bj))
                     & np.isfinite(images[i]) & np.isfinite(images[j]))
            if not valid[cy, cx]:
                continue
            baseline = abs(b.t_start_mjd - a.t_start_mjd)
            if best is None or baseline > best[0]:
                best = (baseline, i, j, valid)
    if best is None:
        raise ValueError('No cross-visit exposures with matching wavelength coverage at this target')
    _, i, j, mask = best
    return [np.where(mask, images[k], np.nan) for k in (i, j)], [metadata[k] for k in (i, j)], [spectra[k] for k in (i, j)]
