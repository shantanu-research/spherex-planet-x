"""
SPHEREx Planet X Challenge - Realistic Multi-Epoch Level-2 Simulation Generator
Generates physically grounded SPHEREx multi-visit cutouts including the real LVF color-shift phenomenon.
"""

from typing import List, Dict, Any, Tuple
import math
import random
import hashlib
from ..orchestration.catalog import BENCHMARK_TARGETS
from ..orchestration.resolver import propagate_coordinates, SPHEREx_PIXEL_SCALE_ARCSEC
from ..calibration.band_balancer import DETECTOR_SPECS, get_channel_wavelength

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

def get_star_spectral_slope(wavelength_um: float, teff: float) -> float:
    """Computes color slope across the infrared LVF bandpass."""
    # Rayleigh-Jeans / Wien approx relative to 2.5 um
    # F ~ lambda^(-4) in RJ or Wien exponential
    l_ratio = wavelength_um / 2.5
    exponent = 14387.77 / (wavelength_um * teff)
    norm_exp = 14387.77 / (2.5 * teff)
    
    # Relative brightness variation across the LVF channel
    f_l = (l_ratio ** -5) / (math.exp(min(40.0, exponent)) - 1.0)
    f_norm = (1.0 ** -5) / (math.exp(min(40.0, norm_exp)) - 1.0)
    return max(0.2, min(3.0, f_l / max(1e-9, f_norm)))

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
      - Dithered raw exposures with stepped LVF spectral channels
      - Realistic LVF 20-30% color-shift brightness flicker on stationary stars
      - Moving target displacement based on exact proper motion & parallax
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

    field_stars = generate_stationary_field_stars(seed=42 + int.from_bytes(hashlib.sha256(target_key.encode()).digest()[:4], "big") % 1000, grid_size=grid_size, n_stars=24)
    
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
        
        # In a real SPHEREx survey pass, pointings step across spectral channels.
        # Exposures within each visit sample channels 4, 5, 6, 7.
        # Single exposures fluctuate by 20-30% due to LVF color slope;
        # Akhilesh's Band-Balanced stacking equalizes them across C_shared.
        exposures = []
        dithers = [
            (0.0, 0.0, 4),
            (0.4, -0.3, 5),
            (-0.3, 0.5, 6),
            (0.2, 0.4, 7)
        ]
        
        for exp_idx, (dith_x, dith_y, channel_num) in enumerate(dithers):
            ch_lambda, ch_bw = get_channel_wavelength(detector, channel_num)
            
            # Create base exposure image
            exp_img = [[0.0 for _ in range(grid_size)] for _ in range(grid_size)]
            var_img = [[0.25 for _ in range(grid_size)] for _ in range(grid_size)]
            zodi_img = [[1.85 for _ in range(grid_size)] for _ in range(grid_size)]  # Zodiacal light ~1.8 MJy/sr
            flag_img = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
            
            # 1. Add background noise + zodi
            rng = random.Random(v_idx * 100 + exp_idx * 10)
            for y in range(grid_size):
                for x in range(grid_size):
                    # Background noise sigma ~ 0.35 MJy/sr
                    noise = rng.gauss(0.0, 0.35)
                    exp_img[y][x] = zodi_img[y][x] + noise
                    
            # 2. Add stationary background stars (with LVF spectral slope flicker!)
            for s in field_stars:
                # The LVF color-shift phenomenon:
                # A star observed at different channels exhibits a spectral slope variation of 20-30%!
                slope = get_star_spectral_slope(ch_lambda, s["teff"])
                # Raw flicker variation across dither channels (20-30% as documented in Section 1.1)
                flicker_factor = 0.75 + 0.50 * (channel_num / 17.0) * (s["teff"] / 5000.0)
                star_flux = s["base_flux"] * flicker_factor
                add_psf_source(exp_img, s["x"] + dith_x, s["y"] + dith_y, star_flux)
                # Mark cataloged source in FLAGS (MP_SOURCE = 1 << 21)
                flag_x = int(round(s["x"]))
                flag_y = int(round(s["y"]))
                if 0 <= flag_x < grid_size and 0 <= flag_y < grid_size:
                    flag_img[flag_y][flag_x] |= (1 << 21)
                    
            # 3. Add moving target
            # For variable stars (RW Aur, R Dra), modulate flux over time
            current_target_flux = target_base_flux
            if target_id == "rw_aur":
                # Dust occultation dimming
                dimming = [1.0, 0.25, 0.80, 0.40][v_idx % 4]
                current_target_flux *= dimming
            elif target_id == "r_dra":
                # Mira pulsation
                phase = (v_def["mjd"] - 60000.0) / 245.6
                current_target_flux *= (0.3 + 1.2 * math.cos(2.0 * math.pi * phase)**2)
                
            add_psf_source(exp_img, target_x_px + dith_x, target_y_px + dith_y, current_target_flux)
            # Mark target as source in flags
            tx = int(round(target_x_px))
            ty = int(round(target_y_px))
            if 0 <= tx < grid_size and 0 <= ty < grid_size:
                flag_img[ty][tx] |= (1 << 21)

            # 4. Inject few random bad pixels (hot pixel, cosmic ray)
            for _ in range(3):
                bx = rng.randint(2, grid_size - 3)
                by = rng.randint(2, grid_size - 3)
                exp_img[by][bx] += 45.0
                flag_img[by][bx] |= (1 << 10)  # MP_HOT from spherex_flag_bits.csv

            exposures.append({
                "exp_id": f"{target_id}_{detector}_v{v_idx+1}_exp{exp_idx+1}",
                "mjd_mid": v_def["mjd"] + exp_idx * 0.05,
                "wavelength_um": ch_lambda,
                "bandwidth_um": ch_bw,
                "channel": channel_num,
                "dither_x": dith_x,
                "dither_y": dith_y,
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
