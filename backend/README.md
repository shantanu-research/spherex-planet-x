# SPHEREx Flipbook – data pipeline and backend

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

## Exposure fields (shared with the processing, spectra and viewer modules)
`image_url, cutout_url, t_start_mjd, t_end_mjd, t_start_iso, detector, release, visit` (+ `file_url, cached, error` from /api/cutouts)

## Files
- `irsa/archive.py` – TAP query (spherex.artifact JOIN spherex.plane, IRSA tutorial pattern), dedupe across releases
- `irsa/visits.py` – split into visits at gaps > 30 days
- `irsa/cutouts.py` – parallel download with retries and disk cache (`cache/`)
- `irsa/api.py` – FastAPI app
- `scripts/check_irsa.py` – real-archive check; writes `notes/real_header.txt` and `notes/plane_columns.txt`

Data: NASA SPHEREx via NASA/IPAC Infrared Science Archive (IRSA).
