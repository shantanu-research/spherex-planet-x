"""Bounded live archive preview; no invented epochs or scientific validation."""
import asyncio
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from scipy.ndimage import map_coordinates
from backend.irsa import archive, cutouts, visits


def aligned_image(path, output_wcs, shape):
    with fits.open(path) as hdus:
        hdu = hdus['IMAGE']
        data = np.array(hdu.data, dtype=float)
        if 'ZODI' in hdus:
            data -= hdus['ZODI'].data
        valid = np.isfinite(data)
        if 'FLAGS' in hdus:
            flag_hdu = hdus['FLAGS']
            # Source and full-sample flags are informational, not rejected pixels.
            bits = [int(v) for k, v in flag_hdu.header.items()
                    if k.startswith('MP_') and k not in ('MP_SOURCE', 'MP_FULLSAMPLE')]
            reject = sum(1 << bit for bit in set(bits)) if bits else -1
            valid &= (flag_hdu.data & reject) == 0
        yy, xx = np.indices(shape)
        ra, dec = output_wcs.pixel_to_world_values(xx, yy)
        sx, sy = WCS(hdu.header).celestial.world_to_pixel_values(ra, dec)
        coords = np.array([sy, sx])
        weights = map_coordinates(valid.astype(float), coords, order=1, mode='constant', cval=0)
        values = map_coordinates(np.where(valid, data, 0), coords, order=1, mode='constant', cval=0)
        result = np.divide(values, weights, out=np.full(shape, np.nan), where=weights > .99)
        return result, hdu.header.get('DATE-OBS', ''), hdu.header.get('BUNIT', '')


def render_live(target, detector, fov, mode):
    if mode not in ('within_visit_fast', 'spectral_preview', 'wavelength_matched', 'longest_baseline'):
        return {'status': 'unavailable', 'frames': [], 'message': 'Live archive preview supports individual exposures. Temporal comparisons require verified matching wavelength coverage.'}
    ra, dec = target['ra_deg'], target['dec_deg']
    records = visits.select_frames(visits.group_visits(archive.search(ra, dec, fov / 60, detector)), limit=24)
    results = asyncio.run(cutouts.fetch_all([r.cutout_url for r in records]))
    n = min(256, max(16, round(fov * 60 / 6.15)))
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ['RA---TAN', 'DEC--TAN']
    wcs.wcs.crval = [ra, dec]
    wcs.wcs.crpix = [(n + 1) / 2] * 2
    scale = fov / 60 / n
    wcs.wcs.cdelt = [-scale, scale]
    images, metadata, failures, spectra = [], [], [], []
    for record, download in zip(records, results):
        if download['error']:
            failures.append(download['error'])
            continue
        try:
            pixels, date, unit = aligned_image(cutouts.CUTOUT_DIR / download['file'], wcs, (n, n))
            if not np.isfinite(pixels).any():
                continue
            from backend.spectral_matching import wavelength_grid
            try:
                spectrum = wavelength_grid(cutouts.CUTOUT_DIR / download['file'], wcs, (n, n))
            except (ValueError, KeyError):
                spectrum = None
            spectra.append(spectrum)
            images.append(pixels)
            metadata.append((record, date, unit))
        except (ValueError, KeyError, OSError) as exc:
            failures.append(str(exc))
    if not images:
        return {'status': 'unavailable', 'frames': [], 'message': 'No usable archive cutouts', 'errors': failures}
    if mode in ('wavelength_matched', 'longest_baseline'):
        from backend.spectral_matching import matched_baseline
        images, metadata, spectra = matched_baseline(images, metadata, spectra)
    finite = np.concatenate([im[np.isfinite(im)] for im in images])
    low, high = np.percentile(finite, [1, 99.5])
    frames = []
    for i, (pixels, (record, date, unit)) in enumerate(zip(images, metadata)):
        normalized = np.clip((pixels - low) / max(high - low, 1e-12), 0, 1)
        grey = np.nan_to_num(np.arcsinh(normalized * 10) / np.arcsinh(10) * 255).astype('uint8')
        frames.append({'frame_id': str(i), 'visit_id': str(record.visit), 'date_utc': date,
                       'mjd': record.t_start_mjd, 'band': detector, 'label': date,
                       'is_real_data': True, 'source_file': record.image_url,
                       'target_pos_px': [n / 2, n / 2], 'wavelength_um': float(spectra[i][0][n // 2, n // 2]) if spectra[i] is not None else None,
                       'rgb_pixels': np.repeat(grey[:, :, None], 3, axis=2).tolist()})
    return {'status': 'success', 'target': target, 'detector': detector, 'mode': mode,
            'grid_size': n, 'is_real_data': True, 'frames': frames, 'field_stars': [],
            'spectrophotometry': {'spectrum': []}, 'flicker_audit': None,
            'astrometric_validation': None, 'manifest': {'n_frames': len(frames),
            'grid_size': n, 'pixel_scale_arcsec': scale * 3600, 'fov_arcmin': fov,
            'warning': 'Individual exposure preview: wavelengths vary; flickering is not evidence of variability.',
            'source': 'IRSA', 'errors': failures}}
