# SPHEREx Flipbook – Track 1 (data pipeline and backend)

## Start
1. Double-click `setup.bat` (installs into `.venv`, runs tests, checks the real archive).
2. Double-click `run_server.bat`, then open http://localhost:8000/docs

## Endpoints
- `GET /api/observations?ra=..&dec=..` (or `name=..`) — exposures covering the position, grouped into visits.
  Optional: `size` (deg, default 0.083 = 5 arcmin), `det` (D1–D6), `tmin`/`tmax` (MJD).
- `GET /api/cutouts?...same params...&per_visit=4&limit=200` — picks frames so every visit is represented
  (`per_visit` = max per visit, evenly spaced in time; `limit` = overall cap shared evenly across visits),
  downloads them (8 at a time, cached) and returns a frame list; each frame's `file_url` is served under `/files/...`.
  Tip: ask for one detector (`det=D5`) — each cutout is ~4 MB, mostly PSF data.
- `GET /api/collections` — SPHEREx collections IRSA currently offers (DR1 check).
- `GET /api/precached` (list) or `/api/precached?slug=wise-0855-0714` — the demo targets prepared by
  `precache.bat`: position corrected for proper motion, visits, and frames per best detector. Instant, works offline.

## Pre-cache the demo targets (run on every machine that serves the demo)
Double-click `precache.bat` (~10 min). It reads `test_targets.csv` (repo `data/reference/`), moves each
target to its 2025.9 position using its proper motion, runs one archive search per target, downloads
4 frames per visit for each best detector (6 arcmin cutouts, ~1 GB total) and writes `cache/targets/*.json`.
Re-run it to fill any cutouts IRSA refused with 503 "busy"; finished downloads are kept.
Last run (2026-11-14): 5/5 targets, 234/234 cutouts.

## Exposure fields (agree these with Tracks 2–4)
`image_url, cutout_url, t_start_mjd, t_end_mjd, t_start_iso, detector, release, visit` (+ `file_url, cached, error` from /api/cutouts)

## Files
- `track1/archive.py` – TAP query (spherex.artifact JOIN spherex.plane, IRSA tutorial pattern), dedupe across releases
- `track1/visits.py` – split into visits at gaps > 30 days
- `track1/cutouts.py` – parallel download with retries and disk cache (`cache/`)
- `track1/api.py` – FastAPI app
- `scripts/check_irsa.py` – real-archive check; writes `notes/real_header.txt` and `notes/plane_columns.txt`

Data: NASA SPHEREx via NASA/IPAC Infrared Science Archive (IRSA).
