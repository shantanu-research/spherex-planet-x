"""Real FITS processing. Science arrays remain separate from rendered pixels.

Variance is propagated through bilinear interpolation using squared weights.
The output variance is marginal per pixel: interpolation induces covariance.
Aperture photometry is performed on native pixels to avoid that covariance.
"""
from dataclasses import dataclass
from pathlib import Path
import warnings
import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_area

@dataclass
class Exposure:
    image: np.ndarray
    variance: np.ndarray
    wavelength: np.ndarray
    bandwidth: np.ndarray
    mjd: float
    detector: str
    source: str
    target_xy: tuple
    photometry: dict
    visit: int = 0


def position(target, mjd):
    coord = SkyCoord(ra=target['ra_deg'] * u.deg, dec=target['dec_deg'] * u.deg,
                     pm_ra_cosdec=target.get('pm_ra_mas', 0) * u.mas/u.yr,
                     pm_dec=target.get('pm_dec_mas', 0) * u.mas/u.yr,
                     obstime=Time(target.get('discovery_epoch', 2000), format='jyear'))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        result = coord.apply_space_motion(new_obstime=Time(mjd, format='mjd'))
    return result.ra.deg, result.dec.deg


def output_grid(target, fov, mjd=61000):
    n = min(192, max(24, round(fov * 60 / 6.15)))
    w = WCS(naxis=2)
    w.wcs.ctype = ['RA---TAN', 'DEC--TAN']
    w.wcs.crval = position(target, mjd)
    w.wcs.crpix = [(n+1)/2] * 2
    w.wcs.cdelt = [-fov/60/n, -fov/60/n]
    return w, (n, n)


def resample(image, variance, sx, sy):
    finite_coords = np.isfinite(sx) & np.isfinite(sy)
    sx, sy = np.where(finite_coords, sx, -2), np.where(finite_coords, sy, -2)
    ix, iy = np.floor(sx).astype(int), np.floor(sy).astype(int)
    dx, dy = sx-ix, sy-iy
    total, var, norm = np.zeros(sx.shape), np.zeros(sx.shape), np.zeros(sx.shape)
    for ox, oy, weight in [(0,0,(1-dx)*(1-dy)),(1,0,dx*(1-dy)),(0,1,(1-dx)*dy),(1,1,dx*dy)]:
        x, y = ix+ox, iy+oy
        inside = finite_coords & (x>=0)&(y>=0)&(x<image.shape[1])&(y<image.shape[0])
        xc, yc = np.clip(x,0,image.shape[1]-1), np.clip(y,0,image.shape[0]-1)
        good = inside & np.isfinite(image[yc,xc]) & np.isfinite(variance[yc,xc]) & (variance[yc,xc]>0)
        wt = np.where(good,weight,0)
        total += wt*np.nan_to_num(image[yc,xc])
        var += wt**2*np.nan_to_num(variance[yc,xc])
        norm += wt
    good = norm > .999
    return np.where(good,total/np.maximum(norm,1e-30),np.nan), np.where(good,var/np.maximum(norm,1e-30)**2,np.nan)


def aperture(image, variance, xy, wavelength, bandwidth, pixel_area_sr):
    yy, xx = np.indices(image.shape)
    radius = np.hypot(xx-xy[0], yy-xy[1])
    ap, ann = radius<=2, (radius>=3)&(radius<=5)
    good = np.isfinite(image)&np.isfinite(variance)&(variance>0)
    if np.count_nonzero(ap & good) < .9*np.count_nonzero(ap) or np.count_nonzero(ann & good)<15:
        return {'status':'masked_or_outside', 'flux_mjy':None, 'flux_err_mjy':None}
    bg = np.median(image[ann & good])
    count = np.count_nonzero(ap & good)
    bg_var = np.median(variance[ann & good])/np.count_nonzero(ann & good)
    factor = pixel_area_sr * 1e9
    flux = np.sum(image[ap & good]-bg)*factor
    err = np.sqrt(np.sum(variance[ap & good])+count**2*bg_var)*factor
    x,y = int(round(float(xy[0]))), int(round(float(xy[1])))
    if not (0<=x<image.shape[1] and 0<=y<image.shape[0]):
        return {'status':'outside','flux_mjy':None,'flux_err_mjy':None}
    wave, band = wavelength[y,x], bandwidth[y,x]
    if not np.isfinite(wave) or not np.isfinite(band):
        return {'status':'missing_wavelength','flux_mjy':None,'flux_err_mjy':None}
    return {'status':'measured' if flux/err>=3 else 'low_snr', 'flux_mjy':float(flux),
            'flux_err_mjy':float(err),'snr':float(flux/err),'wavelength_um':float(wave),
            'bandwidth_um':float(band),'aperture_radius_px':2,
            'note':'Native aperture flux; no PSF aperture correction; uncertainties exclude calibration systematics.'}


