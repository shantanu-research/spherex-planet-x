"""
SPHEREx Planet X Challenge - Realistic Multi-Epoch Level-2 Simulation Generator
Generates physically grounded SPHEREx multi-visit cutouts including the real LVF color-shift phenomenon.
"""

from typing import List, Dict, Any, Tuple
import math
import random
import zlib
from ..track1_orchestration.catalog import BENCHMARK_TARGETS
from ..track1_orchestration.resolver import propagate_coordinates, SPHEREx_PIXEL_SCALE_ARCSEC
from ..track2_calibration.band_balancer import DETECTOR_SPECS, get_channel_wavelength

def generate_stationary_field_stars(
    seed: int,
    grid_size: int = 64,
    n_stars: int = 25
) -> List[Dict[str, Any]]:
    """Generates a fixed set of bright, stationary Gaia DR3 reference stars."""
    rng = random.Random(seed)
    stars = []
    margin = 8
    for i in range(n_stars):
        x = rng.uniform(margin, grid_size - margin)
        y = rng.uniform(margin, grid_size - margin)
        # Avoid placing star directly at image center (where target is)
        if math.hypot(x - grid_size/2, y - grid_size/2) < 6.0:
            x += 9.0
        # Color temperature: 3200 K to 7500 K
        teff = rng.uniform(3200.0, 7500.0)
        # High SNR Gaia reference stars (25 to 55 MJy/sr)
        flux = rng.uniform(25.0, 55.0)
        stars.append({
            "id": i + 1,
            "x": x,
            "y": y,
            "teff": teff,
            "base_flux": flux
        })
    return stars

def add_psf_source(
    image: List[List[float]],
    cx: float,
    cy: float,
    peak_flux: float,
    fwhm_px: float = 2.1
):
    """Adds a 2D Gaussian point spread function (PSF) to an image array."""
    h = len(image)
    w = len(image[0])
    sigma = fwhm_px / 2.355
    sigma2 = 2.0 * (sigma ** 2)
    radius = int(math.ceil(fwhm_px * 2.5))
    
    min_x = max(0, int(cx - radius))
    max_x = min(w - 1, int(cx + radius))
    min_y = max(0, int(cy - radius))
    max_y = min(h - 1, int(cy + radius))
    
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            dist2 = (x - cx)**2 + (y - cy)**2
            val = peak_flux * math.exp(-dist2 / sigma2)
            image[y][x] += val

def get_star_spectral_slope(
    wavelength_um: float,
    teff: float,
    reference_um: float = 2.5,
    clamp: Tuple[float, float] = (0.05, 20.0),
) -> float:
    """
    Relative surface brightness of a blackbody at `wavelength_um` versus `reference_um`.

    Uses B_nu (per unit frequency, matching SPHEREx MJy/sr units):
        B_nu(lambda, T) ∝ lambda^-3 / (exp(hc / lambda k T) - 1)
    This is the physical origin of LVF flicker: the same star looks brighter or
    fainter depending on which wavelength the filter shows it at, and the size of
    the effect depends on the star's own colour (temperature).
    """
    c2 = 14387.77  # hc/k in um*K

    def b_nu(lam: float) -> float:
        x = c2 / (lam * teff)
        if x > 700.0:
            return 0.0
        return (lam ** -3) / math.expm1(x)

    ref = b_nu(reference_um)
    if ref <= 0.0:
        return clamp[0]
    return max(clamp[0], min(clamp[1], b_nu(wavelength_um) / ref))


def _stable_seed(*parts: Any) -> int:
    """Deterministic seed (Python's hash() is randomised per process)."""
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))


