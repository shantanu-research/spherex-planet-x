"""
SPHEREx Planet X Challenge - Temporal Visit Clustering
Groups SPHEREx exposures into discrete survey passes based on 30-day temporal gaps.
"""

from typing import List, Dict, Any
from datetime import datetime, timezone

SURVEY_3_MJD_BOUNDARY = 61176.0  # Survey 3/4 Nyquist half-channel stepping begins May 16, 2026 (MJD 61176)
TEMPORAL_GAP_THRESHOLD_DAYS = 30.0

def mjd_to_utc_iso(mjd: float) -> str:
    """Convert Modified Julian Date to ISO UTC string."""
    # MJD 0 is 1858-11-17
    # Unix epoch (1970-01-01) is MJD 40587
    unix_time = (mjd - 40587.0) * 86400.0
    dt = datetime.fromtimestamp(unix_time, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

def mjd_to_decimal_year(mjd: float) -> float:
    """Convert MJD to decimal fractional year."""
    # Approx 365.25 days/yr from J2000.0 (MJD 51544.5 = 2000-01-01 12:00)
    return 2000.0 + (mjd - 51544.5) / 365.25

def cluster_exposures_into_visits(exposures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sorts exposures chronologically by MJD-OBS and clusters them into visits V_1 ... V_M
    at every gap delta_t > 30.0 days.
    """
    if not exposures:
        return []

    # Sort strictly by MJD mid-point
    sorted_exps = sorted(exposures, key=lambda x: x["mjd_mid"])
    
    visits: List[Dict[str, Any]] = []
    current_cluster: List[Dict[str, Any]] = []
    
    for exp in sorted_exps:
        if not current_cluster:
            current_cluster.append(exp)
            continue
            
        prev_mjd = current_cluster[-1]["mjd_mid"]
        gap_days = exp["mjd_mid"] - prev_mjd
        
        if gap_days > TEMPORAL_GAP_THRESHOLD_DAYS:
            # Finalize current visit cluster
            visit_id = f"V{len(visits) + 1}"
            mjd_start = min(e["mjd_mid"] for e in current_cluster)
            mjd_end = max(e["mjd_mid"] for e in current_cluster)
            mjd_mid = 0.5 * (mjd_start + mjd_end)
            
            visits.append({
                "visit_id": visit_id,
                "visit_index": len(visits) + 1,
                "mjd_start": round(mjd_start, 4),
                "mjd_end": round(mjd_end, 4),
                "mjd_mid": round(mjd_mid, 4),
                "decimal_year": round(mjd_to_decimal_year(mjd_mid), 4),
                "date_utc": mjd_to_utc_iso(mjd_mid),
                "survey_pass": "Survey 1/2 (Canonical)" if mjd_mid < SURVEY_3_MJD_BOUNDARY else "Survey 3/4 (Nyquist Half-Channel)",
                "n_exposures": len(current_cluster),
                "exposures": current_cluster
            })
            current_cluster = [exp]
        else:
            current_cluster.append(exp)
            
    # Add final cluster
    if current_cluster:
        visit_id = f"V{len(visits) + 1}"
        mjd_start = min(e["mjd_mid"] for e in current_cluster)
        mjd_end = max(e["mjd_mid"] for e in current_cluster)
        mjd_mid = 0.5 * (mjd_start + mjd_end)
        
        visits.append({
            "visit_id": visit_id,
            "visit_index": len(visits) + 1,
            "mjd_start": round(mjd_start, 4),
            "mjd_end": round(mjd_end, 4),
            "mjd_mid": round(mjd_mid, 4),
            "decimal_year": round(mjd_to_decimal_year(mjd_mid), 4),
            "date_utc": mjd_to_utc_iso(mjd_mid),
            "survey_pass": "Survey 1/2 (Canonical)" if mjd_mid < SURVEY_3_MJD_BOUNDARY else "Survey 3/4 (Nyquist Half-Channel)",
            "n_exposures": len(current_cluster),
            "exposures": current_cluster
        })
        
    return visits
