"""Find SPHEREx exposures covering a sky position (IRSA TAP).

Query pattern follows IRSA's official spherex-cutouts tutorial:
spherex.artifact JOIN spherex.plane, footprint CONTAINS the point.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from astropy.time import Time

IRSA_BASE = "https://irsa.ipac.caltech.edu/"
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "queries"
QUERY_CACHE_SECONDS = 6 * 3600

# Newer releases win when the same exposure appears twice.
RELEASE_RANK = {"dr1": 3, "qr3": 2, "qr2": 1, "qr": 0, "unknown": -1}


@dataclass
class Exposure:
    """One SPHEREx exposure covering the target. Shared with the processing, spectra and viewer modules."""
    image_url: str        # full-image URL (never download this directly, ~70 MB)
    cutout_url: str       # same image cut down around the target
    t_start_mjd: float
    t_end_mjd: float
    t_start_iso: str
    detector: str         # e.g. "SPHEREx-D2"
    release: str          # dr1 / qr3 / qr2 / unknown
    visit: int = -1       # filled in by visits.group_visits

    def to_dict(self) -> dict:
        return asdict(self)


def build_query(ra: float, dec: float, detector: str | None = None,
                t_min_mjd: float | None = None, t_max_mjd: float | None = None) -> str:
    if not math.isfinite(ra) or not math.isfinite(dec) or not 0 <= ra < 360 or not -90 <= dec <= 90:
        raise ValueError("RA must be in [0, 360) and declination in [-90, 90] degrees")
    q = (
        "SELECT a.uri, p.time_bounds_lower, p.time_bounds_upper, p.energy_bandpassname "
        "FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid "
        f"WHERE 1 = CONTAINS(POINT('ICRS', {ra:.7f}, {dec:.7f}), p.poly)"
    )
    if detector:
        q += f" AND p.energy_bandpassname = '{_detector_name(detector)}'"
    if t_min_mjd is not None:
        q += f" AND p.time_bounds_lower >= {t_min_mjd}"
    if t_max_mjd is not None:
        q += f" AND p.time_bounds_lower <= {t_max_mjd}"
    return q + " ORDER BY p.time_bounds_lower"


def _detector_name(det: str | int) -> str:
    s = str(det).strip().upper()
    if s.startswith("SPHEREX-"):
        s = s.split("-", 1)[1]
    if s.startswith("D"):
        s = s[1:]
    number = int(s)
    if number not in range(1, 7):
        raise ValueError("Detector must be between D1 and D6")
    return f"SPHEREx-D{number}"


def guess_release(uri: str) -> str:
    m = re.search(r"(dr\d|qr\d?)", uri.lower())
    return m.group(1) if m else "unknown"


def cutout_url(image_url: str, ra: float, dec: float, size_deg: float) -> str:
    sep = "&" if "?" in image_url else "?"
    return f"{image_url}{sep}center={ra:.7f},{dec:.7f}d&size={size_deg:.5f}"


def rows_to_exposures(rows, ra: float, dec: float, size_deg: float) -> list[Exposure]:
    out = []
    for uri, t0, t1, band in rows:
        uri = str(uri)
        image_url = uri if uri.startswith("http") else IRSA_BASE + uri.lstrip("/")
        t0, t1 = float(t0), float(t1)
        out.append(Exposure(
            image_url=image_url,
            cutout_url=cutout_url(image_url, ra, dec, size_deg),
            t_start_mjd=t0,
            t_end_mjd=t1,
            t_start_iso=Time(t0, format="mjd").isot,
            detector=str(band),
            release=guess_release(uri),
        ))
    return out


def deduplicate(exps: list[Exposure]) -> list[Exposure]:
    """Same detector + same start time (to ~1 s) = same exposure; keep newest release."""
    best: dict[tuple, Exposure] = {}
    for e in exps:
        key = (e.detector, round(e.t_start_mjd * 86400))
        cur = best.get(key)
        if cur is None or RELEASE_RANK.get(e.release, -1) > RELEASE_RANK.get(cur.release, -1):
            best[key] = e
    return sorted(best.values(), key=lambda e: (e.t_start_mjd, e.detector))


def _run_tap(query: str):
    import io
    import httpx
    from astropy.table import Table
    response = httpx.get(
        IRSA_BASE + "TAP/sync",
        params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": query},
        timeout=45.0, follow_redirects=True,
    )
    response.raise_for_status()
    table = Table.read(io.BytesIO(response.content), format="votable")
    return [tuple(r) for r in table.iterrows(
        "uri", "time_bounds_lower", "time_bounds_upper", "energy_bandpassname")]



def search(ra: float, dec: float, size_deg: float = 0.083, detector: str | None = None,
           t_min_mjd: float | None = None, t_max_mjd: float | None = None,
           use_cache: bool = True, tap=None) -> list[Exposure]:
    """Position -> deduplicated list of exposures (visit numbers not yet set)."""
    query = build_query(ra, dec, detector, t_min_mjd, t_max_mjd)
    if not math.isfinite(size_deg) or not 0 < size_deg <= 0.25:
        raise ValueError("Cutout size must be between 0 and 0.25 degrees")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / (hashlib.sha1(query.encode()).hexdigest() + ".json")
    if use_cache and cache_file.exists() and time.time() - cache_file.stat().st_mtime < QUERY_CACHE_SECONDS:
        rows = json.loads(cache_file.read_text())
    else:
        rows = (tap or _run_tap)(query)
        rows = [[str(u), float(a), float(b), str(c)] for u, a, b, c in rows]
        cache_file.write_text(json.dumps(rows))
    return deduplicate(rows_to_exposures(rows, ra, dec, size_deg))


def list_collections():
    """DR1 may rename collections: discover them instead of hard-coding."""
    from astroquery.ipac.irsa import Irsa
    return Irsa.list_collections(servicetype="SIA", filter="spherex")