def plan_visit_shots(
    rng: random.Random,
    n_bands: int = 17,
    n_sweeps: int = 2,
    half_band_shift: bool = False,
    position_jitter: float = 0.2,
    n_repeat_shots: int = 4,
    dropped_bands: Tuple[int, ...] = (),
) -> List[float]:
    """
    Plans where on the LVF the target lands for every shot in one visit.

    Returns fractional band positions in [0, n_bands): position p means the target is seen
    at lambda = lmin + p * band_width, i.e. inside band floor(p) + 1.

    - Each sweep steps once across all bands, starting at a random band (time order).
    - Surveys 3-4 are shifted by half a band, so shots land near band edges and fall
      into either neighbouring band: some bands get 2 shots, some get none.
    - A few random repeat shots make shots-per-band uneven between visits.
    - `dropped_bands` (1-based) simulates bad or missing shots in this visit.
    """
    offset = 0.5 if half_band_shift else 0.0
    eps = 1e-6
    positions: List[float] = []
    for _ in range(n_sweeps):
        start = rng.randrange(n_bands)
        for i in range(n_bands):
            k = (start + i) % n_bands
            p = k + 0.5 + offset + rng.uniform(-position_jitter, position_jitter)
            positions.append(min(n_bands - eps, max(0.0, p)))
    for _ in range(n_repeat_shots):
        k = rng.randrange(n_bands)
        p = k + 0.5 + offset + rng.uniform(-position_jitter, position_jitter)
        positions.append(min(n_bands - eps, max(0.0, p)))
    if dropped_bands:
        positions = [p for p in positions if int(p) + 1 not in dropped_bands]
    return positions

