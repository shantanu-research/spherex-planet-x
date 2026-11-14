# Fainter variables near the north ecliptic pole (2026-11-14)

Goal: a real SPHEREx light curve (R Draconis saturates in every frame).

## Candidate search
- AAVSO VSX (`B/vsx/vsx`, via the CfA VizieR mirror; CDS TAP timed out) within 10 deg of the NEP (RA 270, Dec +66.56):
  18,750 variables -> 941 long-period types (M, SR*, L*, RV*) -> 394 with amplitude >= 0.5 mag.
- Cross-matched with 2MASS PSC (IRSA `fp_psc`, K < 11, 4" radius) -> `notes/vsx_lpv_candidates_nep.csv`.

## Saturation probe (one mid-survey cutout per detector, FLAGS in the r=2.5 px aperture)
| star | 2MASS K | result |
|---|---|---|
| X Dra, W Dra (Miras, 0.8 deg from NEP) | 5.5, 5.7 | OVERFLOW/BLOOM on D1-D6 |
| V0566 Dra (Mira) | 6.5 | OVERFLOW on D1-D6 |
| IZ Dra (Mira, P 333 d) | 7.5 | OVERFLOW on D1-D4, **clean on D5/D6** |
| V0396 Dra (LB) | 8.4 | borderline: D2-D4 OVERFLOW, D1/D5/D6 clean |
| ASASSN-V J181412.05+643946.3 (SR, P 164 d) | 9.9 | **clean on D1-D6** (D1 frame had NONFUNC) |

Rule of thumb: SPHEREx point sources saturate on D1-D4 for K brighter than ~8.5; use K >= 9 stars, or D5/D6 for red stars.

## Light curves (`python scripts/precache_timelapse.py "<name>" D..`, plots via `scripts/plot_lightcurve.py`)
**ASASSN-V J181412.05+643946.3** (2.4 deg from NEP, 21,714 exposures, 527 d):
| det | wavelength | frames | usable | flux_norm range |
|---|---|---|---|---|
| D2 | 1.240 um | 76 | 66 | 0.84-1.07 |
| D3 | 1.834 um | 58 | 53 | 0.75-1.18 |
| D6 | 4.603 um | 58 | 52 | 0.87-1.09 |
Clear, repeating variation in all three bands: minima around Jun 2025, Nov 2025, May 2026 (spacing ~160 d,
consistent with the VSX period of 164 d). Amplitude larger at 1.8 um (~+-20%) than at 4.6 um (~+-10%).
**Check:** comparison star of similar brightness 1.4' away (RA 273.604, Dec +64.665), same frames, same aperture:
scatter 2.3% (D2) / 5.4% (D3) vs target 5.9% / 11.5%, correlation with target ~0 -> the variation is the star's, not the pipeline's.
Plot: `notes/asassn-v-j181412-05-643946-3_lightcurve.png`.

**IZ Dra** (Mira, 6.9 deg from NEP): D6 4.567 um, 28 weekly frames, 24 usable, flux 0.76-1.19 over 484 d: rise to
max ~Jul 2025, decline to Oct 2025, max again ~Jul-Aug 2026 (consistent with P ~333 d). 4 frames near maximum flagged
saturated. D5 only 11 frames (2 usable). Plot: `notes/iz-dra_lightcurve.png`.

Caveats: flux is relative aperture photometry (MJy/sr x px, background-subtracted), normalised to the median of usable
frames; no colour/aperture corrections; flagged frames are shown but never used or interpolated.
