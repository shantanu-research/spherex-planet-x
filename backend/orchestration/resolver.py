"""
SPHEREx Planet X Challenge - Target Astrometric Resolver
Propagates celestial coordinates through proper motion and annual parallax across epochs.
"""

import math
from typing import Dict, Any, Tuple
from .catalog import get_target_by_query

SPHEREx_PIXEL_SCALE_ARCSEC = 6.15  # Native SPHEREx pixel scale: 6.15 arcsec/px
MISSION_MID_EPOCH = 2025.8         # October 2025 (Midpoint of Survey 1 & 2)

def earth_barycentric_coords(epoch_year: float) -> Tuple[float, float, float]:
    """
    Approximate Earth's barycentric position in AU as a function of decimal year.
    Used to calculate annual parallax reflex ellipses.
    """
    fraction = epoch_year - math.floor(epoch_year)
    mean_anomaly = 2.0 * math.pi * fraction
    # Earth's orbit approximated on ecliptic with obliquity eps ~ 23.44 deg
    eps = math.radians(23.4392911)
    x = -math.sin(mean_anomaly)
    y_ecl = math.cos(mean_anomaly)
    y = y_ecl * math.cos(eps)
    z = y_ecl * math.sin(eps)
    return x, y, z

def propagate_coordinates(
    ra_deg_0: float,
    dec_deg_0: float,
    epoch_0: float,
    target_epoch: float,
    pm_ra_mas: float,
    pm_dec_mas: float,
    parallax_mas: float
) -> Dict[str, Any]:
    """
    Propagate celestial coordinates from discovery epoch_0 to target_epoch.
    Includes proper motion (linear drift) + annual parallax (reflex ellipse).
    """
    dt_years = target_epoch - epoch_0
    dec_rad_0 = math.radians(dec_deg_0)
    cos_dec = max(0.001, math.cos(dec_rad_0))
    
    # 1. Proper motion displacement in mas
    # pm_ra_mas is mu_alpha * cos(dec), so delta_ra = pm_ra_mas / cos(dec)
    delta_ra_pm_mas = (pm_ra_mas * dt_years) / cos_dec
    delta_dec_pm_mas = pm_dec_mas * dt_years
    
    # 2. Annual Parallax displacement in mas
    if parallax_mas > 0.0:
        X, Y, Z = earth_barycentric_coords(target_epoch)
        ra_rad_0 = math.radians(ra_deg_0)
        sin_ra = math.sin(ra_rad_0)
        cos_ra = math.cos(ra_rad_0)
        sin_dec = math.sin(dec_rad_0)
        
        delta_ra_par_mas = parallax_mas * (X * sin_ra - Y * cos_ra) / cos_dec
        delta_dec_par_mas = parallax_mas * (X * cos_ra * sin_dec + Y * sin_ra * sin_dec - Z * cos_dec)
    else:
        delta_ra_par_mas = 0.0
        delta_dec_par_mas = 0.0
        
    total_delta_ra_mas = delta_ra_pm_mas + delta_ra_par_mas
    total_delta_dec_mas = delta_dec_pm_mas + delta_dec_par_mas
    
    # Convert mas to degrees (1 deg = 3,600,000 mas)
    ra_prop_deg = (ra_deg_0 + total_delta_ra_mas / 3600000.0) % 360.0
    dec_prop_deg = max(-90.0, min(90.0, dec_deg_0 + total_delta_dec_mas / 3600000.0))
    
    # Angular separation in arcseconds
    dra_arcsec = (total_delta_ra_mas / 1000.0) * cos_dec
    ddec_arcsec = total_delta_dec_mas / 1000.0
    total_drift_arcsec = math.hypot(dra_arcsec, ddec_arcsec)
    total_drift_px = total_drift_arcsec / SPHEREx_PIXEL_SCALE_ARCSEC
    
    return {
        "epoch_0": epoch_0,
        "target_epoch": target_epoch,
        "dt_years": round(dt_years, 3),
        "ra_prop_deg": round(ra_prop_deg, 6),
        "dec_prop_deg": round(dec_prop_deg, 6),
        "dra_arcsec": round(dra_arcsec, 3),
        "ddec_arcsec": round(ddec_arcsec, 3),
        "total_drift_arcsec": round(total_drift_arcsec, 3),
        "total_drift_px": round(total_drift_px, 2),
        "parallax_shift_arcsec": round(math.hypot(delta_ra_par_mas, delta_dec_par_mas) / 1000.0, 3)
    }

def resolve_target(query: str, target_epoch: float = MISSION_MID_EPOCH) -> Dict[str, Any]:
    """
    Full target resolution pipeline:
    Resolves name -> pulls catalog metadata -> propagates astrometry to target observation epoch.
    """
    target = get_target_by_query(query)
    prop = propagate_coordinates(
        ra_deg_0=target["ra_deg"],
        dec_deg_0=target["dec_deg"],
        epoch_0=target["discovery_epoch"],
        target_epoch=target_epoch,
        pm_ra_mas=target["pm_ra_mas"],
        pm_dec_mas=target["pm_dec_mas"],
        parallax_mas=target["parallax_mas"]
    )
    
    # Check for stale catalog epoch hazard warning
    stale_epoch_warning = None
    if prop["total_drift_px"] > 1.5:
        stale_epoch_warning = (
            f"STALE CATALOG EPOCH HAZARD: Target has drifted {prop['total_drift_arcsec']}\" "
            f"({prop['total_drift_px']} native SPHEREx pixels) since epoch {target['discovery_epoch']}. "
            f"Naive querying at catalog coordinates would place target at stamp boundary or fail FOV coverage! "
            f"Propagated to {target_epoch} coordinates: RA {prop['ra_prop_deg']:.5f}°, Dec {prop['dec_prop_deg']:.5f}°."
        )
        
    return {
        "status": "resolved",
        "target": target,
        "epoch_propagation": prop,
        "stale_epoch_warning": stale_epoch_warning
    }
