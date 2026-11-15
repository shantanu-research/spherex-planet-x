# SPHEREx Planet X
Updated: 2026-11-15

## Verified (fresh venv, Python 3.13, all 42 project FITS downloaded and hash-verified)
- `python -m pytest tests backend/tests/test_offline.py -q`: 51 passed, 0 skipped (real-FITS tests run).
- `node tests/test_frontend.cjs`: passed.
- `python scripts/validate_observations.py`: reproduces `docs/validation.json` with no diff.
- Server run locally: `/api/health`, `/api/targets`, `/api/frames`, `/api/validation`, `/api/spectrum` return 200; `/api/export/mp4` returns real H.264 (25 frames).
- Browser (Chromium) at 1440px and 390px: real FITS renders, no console errors, no horizontal scroll.

## Not done / external
- **No public deployment yet.** Docker image builds and serves locally (verified: index, /api/health, /api/frames, MP4 export). Render needs the owner to click the README deploy button or connect the repo; no account access from here.
- Scientific limits are unchanged and documented in README: no PSF-fit WCS refinement, no independent astrometric validation, no discovery claim.
- `/api/spectrum?q=rw_aur` returns `unavailable` for the default detector (apertures masked/outside); this is reported honestly, not substituted.
