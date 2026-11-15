"""
SPHEREx Planet X Challenge - Target Catalog & Benchmark Definitions
Authoritative astrometric and astrophysical parameters for pre-defined benchmark targets.
"""

from typing import Dict, Any, List

BENCHMARK_TARGETS: Dict[str, Dict[str, Any]] = {
    "WISE 0855-0714": {
        "id": "wise_0855",
        "name": "WISE J085510.83-071442.5",
        "common_name": "WISE 0855-0714",
        "category": "Cold Brown Dwarf (Y-Dwarf)",
        "discovery_epoch": 2010.5,
        "ra_deg": 133.7951,        # 08h 55m 10.831s
        "dec_deg": -7.2451,        # -07d 14m 42.53s
        "pm_ra_mas": -8160.0,      # -8.16 arcsec/yr in ra * cos(dec)
        "pm_dec_mas": 660.0,       # +0.66 arcsec/yr in dec
        "parallax_mas": 464.0,     # 0.464 arcsec / 2.28 pc (4th closest system to Sun)
        "spectral_type": "Y2",
        "teff_k": 250,             # Coldest known brown dwarf (~250-285 K)
        "peak_detector": "D6",     # Peak thermal emission in 4.4 - 5.0 um
        "description": "Coldest known sub-stellar object (~250-285 K). Rapid westward proper motion (~2 arcmin drift from 2010 to 2026). Near-zero flux in D1-D3, steep rise in D4, massive thermal peak in D5/D6 with deep H2O-ice & CH4 bands.",
        "diagnostic_bands": ["D4_ice_3.0um", "D5_co2_4.27um", "D6_thermal_4.6um"]
    },
    "Barnard's Star": {
        "id": "barnards_star",
        "name": "Barnard's Star (GJ 699)",
        "common_name": "Barnard's Star",
        "category": "Ultra-High Proper Motion Star",
        "discovery_epoch": 2000.0,  # J2000.0 reference epoch
        "ra_deg": 269.4521,        # 17h 57m 48.5s
        "dec_deg": 4.6933,         # +04d 41m 36s
        "pm_ra_mas": -802.0,       # -0.802 arcsec/yr
        "pm_dec_mas": 10362.0,     # +10.362 arcsec/yr (Total: 10.39 arcsec/yr)
        "parallax_mas": 547.0,     # 0.547 arcsec / 1.83 pc (2nd closest star system to Sun)
        "spectral_type": "M4.0V",
        "teff_k": 3134,
        "peak_detector": "D1",     # Saturated core, strong in near-IR optical transition
        "description": "Fastest moving star in the sky (10.39 arcsec/yr). Moves ~0.85 SPHEREx native pixels per 6-month survey visit. Core saturates (OVERFLOW/PERSIST); strong TiO/VO molecular bands in D1-D2.",
        "diagnostic_bands": ["D1_tio_0.85um", "D2_h2o_1.4um"]
    },
    "Epsilon Indi Ba/Bb": {
        "id": "eps_indi_b",
        "name": "Epsilon Indi Ba/Bb",
        "common_name": "Epsilon Indi Ba/Bb",
        "category": "Binary Brown Dwarf (T1 + T6)",
        "discovery_epoch": 2020.0,
        "ra_deg": 331.0420,        # 22h 04m 10s (Target is Ba/Bb itself, 400 arcsec south of Eps Ind A!)
        "dec_deg": -56.7830,       # -56d 47m 00s
        "pm_ra_mas": 3982.0,       # +3.982 arcsec/yr
        "pm_dec_mas": -2467.0,     # -2.467 arcsec/yr (Total 4.68 arcsec/yr)
        "parallax_mas": 272.0,     # 0.272 arcsec / 3.67 pc
        "spectral_type": "T1 + T6",
        "teff_k": 1100,
        "peak_detector": "D3",     # Strong 2 um flux peak between deep water/methane bands
        "description": "Benchmark T1+T6 brown dwarf binary pair (0.73 arcsec separation) 400 arcsec south of primary host star Epsilon Indi A. Unresolved by SPHEREx. Deep 1.4 um and 1.9 um H2O vapor absorption, profound 2.2 um and 3.3 um CH4 bands.",
        "diagnostic_bands": ["D2_h2o_1.4um", "D3_ch4_2.2um", "D4_ch4_3.3um"]
    },
    "RW Aurigae": {
        "id": "rw_aur",
        "name": "RW Aurigae",
        "common_name": "RW Aurigae",
        "category": "Variable Young Stellar Object",
        "discovery_epoch": 2000.0,
        "ra_deg": 76.9563,         # 05h 07m 49.5s
        "dec_deg": 30.4000,        # +30d 24m 00s
        "pm_ra_mas": 0.0,          # Effectively zero proper motion (<0.03 arcsec/yr)
        "pm_dec_mas": 0.0,
        "parallax_mas": 6.13,      # ~163 pc
        "spectral_type": "K3:e + K5:e",
        "teff_k": 4500,
        "peak_detector": "D2",
        "description": "Classical T Tauri binary star with circumstellar accretion disk and tidal stream. Exhibits massive photometric dimming (>1-2 mag) due to occulting dust plumes rather than proper motion.",
        "diagnostic_bands": ["D1_phot_0.9um", "D3_dust_2.0um", "D5_dust_4.0um"]
    },
    "R Draconis": {
        "id": "r_dra",
        "name": "R Draconis",
        "common_name": "R Draconis",
        "category": "Mira-Type Long-Period Variable",
        "discovery_epoch": 2000.0,
        "ra_deg": 248.1675,        # 16h 32m 40.2s
        "dec_deg": 66.7550,        # +66d 45m 18s
        "pm_ra_mas": 0.0,          # Effectively zero proper motion
        "pm_dec_mas": 0.0,
        "parallax_mas": 1.51,      # ~660 pc (Gaia)
        "spectral_type": "M5e-M9e",
        "teff_k": 2800,
        "peak_detector": "D4",
        "description": "Mira-type asymptotic giant branch (AGB) pulsating variable (period ~246 days) near North Ecliptic Pole (~9 deg away). Visual magnitude swings from 6.7 to 13.2. Strong circumstellar silicate dust emission in D4-D6.",
        "diagnostic_bands": ["D1_optical_0.8um", "D4_miradust_3.2um", "D6_co_4.6um"]
    },
    "Planet X Candidate (Sedna-Type TNO)": {
        "id": "planet_x_candidate",
        "name": "Planet X / Hypothetical Trans-Neptunian Object",
        "common_name": "Planet X (TNO Candidate)",
        "category": "Hypothetical Trans-Neptunian Planet",
        "discovery_epoch": 2025.0,
        "ra_deg": 48.250000,        # 03h 13m 00.0s (Outer Solar System high-latitude search field)
        "dec_deg": 12.800000,       # +12d 48m 00s
        "pm_ra_mas": -1250.0,       # Dominated by Earth's annual reflex parallax + orbital motion
        "pm_dec_mas": -320.0,
        "parallax_mas": 2200.0,     # ~450 AU distance -> 2.22 arcsec parallax loop amplitude
        "spectral_type": "Cold TNO (Blackbody 40 K)",
        "teff_k": 42,               # Extremely cold equilibrium temperature
        "peak_detector": "D6",      # Far-IR tail detectable in SPHEREx D6
        "description": "Simulated Planet X / distant Trans-Neptunian dwarf planet at ~450 AU. Displays characteristic 2.2 arcsec annual reflex parallax retrograde loop. Pure thermal emission peaking beyond 5 um, completely absent in D1-D4.",
        "diagnostic_bands": ["D5_tno_4.3um", "D6_tno_4.9um"]
    }
}

