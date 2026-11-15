"""
SPHEREx Planet X Challenge - 102-Channel Molecular Fingerprints & Diagnostic Bands
Defines the 102 SPHEREx spectral channels and key molecular absorption lines.
"""

from typing import List, Dict, Any

# Primary Diagnostic Molecular Bands (Table 2.1)
DIAGNOSTIC_MOLECULAR_BANDS = [
    {
        "name": "TiO / VO Metal Oxides",
        "species": "TiO/VO",
        "wavelength_um": 0.85,
        "detector": "D1",
        "description": "Characteristic optical/near-IR photospheric absorption in M dwarfs (e.g. Barnard's Star)."
    },
    {
        "name": "H2O Vapor Absorption",
        "species": "H2O",
        "wavelength_um": 1.40,
        "detector": "D2",
        "description": "Deep atmospheric water vapor absorption diagnostic of cool brown dwarfs (L/T dwarfs)."
    },
    {
        "name": "H2O 1.9 um Vapor Band",
        "species": "H2O",
        "wavelength_um": 1.90,
        "detector": "D3",
        "description": "Fundamental water vapor band separating J and H infrared photometric windows."
    },
    {
        "name": "CH4 Methane Absorption",
        "species": "CH4",
        "wavelength_um": 2.20,
        "detector": "D3",
        "description": "Overtone methane absorption band defining the transition from L to T brown dwarfs."
    },
    {
        "name": "H2O Ice Grain Absorption",
        "species": "H2O-Ice",
        "wavelength_um": 3.00,
        "detector": "D4",
        "description": "Profound water ice feature in sub-300 K brown dwarfs (WISE 0855) and circumstellar disks (RW Aur)."
    },
    {
        "name": "Fundamental CH4 Band",
        "species": "CH4",
        "wavelength_um": 3.32,
        "detector": "D4",
        "description": "Strongest atmospheric methane absorption band in substellar atmospheres."
    },
    {
        "name": "CO2 Molecular Band",
        "species": "CO2",
        "wavelength_um": 4.27,
        "detector": "D5",
        "description": "Carbon dioxide absorption; marks the onset of cold Y-dwarfs and exoplanet atmospheres."
    },
    {
        "name": "Fundamental CO Band",
        "species": "CO",
        "wavelength_um": 4.60,
        "detector": "D6",
        "description": "Fundamental carbon monoxide band; thermal peak for Y-dwarfs (WISE 0855) and distant TNOs."
    }
]

def generate_102_channel_grid() -> List[Dict[str, Any]]:
    """Generates the full 102-channel wavelength grid across all 6 detectors."""
    detectors = [
        ("D1", 0.744, 1.116, 39),
        ("D2", 1.099, 1.651, 41),
        ("D3", 1.636, 2.421, 41),
        ("D4", 2.423, 3.822, 35),
        ("D5", 3.809, 4.420, 112),
        ("D6", 4.412, 5.002, 128)
    ]
    grid = []
    global_idx = 1
    for det, lmin, lmax, R in detectors:
        step = (lmax - lmin) / 17.0
        for ch in range(1, 18):
            lc = lmin + (ch - 0.5) * step
            # Find nearest diagnostic molecular line
            nearest_mol = None
            for mol in DIAGNOSTIC_MOLECULAR_BANDS:
                if abs(mol["wavelength_um"] - lc) < (step * 0.75):
                    nearest_mol = mol["species"]
                    break
                    
            grid.append({
                "channel_id": global_idx,
                "detector": det,
                "channel_in_detector": ch,
                "wavelength_um": round(lc, 4),
                "bandwidth_um": round(step, 4),
                "resolving_power_R": R,
                "molecular_feature": nearest_mol
            })
            global_idx += 1
    return grid