def read_exposure(path, target, grid, shape):
    with fits.open(path) as hdus:
        h = hdus['IMAGE'].header
        image = np.array(hdus['IMAGE'].data,dtype=float)
        variance = np.array(hdus['VARIANCE'].data,dtype=float)
        if not u.Unit(h.get('BUNIT','')).is_equivalent(u.MJy/u.sr):
            raise ValueError('Unsupported surface brightness unit')
        if 'ZODI' in hdus:
            image -= hdus['ZODI'].data
        flags = hdus['FLAGS']
        bits = {int(v) for k,v in flags.header.items() if k.startswith('MP_') and k not in ('MP_SOURCE','MP_FULLSAMPLE')}
        bits |= {int(k[4:]) for k,v in flags.header.items() if k.startswith('MSKN') and str(v).strip() not in ('SOURCE','FULLSAMPLE')}
        if not bits:
            raise ValueError('Missing flag-bit definitions')
        reject = sum(1<<b for b in bits)
        mask = ((flags.data & reject)!=0) | ~np.isfinite(variance) | (variance<=0)
        image[mask], variance[mask] = np.nan,np.nan
        native = WCS(h).celestial
        mjd_value = h.get('MJD-OBS', h.get('MJD_OBS'))
        mjd = float(mjd_value if mjd_value is not None else Time(h['DATE-OBS']).mjd)
        detector = 'D'+str(h.get('DETECTOR',Path(path).name.split('D')[-1][0])).replace('SPHEREx-','').lstrip('D')
        spectral_header=h.copy()
        for key in list(spectral_header):
            if key.startswith(('A_','B_','AP_','BP_')): del spectral_header[key]
        spectral = WCS(spectral_header,fobj=hdus,key='W')
        if spectral.world_axis_units != ['um','um']:
            raise ValueError('Unsupported wavelength units')
        ny,nx = np.indices(image.shape)
        nw,nb = spectral.all_pix2world(nx,ny,0)
        target_pos = position(target,mjd)
        xy = native.world_to_pixel_values(*target_pos)
        phot = aperture(image,variance,xy,nw,nb,abs(proj_plane_pixel_area(native))*(np.pi/180)**2)
        phot.update(mjd=mjd,detector=detector,source=Path(path).name)
        yy,xx = np.indices(shape)
        sx,sy = native.world_to_pixel_values(*grid.pixel_to_world_values(xx,yy))
        values,var = resample(image,variance,sx,sy)
        wave,band = spectral.all_pix2world(sx,sy,0)
        return Exposure(values,var,np.asarray(wave),np.asarray(band),mjd,detector,str(path),
                        tuple(float(v) for v in grid.world_to_pixel_values(*target_pos)),phot)


def group(exposures):
    ordered = sorted(exposures,key=lambda e:e.mjd)
    visit,last=0,None
    for e in ordered:
        if last is not None and e.mjd-last>30: visit+=1
        e.visit=visit;last=e.mjd
    return ordered


