"""Resolve presets, decimal/sexagesimal coordinates and external object names."""
import hashlib
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote
import httpx
from astropy.coordinates import SkyCoord
from astropy import units as u
from backend.track1_orchestration.catalog import get_target_by_query


def resolve(query):
    try:
        return dict(get_target_by_query(query))
    except ValueError:
        pass
    query=query.strip()
    if not query or len(query)>160: raise ValueError('Enter a target name or RA, Dec')
    parts=re.split(r'[,\s]+',query)
    try:
        if len(parts)==2:
            if ':' in query: c=SkyCoord(parts[0],parts[1],unit=(u.hourangle,u.deg))
            else:
                ra,dec=map(float,parts)
                if not 0<=ra<360 or not -90<=dec<=90: raise ValueError('Coordinates out of bounds')
                c=SkyCoord(ra*u.deg,dec*u.deg)
        else: raise ValueError('Not coordinate input')
    except ValueError:
        if any(ch.isdigit() for ch in query) and re.fullmatch(r'[\d\s,:.+-]+',query):
            raise ValueError('Use RA in [0,360) and Dec in [-90,90], or hh:mm:ss ±dd:mm:ss')
        response=httpx.get('https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?'+quote(query,safe=''),timeout=15)
        response.raise_for_status()
        root=ET.fromstring(response.text)
        ra,dec=root.find('.//jradeg'),root.find('.//jdedeg')
        if ra is None or dec is None: raise ValueError('Object name could not be resolved')
        c=SkyCoord(float(ra.text)*u.deg,float(dec.text)*u.deg)
    return {'id':'field_'+hashlib.sha256(query.encode()).hexdigest()[:12], 'common_name':query,'name':query,
            'ra_deg':float(c.ra.deg),'dec_deg':float(c.dec.deg),'discovery_epoch':2000.,
            'pm_ra_mas':0.,'pm_dec_mas':0.,'parallax_mas':0.,'category':'User-selected field',
            'spectral_type':'Unknown','teff_k':0,'peak_detector':'D6',
            'description':'Coordinates resolved in ICRS; proper motion is unknown and has not been inferred.'}
