# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing codebase: static HTML/CSS/JS in `frontend/`, served by the Python server in `backend/server.py`. No framework; no build step. Deployed on Render (free plan) from a Docker image.

## Users

- Primary: NASA Space Apps Challenge 2026 judges and reviewers, who open the live link once, quickly, to decide whether the project works and is honest.
- Secondary: other participants and astronomy-curious visitors who arrive from the submission or the GitHub repository.
- The viewer itself is a working tool for inspecting SPHEREx infrared sky images across observation epochs.

## Product Purpose

SPHEREx Sky Flipbook lets a user blink real SPHEREx Level-2 images from different dates and wavelengths and see which apparent changes are motion, which are only wavelength differences from SPHEREx's spatially varying filter, and which cannot be told. Success on the landing page: a judge understands the idea in seconds and opens the viewer.

## Positioning

It treats wavelength as a confound, not an afterthought: unavailable or unsafe comparisons are refused with a reason instead of being filled in, and every view shows its source files, dates, masks and measurement limits.

## Operating Context

NASA Space Apps Challenge 2026, Pune local event, challenge "Planet X and SPHEREx". Submission deadline 15 Nov 2026, 11:59 pm IST. Team Overdrive. Four tracks: data pipeline and backend, image processing, spectra and science validation, viewer and demo.

## Capabilities and Constraints

- 42 SPHEREx FITS files across five test fields, plus one clearly labelled simulated field; 41 files have usable pixels in the default fields.
- Eight viewing modes, wipe comparison, zoom, spectra from measured apertures, Gaia DR3 and CatWISE overlays, GIF/MP4/CSV export, shareable and embeddable URLs.
- NASA's archive (IRSA) was returning errors on 15 Nov: new-coordinate searches and overlays may fail; the five installed test targets work.
- Not claimed: no Planet X detection, no molecular identification, no independent astrometric validation.
- Not built: Aladin Lite map, known-asteroid markers, manual QR2/QR3/DR1 selector.

## Brand Commitments

- NASA Space Apps Challenge brand palette (deep blue, neon yellow, rocket red) and logo, unaltered, from the June 2026 brand guide.
- SPHEREx logo used under Caltech's image policy, credit "Courtesy NASA/JPL-Caltech", no endorsement implied.
- NASA meatball, worm and seal are never used. Required notice: "This website is not operated by NASA, JPL, Caltech or IPAC."
- Original team mission patch (`frontend/assets/mission-patch.svg`).
- Visual direction pinned by the user for the landing page: inspired by NASA's own web conventions (confirmed 2026-11-15).

## Evidence on Hand

- Real data demo: `docs/demo/flipbook-wise0855.gif`, `docs/demo/walkthrough.mp4` (28 s), `docs/screenshot.png`.
- Validation report `docs/validation.json`, observation manifest `data/observation-manifest.json`.
- Team roles from README "Who built what"; team emails and LinkedIn URLs supplied by the team in chat on 2026-11-15.
- Absent: team photos, testimonials, usage numbers, press. Do not fabricate any.

## Product Principles

1. Honesty over spectacle: say what is unavailable and why.
2. The data leads: real images before illustrations.
3. Judges first: the viewer is one click from the first screen.
4. Every claim traces to a file, a date, or a source.
5. Team credit is specific: each person is tied to the work they did.

## Accessibility & Inclusion

Keyboard operable, visible focus, skip link, contrast of at least WCAG AA, `prefers-reduced-motion` respected, works at phone width.
