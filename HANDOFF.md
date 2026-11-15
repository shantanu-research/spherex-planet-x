# Handoff: SPHEREx Sky Flipbook

Team Overdrive · NASA Space Apps Challenge 2026 · Planet X and SPHEREx challenge · Pune local event
Updated 2026-11-15. Submission deadline: **15 Nov 2026, 11:59 pm IST** on spaceappschallenge.org.

## Links

| What | Where |
| --- | --- |
| Live site | https://spherex-planet-x-i008.onrender.com |
| Health check (open first to wake it) | https://spherex-planet-x-i008.onrender.com/api/health |
| Repository | https://github.com/shantanu-research/spherex-planet-x (branch `main`) |
| Render service | https://dashboard.render.com/web/srv-dbsnq5k9v7es73b5jme0 (free plan, Singapore) |
| Demo video (28 s) | `docs/demo/walkthrough.mp4` |
| Project description | `docs/submission/project.md` |
| Mission patch | `frontend/assets/mission-patch.svg` |

## Before you submit tonight

1. Open the health check link and wait for `"status": "online"`. The free plan sleeps after ~15 min idle; waking took ~2 minutes.
2. Confirm the "Who built what" section in `README.md` with the team (taken from the Drive roles doc: Malhar Tamhankar Track 1, Akhilesh Rohit Bhosale Track 2, Amrita Patil Track 3, Shantanu Pawar Track 4).
3. Submit on spaceappschallenge.org with: live link, GitHub link, `docs/demo/walkthrough.mp4`, and the text of `docs/submission/project.md`.
4. Check the video and links open in a private browser window without login.

## Run locally

```bash
git clone https://github.com/shantanu-research/spherex-planet-x.git
cd spherex-planet-x
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python scripts/download_observations.py   # 42 FITS files, ~220 MB, SHA-256 verified
python -m backend.server 8080
```

Open http://localhost:8080. Needs Python 3.12+, Node.js (frontend test only) and FFmpeg (MP4 export).
Docker: `docker build -t spherex-flipbook . && docker run --rm -p 8080:8080 spherex-flipbook`.

## Checks (all passing on commit `e04ceb1` or later)

```bash
python -m pytest tests backend/tests/test_offline.py -q   # 58 passed with FITS downloaded
node tests/test_frontend.cjs
python scripts/validate_observations.py                   # regenerates docs/validation.json, no diff
```

- GitHub Actions (`.github/workflows/test.yml`): `test` and `docker` jobs both green.
- A 72-check browser audit of every control (wipe drag by mouse/touch/after zoom, speed slider,
  playback rate, hover readout, all modes/detectors/presets, exports, share/embed, URL state,
  mobile layout, no console errors) passed locally and on the live site. The script lived in the
  cloud session's scratch space and is not in the repo; recreate it if needed.

## Deploying changes

Render is **not** auto-deploying on push (no GitHub webhook reached it). After pushing to `main`:
Render dashboard → the service → **Manual Deploy → Deploy latest commit**. Or reconnect the
GitHub repo in the service settings to restore auto-deploy. Build takes ~3–4 minutes.

## What's built

- Coordinate input (decimal, `hh:mm:ss ±dd:mm:ss`, and `08h55m10.831s -7d14m42.53s`), object names via CDS Sesame, and five test-target presets plus a clearly labelled simulated field. Coordinates within 1 arcmin of a test target load its installed FITS.
- Flipbook of real SPHEREx Level-2 data: visit blink, longest baseline, difference sequence, motion-tracked, false colour, wavelength-matched, individual exposures, shift-and-stack. Unavailable comparisons say why.
- Wipe comparison (drag or slider), zoom/pan, reticle, WCS compass, trail, mask display, hover coordinate readout, speed 1–15 fps, keyboard shortcuts.
- Pipeline strip showing what each of the four tracks produced for the current view.
- Spectrum from measured aperture fluxes with errors; molecular band positions marked as references only.
- Gaia DR3 / CatWISE overlay requests, observation table with "data as of" date.
- GIF/MP4/CSV export, shareable URL, iframe embed, "Flag something interesting" (local JSON).
- Space Apps brand styling, original team mission patch, SPHEREx logo (credit NASA/JPL-Caltech), Space Apps logo; NASA insignia deliberately not used.

## Known limits and open items

- **IRSA outage (15 Nov):** IRSA's TAP and SIA services returned HTTP 502 (even `/TAP/availability`), from the cloud sandbox and from Render. New-coordinate searches and Gaia/CatWISE overlays fail until IRSA recovers; the site says so. Presets and test-target coordinates work from installed data. Re-test a far field such as `10, 20` later.
- Not built: Aladin Lite map, known-asteroid markers, manual QR2/QR3/DR1 selector.
- Science limits are listed in `README.md` ("Scientific interpretation"): no PSF-fit WCS refinement, no independent astrometric validation, no discovery or molecular-detection claim.
- Free-plan memory limits were not load-tested.

## Branding and permissions

- Space Apps logo: unaltered, from the June 2026 brand guide (`frontend/assets/spaceapps-logo-2026-white.png`).
- SPHEREx logo: Caltech SPHEREx image use policy, credit "Courtesy NASA/JPL-Caltech", no endorsement implied.
- NASA meatball, worm and seal: not used (need NASA written permission; Space Apps guide says not to use NASA official branding).
- Site notice reads: "NASA Space Apps Challenge 2026 project · Team Overdrive … This website is not operated by NASA, JPL, Caltech or IPAC."

## Repository map

| Path | Contents |
| --- | --- |
| `backend/server.py` | HTTP server and API (`/api/frames`, `/api/spectrum`, `/api/observations`, `/api/export/*`, …) |
| `backend/real_pipeline.py`, `backend/science.py` | FITS loading, masking, registration, band balancing, measurements |
| `backend/targets.py` | Coordinate/name resolution and preset matching |
| `backend/track1/` | IRSA archive queries, visits, cutouts |
| `frontend/index.html` (landing), `frontend/viewer.html`, `frontend/js/`, `frontend/css/style.css` | Viewer UI |
| `frontend/assets/` | Mission patch, SPHEREx and Space Apps logos |
| `tests/` | Python and frontend tests |
| `docs/` | Validation report, demo video, screenshot, submission text |
| `Dockerfile`, `render.yaml` | Deployment |
