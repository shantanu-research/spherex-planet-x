"""Data backend API.

Run:  uvicorn irsa.api:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import archive, cutouts, visits

app = FastAPI(title="SPHEREx Flipbook - data API")
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


@app.get("/api/collections")
def collections():
    try:
        return {"collections": [str(r) for r in archive.list_collections()]}
    except Exception as ex:
        raise HTTPException(502, f"{type(ex).__name__}: {ex}")