def get_benchmark_list() -> List[Dict[str, Any]]:
    """Return summary list of all available benchmarks."""
    result = []
    for key, data in BENCHMARK_TARGETS.items():
        result.append({
            "key": key,
            "id": data["id"],
            "name": data["common_name"],
            "category": data["category"],
            "ra_deg": data["ra_deg"],
            "dec_deg": data["dec_deg"],
            "pm_total_arcsec_yr": round(((data["pm_ra_mas"]**2 + data["pm_dec_mas"]**2)**0.5) / 1000.0, 3),
            "spectral_type": data["spectral_type"],
            "peak_detector": data["peak_detector"],
            "description": data["description"]
        })
    return result

def get_target_by_query(query: str) -> Dict[str, Any]:
    """Fuzzy/exact match query against benchmark catalog."""
    q = query.strip().lower()
    if not q:
        raise ValueError("Target name cannot be empty")
    q_norm = q.replace("'", "").replace(" ", "").replace("-", "").replace("_", "")
    for name, target in BENCHMARK_TARGETS.items():
        name_norm = name.lower().replace("'", "").replace(" ", "").replace("-", "").replace("_", "")
        id_norm = target["id"].lower().replace("'", "").replace(" ", "").replace("-", "").replace("_", "")
        common_norm = target["common_name"].lower().replace("'", "").replace(" ", "").replace("-", "").replace("_", "")
        if (q == name.lower() or 
            q == target["id"].lower() or 
            q in target["name"].lower() or 
            q in target["common_name"].lower() or
            q_norm == name_norm or
            q_norm == id_norm or
            q_norm in common_norm or
            common_norm in q_norm):
            return target
    raise ValueError(f"Unknown benchmark target: {query}")
