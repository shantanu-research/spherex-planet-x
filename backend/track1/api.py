"""Track 1 backend API.

Run:  uvicorn track1.api:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import archive, cutouts, visits

app = FastAPI(title="SPHEREx Flipbook - Track 1 data API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

cutouts.CUTOUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=cutouts.CUTOUT_DIR), name="files")


def _position(ra, dec, name):
    if name:
        from astropy.coordinates import SkyCoord
        try:
            c = SkyCoord.from_name(name)
        except Exception as ex:
            raise HTTPException(404, f"Could not resolve '{name}': {ex}")
        return c.ra.deg, c.dec.deg
    if ra is None or dec is None:
        raise HTTPException(400, "Give ra and dec (degrees) or name")
    return ra, dec


def _observations(ra, dec, name, size, det, tmin, tmax):
    ra, dec = _position(ra, dec, name)
    t0 = time.time()
    try:
        exps = archive.search(ra, dec, size, det, tmin, tmax)
    except Exception as ex:
        raise HTTPException(502, f"IRSA query failed: {type(ex).__name__}: {ex}")
    exps = visits.group_visits(exps)
    return ra, dec, exps, round(time.time() - t0, 2)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/observations")
def observations(ra: float | None = None, dec: float | None = None, name: str | None = None,
                 size: float = Query(0.083, gt=0, le=0.25, description="cutout size, degrees"),
                 det: str | None = Query(None, description="detector 1-6, e.g. D5"),
                 tmin: float | None = Query(None, description="start MJD"),
                 tmax: float | None = Query(None, description="end MJD")):
    ra, dec, exps, secs = _observations(ra, dec, name, size, det, tmin, tmax)
    return {"ra": ra, "dec": dec, "size_deg": size, "query_seconds": secs,
            "n_exposures": len(exps), "visits": visits.summarize(exps),
            "exposures": [e.to_dict() for e in exps]}


@app.get("/api/cutouts")
async def get_cutouts(ra: float | None = None, dec: float | None = None, name: str | None = None,
                      size: float = Query(0.083, gt=0, le=0.25),
                      det: str | None = None, tmin: float | None = None, tmax: float | None = None,
                      per_visit: int | None = Query(None, ge=1, le=500,
                                                    description="max frames per visit, evenly spaced"),
                      limit: int = Query(200, ge=1, le=1000,
                                         description="overall cap, shared evenly across visits")):
    ra, dec, exps, qsecs = _observations(ra, dec, name, size, det, tmin, tmax)
    n_available = len(exps)
    exps = visits.select_frames(exps, per_visit=per_visit, limit=limit)
    t0 = time.time()
    results = await cutouts.fetch_all([e.cutout_url for e in exps])
    frames = []
    for e, r in zip(exps, results):
        d = e.to_dict()
        d["file_url"] = f"/files/{r['file']}" if r["file"] else None
        d["cached"], d["error"] = r["cached"], r["error"]
        frames.append(d)
    return {"ra": ra, "dec": dec, "size_deg": size, "query_seconds": qsecs,
            "download_seconds": round(time.time() - t0, 2),
            "n_available": n_available,
            "visits": visits.summarize(exps),
            "n_ok": sum(f["file_url"] is not None for f in frames),
            "n_failed": sum(f["file_url"] is None for f in frames),
            "frames": frames}


@app.get("/api/timelapse")
async def timelapse_endpoint(
        ra: float | None = None, dec: float | None = None, name: str | None = None,
        det: str = Query(..., description="detector, e.g. D3"),
        every_days: float = Query(7.0, gt=0, le=365, description="one frame per this many days"),
        wave: float | None = Query(None, description="reference wavelength (um); default = best-covered channel"),
        tol: float | None = Query(None, description="wavelength tolerance (um); default = half a channel"),
        size: float = Query(0.1, gt=0, le=0.25),
        max_frames: int = Query(120, ge=2, le=400),
        download: bool = True):
    """Same-wavelength time-lapse sampled by date, plus a relative light curve."""
    from . import timelapse
    ra, dec, exps, qsecs = _observations(ra, dec, name, size, None, None, None)
    t0 = time.time()
    out = await timelapse.build_timelapse(exps, ra, dec, det, every_days=every_days, wave_um=wave,
                                          tol_um=tol, max_frames=max_frames, download=download)
    out["query_seconds"] = qsecs
    out["build_seconds"] = round(time.time() - t0, 1)
    return out


PRECACHE_DIR = cutouts.CUTOUT_DIR.parent / "targets"
TIMELAPSE_DIR = cutouts.CUTOUT_DIR.parent / "timelapse"


@app.get("/api/precached/timelapse")
def precached_timelapse(slug: str | None = None, det: str | None = None):
    """Time-lapses prepared by scripts/precache_timelapse.py."""
    import json
    if slug and det:
        f = TIMELAPSE_DIR / f"{slug}_{archive._detector_name(det)[-2:]}.json"
        if not f.exists():
            raise HTTPException(404, f"No pre-cached time-lapse for {slug} {det}")
        return json.loads(f.read_text())
    out = []
    for f in sorted(TIMELAPSE_DIR.glob("*.json")):
        m = json.loads(f.read_text())
        out.append({"slug": m.get("slug"), "detector": m["detector"], "n_frames": m["n_frames"],
                    "span_days": m["span_days"], "reference_wave_um": m["reference_wave_um"],
                    "n_usable_photometry": m["n_usable_photometry"]})
    return {"timelapses": out}


@app.get("/api/precached")
def precached(slug: str | None = None):
    """Demo targets prepared by scripts/precache.py (instant, works offline)."""
    import json
    if slug:
        f = PRECACHE_DIR / f"{slug}.json"
        if not f.exists():
            raise HTTPException(404, f"No pre-cached target '{slug}'")
        return json.loads(f.read_text())
    out = []
    for f in sorted(PRECACHE_DIR.glob("*.json")):
        m = json.loads(f.read_text())
        out.append({"slug": f.stem, "name": m["target"]["name"], "ra": m["ra"], "dec": m["dec"],
                    "n_exposures": m["n_exposures"], "n_visits": len(m["visits"]),
                    "detectors": list(m["frames_by_detector"]), "created_utc": m["created_utc"]})
    return {"targets": out}


@app.get("/api/collections")
def collections():
    try:
        return {"collections": [str(r) for r in archive.list_collections()]}
    except Exception as ex:
        raise HTTPException(502, f"{type(ex).__name__}: {ex}")
