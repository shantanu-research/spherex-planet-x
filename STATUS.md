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

## Added this session
- "Data as of" date in the Observations tab; reference molecular band positions labelled "(ref)" on real spectra; "Flag something interesting" button (local JSON download). Browser-verified.
- README "Who built what" rewritten from the Drive roles document. Track 1 name is blank there, Track 3 commits are under Shantanu's name in Git, and "Pikq P" is not in the roles doc: **team must confirm**.

## Still open (cannot be fixed from here)
- Public URL (needs the owner's Render/hosting sign-in).
- Gaia/CatWISE overlays could not be verified live: from this sandbox IRSA returned 502 and Gaia was unreachable. Re-check on the deployed site.
- Not implemented: known-asteroid markers (needs SkyBoT/SB Ident network access), a manual QR2/QR3/DR1 release selector.
- NASA's official 2026 submission/judging guides are not in the Drive; check demo limits and AI-disclosure rules there.
