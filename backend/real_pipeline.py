"""Unified local/live SPHEREx processing and rendering."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import threading
from functools import lru_cache
import numpy as np
from astropy.time import Time
from backend.science import read_exposure, output_grid, group, balanced_stacks, tracked, measured_motion, position
from backend.track1 import archive, cutouts, visits

DATA_ROOT=Path(os.environ.get('SPHEREX_DATA_DIR',str(Path(__file__).resolve().parent.parent/'data'/'observations')))
_LOCK=threading.Lock()
MODES=('visit_blink','longest_baseline','difference_sequence','motion_tracked','spectral_color','false_colour','wavelength_matched','within_visit_fast','spectral_preview','shift_stack')


def local_paths(target):
    return sorted((DATA_ROOT/target['id']).glob('*.fits'))


def discover(target,detector,fov):
    files=local_paths(target)
    if files: return files,[], 'Project Drive / NASA IRSA FITS'
    if target['id']=='planet_x_candidate':
        return [],['This hypothetical target is available only as a simulation.'],'none'
    ra,dec=position(target,Time.now().mjd)
    records=visits.select_frames(visits.group_visits(archive.search(ra,dec,fov/60,None)),limit=72)
    results=asyncio.run(cutouts.fetch_all([e.cutout_url for e in records]))
    return [cutouts.CUTOUT_DIR/r['file'] for r in results if r['file']], [r['error'] for r in results if r['error']], 'NASA IRSA live archive'


@lru_cache(maxsize=12)
def _load(target_json,detector,fov,signature):
    target=json.loads(target_json)
    paths,errors,provenance=discover(target,detector,fov)
    grid,shape=output_grid(target,fov)
    all_exposures=[]
    for path in paths:
        try:
            exposure=read_exposure(path,target,grid,shape)
            if np.isfinite(exposure.image).any(): all_exposures.append(exposure)
            else: errors.append(f'{path.name}: no usable pixels in requested field')
        except Exception as exc:
            errors.append(f'{path.name}: {type(exc).__name__}: {exc}')
    return group(all_exposures),grid,shape,errors,provenance


def load(target,detector,fov):
    if not np.isfinite(fov) or not 1<=fov<=15: raise ValueError('Field of view must be 1–15 arcminutes')
    paths=local_paths(target)
    signature=tuple((str(p),p.stat().st_mtime_ns) for p in paths)
    with _LOCK:
        return _load(json.dumps(target,sort_keys=True),detector,fov,signature)


def spectrum(exposures):
    measurements=[e.photometry for e in exposures]
    good=[m for m in measurements if m.get('flux_mjy') is not None]
    points=[]
    for i,m in enumerate(sorted(good,key=lambda m:m['wavelength_um'])):
        points.append(dict(m,channel_id=i+1,channel_in_detector=None,molecular_feature=None))
    return {'status':'measured' if points else 'unavailable','source':'real native FITS apertures',
            'spectrum':points,'measurements':measurements,'total_channels':len(points),
            'detected_molecular_features':[], 'peak_flux_mjy':max([p['flux_mjy'] for p in points],default=0),
            'note':'Observed wavelength samples only. No interpolated channels or molecular identification. Low-SNR fluxes are retained with errors.'}


def unavailable(target,mode,message,errors=None):
    return {'status':'unavailable','target':target,'mode':mode,'frames':[],'message':message,'errors':errors or []}


def _single(e):
    return {'image':e.image,'variance':e.variance,'mjd':e.mjd,'visit':e.visit,
            'target_xy':e.target_xy,'sources':[Path(e.source).name]}


def render(target,detector,fov,mode,stretch='asinh',frame_mode=None,color_mode=None):
    if mode not in MODES: raise ValueError('Unknown viewing mode')
    if detector not in [f'D{i}' for i in range(1,7)]: raise ValueError('Detector must be D1–D6')
    all_exp,grid,shape,errors,provenance=load(target,detector,fov)
    es=[e for e in all_exp if e.detector==detector]
    if not es: return unavailable(target,mode,f'No usable {detector} observations for this field.',errors)
    notes=['Flags are preserved as missing pixels. WCS registration has not been refined with stellar PSF fits.',
           'Preset catalogue positions and proper motions are inputs, not independently verified source identifications.',
           'Variance excludes calibration systematics and inter-pixel covariance introduced by resampling.']
    rgb_arrays=None
    if mode in ('within_visit_fast','spectral_preview'):
        stacks=[_single(e) for e in es]
        notes.append('Single exposures have varying wavelengths: flicker is not evidence of variability.')
    elif mode=='wavelength_matched':
        from backend.spectral_matching import matched_baseline
        metadata=[(type('Record',(),{'visit':e.visit,'t_start_mjd':e.mjd})(),'', '') for e in es]
        try:
            ims,met,_=matched_baseline([e.image for e in es],metadata,[(e.wavelength,e.bandwidth) for e in es])
            chosen=[next(e for e in es if e.mjd==m[0].t_start_mjd) for m in met]
            stacks=[dict(_single(e),image=im) for e,im in zip(chosen,ims)]
        except ValueError as exc: return unavailable(target,mode,str(exc),errors)
    elif mode in ('spectral_color','false_colour') or color_mode=='multiband':
        bands={d:balanced_stacks([e for e in all_exp if e.detector==d],require_shared=False) for d in ('D1','D3','D6')}
        common=set.intersection(*(set(s['visit'] for s in bands[d]) for d in bands))
        if not common: return unavailable(target,mode,'False colour requires D1, D3 and D6 in the same visit.',errors)
        stacks=[];rgb_arrays=[]
        for visit in sorted(common):
            components=[next(s for s in bands[d] if s['visit']==visit) for d in ('D6','D3','D1')]
            cube=np.stack([s['image'] for s in components],axis=-1)
            stacks.append(components[0]);rgb_arrays.append(cube)
        notes.append('False colour maps D6/D3/D1 to red/green/blue. Bands are not simultaneous.')
    else:
        stacks=balanced_stacks(es)
        if len(stacks)<2 and mode in ('longest_baseline','difference_sequence'):
            return unavailable(target,mode,'At least two observed visits are required.',errors)
        if not any(np.isfinite(s['image']).any() for s in stacks):
            return unavailable(target,mode,'Visits have no common wavelength coverage. Try individual exposures or another detector.',errors)
        if mode=='longest_baseline': stacks=[stacks[0],stacks[-1]]
        if mode=='difference_sequence':
            # Leave-one-out inverse-variance template; excludes each frame from its own reference.
            original=stacks
            stacks=[]
            for i,s in enumerate(original):
                other=[v for j,v in enumerate(original) if j!=i]
                weights=[np.divide(1,v['variance'],out=np.zeros(shape),where=np.isfinite(v['variance'])&(v['variance']>0)) for v in other]
                denom=np.sum(weights,axis=0)
                mean=np.divide(np.sum([np.nan_to_num(v['image'])*w for v,w in zip(other,weights)],axis=0),denom,out=np.full(shape,np.nan),where=denom>0)
                var=np.divide(1,denom,out=np.full(shape,np.nan),where=denom>0)
                stacks.append(dict(s,image=s['image']-mean,variance=s['variance']+var))
            notes.append('Differences use leave-one-out templates. PSF mismatch can leave residuals; they are not confirmed transients.')
    motion=measured_motion(balanced_stacks(es),fov*60/shape[0])
    if mode in ('motion_tracked','shift_stack') or frame_mode=='comoving':
        stacks=[tracked(s,((shape[1]-1)/2,(shape[0]-1)/2)) for s in stacks]
        notes.append('Tracking uses catalogue proper motion, not a measured motion fit; annual parallax is not corrected.')
    if mode=='shift_stack':
        ims=np.array([s['image'] for s in stacks]);valid=np.isfinite(ims)
        count=valid.sum(axis=0)
        stacked=np.divide(np.nansum(ims,axis=0),count,out=np.full(shape,np.nan),where=count>0)
        variance=np.divide(np.nansum([np.where(ok,s['variance'],np.nan) for s,ok in zip(stacks,valid)],axis=0),count**2,out=np.full(shape,np.nan),where=count>0)
        stacks=[dict(stacks[0],image=stacked,variance=variance,sources=sum([s['sources'] for s in stacks],[]))]
    finite=np.concatenate([s['image'][np.isfinite(s['image'])] for s in stacks])
    if not len(finite): return unavailable(target,mode,'All output pixels are masked.',errors)
    low,high=np.percentile(finite,[1,99.5]); span=max(high-low,1e-20)
    def stretch_image(im):
        normalized=np.clip((im-low)/span,0,1)
        if stretch=='asinh': normalized=np.arcsinh(10*normalized)/np.arcsinh(10)
        elif stretch=='sqrt': normalized=np.sqrt(normalized)
        elif stretch=='log': normalized=np.log1p(9*normalized)/np.log(10)
        return np.nan_to_num(normalized*255).astype('uint8')
    frames=[]
    for i,s in enumerate(stacks):
        im=s['image']; mask=~np.isfinite(im)
        if mode=='difference_sequence':
            limit=max(float(np.percentile(abs(finite),99)),1e-20)
            signed=np.clip(im/limit,-1,1)
            rgb=np.stack([np.clip(signed,0,1),np.zeros(shape),np.clip(-signed,0,1)],axis=-1)
            rgb=np.nan_to_num(rgb*255).astype('uint8')
        elif rgb_arrays is not None:
            cube=rgb_arrays[i];finite_rgb=np.concatenate([c[np.isfinite(c)] for c in rgb_arrays]); ceiling=max(float(np.percentile(finite_rgb,99.5)),1e-20)
            rgb=np.nan_to_num(np.arcsinh(10*np.clip(cube/ceiling,0,1))/np.arcsinh(10)*255).astype('uint8')
            mask=~np.isfinite(cube).all(axis=-1)
        else:
            rgb=np.repeat(stretch_image(im)[:,:,None],3,axis=2)
            if color_mode=='spectral':
                from backend.track4_rendering.colorization import DETECTOR_SUPERPOSITION_WEIGHTS
                rgb=(rgb*np.asarray(DETECTOR_SUPERPOSITION_WEIGHTS[detector])).astype('uint8')
        rgb[mask]=[20,24,32]
        frames.append({'frame_id':str(i),'visit_id':f"V{s['visit']+1}",'mjd':s['mjd'],
            'date_utc':Time(s['mjd'],format='mjd').isot,'epoch_year':float(Time(s['mjd'],format='mjd').jyear),
            'target_pos_px':list(s['target_xy']),'target_displacement_px':[0,0],
            'band':detector,'label':f"V{s['visit']+1}",'instrument':'SPHEREx','is_real_data':True,
            'source_file':', '.join(s['sources']),'rgb_pixels':rgb.tolist(),'mask':mask.astype(int).tolist(),
            'fov_arcmin':fov,'pixel_scale_arcsec':fov*60/shape[0]})
    return {'status':'success','target':target,'detector':detector,'mode':mode,'is_real_data':True,
        'grid_size':shape[0],'frames':frames,'field_stars':[],'flicker_audit':None,
        'astrometric_validation':motion,'spectrophotometry':spectrum(all_exp),
        'manifest':{'n_frames':len(frames),'n_exposures':len(es),'grid_size':shape[0],
        'pixel_scale_arcsec':fov*60/shape[0],'fov_arcmin':fov,'source':provenance,'notes':notes,
        'errors':errors,'wcs':dict(grid.to_header()),'stretches':{'vmin':float(low),'vmax':float(high)}}}
