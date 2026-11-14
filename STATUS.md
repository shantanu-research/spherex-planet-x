# SPHEREx Planet X
Updated: 2026-11-14
- Discovery engine and multi-epoch visualizer; Python backend and static frontend.
- Public GitHub repository: https://github.com/shantanu-research/spherex-planet-x
- main pushed to origin and configured to track origin/main.
- Downloaded Drive archive, cache, and virtual environment excluded from Git.
- UI refined: larger image workspace, quieter controls, responsive layout.
- Fixed frontend astrometry response mismatch that blocked archive rendering.
- Explicit loading/error and missing-audit states; no new dependencies.
- UI changes and regression tests pushed to main (5508364).
- Public forks/PRs available; merge, squash and rebase enabled.
- Direct push/merge access requires named collaborators.
- Untracked backend orchestration files belong to other work.
- Verified at 390px and 1440px; archive/simulation, tabs, playback and frame step.
- Passed: node tests/test_frontend.cjs, JS syntax checks, git diff --check.
- Next: continue backend work; scientific pipeline not revalidated.

## Track 1 pre-cache (Malhar) - do this before every demo run
- On ANY machine that serves the demo (local or the public server): run `backend\precache.bat` once
  (or `python backend/scripts/precache.py`). Takes ~10 min, downloads ~1 GB into `backend/cache/` (git-ignored, so it does NOT come with the code).
- Re-run it if any cutouts failed (IRSA sometimes answers 503 "busy"); finished downloads are kept, only gaps re-download.
- It reads `data/reference/test_targets.csv` and corrects each target for proper motion (Barnard's Star ~4.5' north, WISE 0855 ~2' west of catalogue).
- Check: `GET /api/precached` should list 5 targets. Last run 2026-11-14: 5/5 targets, 234/234 cutouts.
- New (non-preset) positions still hit NASA live: ~15-70 s per new position, so the site needs a loading state.

## FLAG for Track 3 spectra: proper-motion position (from Track 1, 2026-11-14)
- `spectrum_extractor.extract_real_cutout_photometry` calls `archive.search(ra_deg, dec_deg, size_deg=0.083)` with the RAW catalogue position.
- Fast movers have moved since their catalogue epoch: Barnard's Star is ~4.5' north of its J2000 position, so it falls OUTSIDE a 5' cutout (+/-2.5') and its spectrum comes back empty. WISE 0855 is ~2' west (only just inside).
- Fix: use the propagated position, e.g. `from backend.track1.targets import load_targets` -> `t.position_at(2025.9)` (or the resolver's propagated coordinates), and `size_deg=0.1` (6').
- Bonus: same position + size as the pre-cache means the 234 cached cutouts are reused instead of hitting NASA live during the demo (or read `/api/precached?slug=...`).