def generate_simulated_target_visits(
    target_key: str,
    detector: str = "D6",
    grid_size: int = 64,
    n_visits: int = 4
) -> Dict[str, Any]:
    """
    Generates realistic SPHEREx multi-epoch dataset for the specified target.
    Includes:
      - 4 survey visits spanning 18 months (May 2025 to Nov 2026)
      - ~34-38 shots per visit: two sweeps across the 17 LVF bands plus random repeats,
        so shots-per-band is uneven between visits
      - Surveys 3-4 shifted by half a band; visit 2 is missing bands 6 and 13
      - Each shot records the continuous wavelength at the target (`wavelength_um`);
        the band label is left for Track 2 Step 1 to assign
      - LVF flicker from each star's own blackbody colour (B_nu), not a fixed factor:
        naive single-shot scatter is ~10-15% on average, up to ~20% for the reddest/bluest stars
      - Deterministic: same target + detector always gives the same data
      - Moving target displacement based on proper motion & parallax
      - Modeled ZODI background + detector noise
    """
    target = BENCHMARK_TARGETS.get(target_key, BENCHMARK_TARGETS["WISE 0855-0714"])
    target_id = target["id"]
    
    # 4 Survey Visit Epochs
    # V1: May 2025 (MJD 60810, Year 2025.37)
    # V2: Nov 2025 (MJD 60995, Year 2025.88, 180 deg roll)
    # V3: May 2026 (MJD 61180, Year 2026.39, Nyquist step)
    # V4: Nov 2026 (MJD 61365, Year 2026.89)
    visit_definitions = [
        {"mjd": 60810.0, "epoch_yr": 2025.37, "date": "2025-05-15 10:20:00 UTC", "pass": "Survey 1"},
        {"mjd": 60995.0, "epoch_yr": 2025.88, "date": "2025-11-16 14:45:00 UTC", "pass": "Survey 2"},
        {"mjd": 61180.0, "epoch_yr": 2026.39, "date": "2026-05-20 08:15:00 UTC", "pass": "Survey 3 (Nyquist)"},
        {"mjd": 61365.0, "epoch_yr": 2026.89, "date": "2026-11-21 16:30:00 UTC", "pass": "Survey 4"}
    ][:n_visits]

    field_stars = generate_stationary_field_stars(
        seed=42 + _stable_seed(target_key) % 1000, grid_size=grid_size, n_stars=24
    )
    
    # Target starting position in stamp center
    u0 = grid_size / 2.0
    v0 = grid_size / 2.0
    
    # Target intrinsic brightness in this detector
    det_spec = DETECTOR_SPECS.get(detector, DETECTOR_SPECS["D6"])
    det_lmin = det_spec["lmin"]
    det_lmax = det_spec["lmax"]
    det_mid = 0.5 * (det_lmin + det_lmax)
    
    # Calculate target flux based on temperature and peak detector
    teff = target["teff_k"]
    if target_id == "wise_0855":
        # Ultra cold 250 K brown dwarf: Faint in D1-D3, rises sharply in D4, huge peak in D5/D6
        flux_multipliers = {"D1": 0.0, "D2": 0.05, "D3": 0.2, "D4": 3.5, "D5": 14.0, "D6": 24.0}
    elif target_id == "planet_x_candidate":
        # 42 K TNO: undetectable in D1-D4, weak in D5, visible in D6
        flux_multipliers = {"D1": 0.0, "D2": 0.0, "D3": 0.0, "D4": 0.0, "D5": 1.2, "D6": 8.5}
    elif target_id == "barnards_star":
        # M4V 3134 K star: bright across all, peaking in D1/D2
        flux_multipliers = {"D1": 32.0, "D2": 28.0, "D3": 20.0, "D4": 12.0, "D5": 6.0, "D6": 4.0}
    elif target_id == "eps_indi_b":
        # T dwarf 1100 K: peak in D3, strong D5/D6
        flux_multipliers = {"D1": 0.8, "D2": 4.5, "D3": 22.0, "D4": 9.0, "D5": 16.0, "D6": 18.0}
    else:
        flux_multipliers = {"D1": 15.0, "D2": 18.0, "D3": 16.0, "D4": 14.0, "D5": 12.0, "D6": 10.0}
        
    target_base_flux = flux_multipliers.get(detector, 12.0)

    # Reference epoch for target motion
    ref_epoch = visit_definitions[0]["epoch_yr"]
    
    visits = []
    
    for v_idx, v_def in enumerate(visit_definitions):
        t_yr = v_def["epoch_yr"]
        dt_yr = t_yr - ref_epoch
        
        # Calculate target position displacement in arcsec & pixels
        # +x is East (-RA), +y is North (+Dec)
        # pm_ra_mas is mu_alpha * cos(dec)
        pm_ra = target["pm_ra_mas"]
        pm_dec = target["pm_dec_mas"]
        
        # Annual parallax loop
        par_mas = target.get("parallax_mas", 0.0)
        frac = t_yr - math.floor(t_yr)
        par_dx_arcsec = (par_mas / 1000.0) * math.sin(2.0 * math.pi * frac)
        par_dy_arcsec = (par_mas / 1000.0) * math.cos(2.0 * math.pi * frac) * 0.4
        
        target_dx_arcsec = -(pm_ra / 1000.0 * dt_yr) + par_dx_arcsec
        target_dy_arcsec = (pm_dec / 1000.0 * dt_yr) + par_dy_arcsec
        
        target_x_px = u0 + (target_dx_arcsec / SPHEREx_PIXEL_SCALE_ARCSEC)
        target_y_px = v0 + (target_dy_arcsec / SPHEREx_PIXEL_SCALE_ARCSEC)
        
        # Plan where on the LVF the target lands in each shot of this visit.
        # Surveys 3-4 are shifted by half a band; visit 2 loses two bands (bad shots).
        visit_rng = random.Random(_stable_seed(target_key, detector, "visit", v_idx))
        dropped = (6, 13) if v_idx == 1 else ()
        shot_positions = plan_visit_shots(
            visit_rng,
            half_band_shift=(v_idx >= 2),
            dropped_bands=dropped,
        )
        band_width = (det_lmax - det_lmin) / 17.0
        noise_sigma = 0.35  # MJy/sr per pixel
        exposures = []

        for exp_idx, band_pos in enumerate(shot_positions):
            # Exact wavelength the target is seen at in this shot (continuous, not a band centre)
            shot_lambda = det_lmin + band_pos * band_width
            dith_x = visit_rng.uniform(-0.5, 0.5)
            dith_y = visit_rng.uniform(-0.5, 0.5)

            exp_img = [[0.0 for _ in range(grid_size)] for _ in range(grid_size)]
            var_img = [[noise_sigma ** 2 for _ in range(grid_size)] for _ in range(grid_size)]
            zodi_img = [[1.85 for _ in range(grid_size)] for _ in range(grid_size)]  # Zodiacal light ~1.8 MJy/sr
            flag_img = [[0 for _ in range(grid_size)] for _ in range(grid_size)]

            # 1. Background: ZODI + detector noise
            rng = random.Random(_stable_seed(target_key, detector, "exp", v_idx, exp_idx))
            for y in range(grid_size):
                for x in range(grid_size):
                    exp_img[y][x] = zodi_img[y][x] + rng.gauss(0.0, noise_sigma)

            # 2. Stationary field stars. Their brightness follows their own blackbody colour at
            #    the wavelength of this shot: this IS the LVF flicker (no fudge factor).
            for s in field_stars:
                colour = get_star_spectral_slope(shot_lambda, s["teff"], reference_um=det_mid)
                add_psf_source(exp_img, s["x"] + dith_x, s["y"] + dith_y, s["base_flux"] * colour)
                # Mark cataloged source in FLAGS (MP_SOURCE = 1 << 21)
                flag_x = int(round(s["x"]))
                flag_y = int(round(s["y"]))
                if 0 <= flag_x < grid_size and 0 <= flag_y < grid_size:
                    flag_img[flag_y][flag_x] |= (1 << 21)

            # 3. Target: intrinsic variability (RW Aur, R Dra) times its own colour at this wavelength
            current_target_flux = target_base_flux
            if target_id == "rw_aur":
                # Dust occultation dimming
                dimming = [1.0, 0.25, 0.80, 0.40][v_idx % 4]
                current_target_flux *= dimming
            elif target_id == "r_dra":
                # Mira pulsation
                phase = (v_def["mjd"] - 60000.0) / 245.6
                current_target_flux *= (0.3 + 1.2 * math.cos(2.0 * math.pi * phase)**2)
            current_target_flux *= get_star_spectral_slope(shot_lambda, teff, reference_um=det_mid)

            add_psf_source(exp_img, target_x_px + dith_x, target_y_px + dith_y, current_target_flux)
            tx = int(round(target_x_px))
            ty = int(round(target_y_px))
            if 0 <= tx < grid_size and 0 <= ty < grid_size:
                flag_img[ty][tx] |= (1 << 21)

            # 4. A few hot pixels / cosmic rays per shot
            for _ in range(3):
                bx = rng.randint(2, grid_size - 3)
                by = rng.randint(2, grid_size - 3)
                exp_img[by][bx] += 45.0
                flag_img[by][bx] |= (1 << 10)  # MP_HOT from spherex_flag_bits.csv

            exposures.append({
                "exp_id": f"{target_id}_{detector}_v{v_idx+1}_exp{exp_idx+1}",
                "mjd_mid": v_def["mjd"] + exp_idx * 0.02,
                # Step 1 input: wavelength at the target. The band label is assigned by
                # band_balancer.label_exposure_spectral_channel, not hard-coded here.
                "wavelength_um": round(shot_lambda, 5),
                "lambda_at_target": round(shot_lambda, 5),
                "bandwidth_um": round(band_width, 5),
                "dither_x": round(dith_x, 3),
                "dither_y": round(dith_y, 3),
                "image": exp_img,
                "variance": var_img,
                "zodi": zodi_img,
                "flags": flag_img
            })

        visits.append({
            "visit_id": f"V{v_idx + 1}",
            "visit_index": v_idx + 1,
            "mjd_mid": v_def["mjd"],
            "date_utc": v_def["date"],
            "survey_pass": v_def["pass"],
            "target_pos_px": (round(target_x_px, 2), round(target_y_px, 2)),
            "target_displacement_px": (round(target_x_px - u0, 2), round(target_y_px - v0, 2)),
            "exposures": exposures
        })

    return {
        "status": "success",
        "target_key": target_key,
        "target_metadata": target,
        "detector": detector,
        "grid_size": grid_size,
        "n_visits": len(visits),
        "field_stars": field_stars,
        "visits": visits
    }
