"""Bounded live catalogue queries, projected with the same WCS as the science frames."""
from functools import lru_cache
import io
import warnings
import httpx
import numpy as np
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.table import Table
from astropy.time import Time
from backend.science import output_grid

@lru_cache(maxsize=32)
def query_rows(ra,dec,radius,catalog):
    if catalog=='gaia':
        url='https://gea.esac.esa.int/tap-server/tap/sync'
        sql=f"SELECT TOP 100 source_id,ra,dec,pmra,pmdec,ref_epoch FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra},{dec},{radius}))"
    else:
        url='https://irsa.ipac.caltech.edu/TAP/sync'
        sql=f"SELECT TOP 100 source_name,ra,dec FROM catwise_2020 WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra},{dec},{radius}))"
    response=httpx.get(url,params={'REQUEST':'doQuery','LANG':'ADQL','FORMAT':'votable','QUERY':sql},timeout=20,follow_redirects=True)
    response.raise_for_status()
    return Table.read(io.BytesIO(response.content),format='votable')

def overlays(target,mjd,fov):
    if not np.isfinite(mjd) or not 1<=fov<=15: raise ValueError('Invalid overlay epoch or field size')
    grid,shape=output_grid(target,fov)
    ra,dec=map(float,grid.wcs.crval)
    payload={'status':'success','gaia_dr3':[],'catwise':[],'errors':[],
             'note':'Gaia uses linear proper motion; CatWISE positions are catalogue-epoch references. No parallax correction or cross-match validation.'}
    for catalog,key in [('gaia','gaia_dr3'),('catwise','catwise')]:
        try:
            rows=query_rows(ra,dec,fov/60*.72,catalog)
            for row in rows:
                coord=SkyCoord(float(row['ra'])*u.deg,float(row['dec'])*u.deg)
                if catalog=='gaia' and not np.ma.is_masked(row['pmra']) and not np.ma.is_masked(row['pmdec']):
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore')
                        coord=SkyCoord(ra=coord.ra,dec=coord.dec,pm_ra_cosdec=float(row['pmra'])*u.mas/u.yr,pm_dec=float(row['pmdec'])*u.mas/u.yr,obstime=Time(float(row['ref_epoch']),format='jyear')).apply_space_motion(new_obstime=Time(mjd,format='mjd'))
                x,y=grid.world_to_pixel(coord)
                if 0<=x<shape[1] and 0<=y<shape[0]:
                    payload[key].append({'id':str(row['source_id' if catalog=='gaia' else 'source_name']),'catalog':catalog,'x':float(x),'y':float(y)})
        except Exception as exc:
            payload['errors'].append(f'{catalog}: {type(exc).__name__}; catalogue unavailable')
    return payload