def balanced_stacks(exposures, require_shared=True):
    """Fixed narrow log-wavelength bins, equal weights across shared bins.

    Channel membership is evaluated at every output pixel, avoiding a target-only
    wavelength label for a spatially varying filter. Missing common coverage stays masked.
    """
    visits=sorted({e.visit for e in exposures})
    if not visits: return []
    edges=np.geomspace(.7,5.3,257)
    channels=sorted({int(v) for e in exposures for v in np.unique(np.digitize(e.wavelength[np.isfinite(e.image)&np.isfinite(e.wavelength)],edges))})
    shape=exposures[0].image.shape
    sums=[np.zeros(shape) for _ in visits]; varsums=[np.zeros(shape) for _ in visits]; counts=[np.zeros(shape) for _ in visits]
    for ch in channels:
        means=[]; variances=[]; valid=[]
        for visit in visits:
            numerator,weight=np.zeros(shape),np.zeros(shape)
            for e in exposures:
                if e.visit!=visit: continue
                use=(np.digitize(e.wavelength,edges)==ch)&np.isfinite(e.image)&np.isfinite(e.variance)&(e.variance>0)
                wt=np.divide(1,e.variance,out=np.zeros(shape),where=use)
                numerator+=np.nan_to_num(e.image)*wt;weight+=wt
            valid.append(weight>0)
            means.append(np.divide(numerator,weight,out=np.zeros(shape),where=weight>0))
            variances.append(np.divide(1,weight,out=np.zeros(shape),where=weight>0))
        shared=np.logical_and.reduce(valid)
        for i in range(len(visits)):
            use=shared if require_shared else valid[i]
            sums[i]+=np.where(use,means[i],0);varsums[i]+=np.where(use,variances[i],0);counts[i]+=use
    result=[]
    for i,v in enumerate(visits):
        c=counts[i]; good=c>0
        es=[e for e in exposures if e.visit==v]
        result.append({'image':np.divide(sums[i],c,out=np.full(shape,np.nan),where=good),
                       'variance':np.divide(varsums[i],c*c,out=np.full(shape,np.nan),where=good),
                       'channels':c,'mjd':float(np.mean([e.mjd for e in es])), 'visit':v,
                       'target_xy':np.mean([e.target_xy for e in es],axis=0),
                       'sources':[Path(e.source).name for e in es]})
    return result


def tracked(stack, center):
    offset=np.asarray(center)-np.asarray(stack['target_xy'])
    result=dict(stack)
    yy,xx=np.indices(stack['image'].shape)
    result['image'],result['variance']=resample(stack['image'],stack['variance'],xx-offset[0],yy-offset[1])
    result['target_xy']=center
    return result


def measured_motion(stacks, scale):
    points=[]
    for s in stacks:
        image=s['image']; x,y=s['target_xy']; yy,xx=np.indices(image.shape)
        region=(np.hypot(xx-x,yy-y)<=3)&np.isfinite(image)
        if np.count_nonzero(region)<12: continue
        bg=np.nanmedian(image)
        signal=np.where(region,np.maximum(image-bg,0),0)
        noise=np.sqrt(np.nansum(np.where(region,s['variance'],0)))
        if signal.sum()<=5*noise or signal.sum()<=0: continue
        points.append((s['mjd'],float((signal*xx).sum()/signal.sum()),float((signal*yy).sum()/signal.sum())))
    if len(points)<3 or np.ptp([p[0] for p in points])<90:
        return {'status':'insufficient_data','validation_verdict':'At least three detected epochs spanning 90 days are required.'}
    t=np.array([p[0] for p in points]);t=(t-t.mean())/365.25
    sx,cx=np.polyfit(t,[p[1] for p in points],1);sy,cy=np.polyfit(t,[p[2] for p in points],1)
    return {'status':'measured','fitted_pm':{'pm_ra_cosdec_mas_yr':float(-sx*scale*1000),
            'pm_dec_mas_yr':float(-sy*scale*1000),'fitted_total_pm_arcsec_yr':float(np.hypot(sx,sy)*scale),
            'fitted_total_pm_mas_yr':float(np.hypot(sx,sy)*scale*1000)},
            'validation_verdict':'Aperture-centroid linear fit; not independently confirmed. Blends, parallax and PSF changes can bias this estimate.',
            'n_epochs':len(points)}
