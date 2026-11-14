"""
Query running SPHEREx server for 5 benchmark targets:
- Barnard's Star
- WISE 0855-0714
- Epsilon Indi Ba/Bb
- RW Aurigae
- R Draconis

Caches real IRSA FITS cutouts in backend/cache/cutouts/ and prints a summary table of:
- Target name
- Exposure count / Cutouts processed
- Wavelength range (um)
- Peak flux (mJy)
- Saturation flag (presence of OVERFLOW saturation)
- Source provenance
"""

import urllib.request
import urllib.parse
import json
import time
import os
from pathlib import Path

TARGETS = [
    "Barnard's Star",
    "WISE 0855-0714",
    "Epsilon Indi Ba/Bb",
    "RW Aurigae",
    "R Draconis"
]

SERVER_URL = "http://localhost:8080/api/spectrum"

def test_targets():
    results = []
    print("=" * 80)
    print("SPHEREx 102-Channel Spectrophotometry Extraction & Cutout Caching")
    print("Querying http://localhost:8080/api/spectrum for 5 Benchmark Targets")
    print("=" * 80)

    for tgt in TARGETS:
        print(f"\n[+] Requesting spectrum for: {tgt} ...")
        t0 = time.time()
        url = f"{SERVER_URL}?q={urllib.parse.quote(tgt)}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SPHEREx-SED-Benchmark/1.0"})
            with urllib.request.urlopen(req, timeout=300.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - t0
                print(f"    Completed in {elapsed:.2f}s - Status: {data.get('status')}")
                results.append((tgt, data, elapsed))
        except Exception as e:
            elapsed = time.time() - t0
            print(f"    FAILED ({elapsed:.2f}s): {e}")
            results.append((tgt, {"status": "error", "message": str(e)}, elapsed))

    # Print Summary Table
    print("\n" + "=" * 105)
    print(f"{'Target Name':<22} | {'Exposures':<10} | {'Wavelength (um)':<18} | {'Peak Flux (mJy)':<16} | {'Saturation Flag':<16} | {'Source'}")
    print("-" * 105)

    for tgt, d, el in results:
        if d.get("status") == "success":
            exps = d.get("exposure_count", d.get("cutouts_processed", "N/A"))
            w_range = d.get("wavelength_range_um", [0.75, 5.0])
            w_str = f"{w_range[0]:.3f} - {w_range[1]:.3f}" if isinstance(w_range, list) and len(w_range) == 2 else str(w_range)
            peak = f"{d.get('peak_flux_mjy', 0.0):.2f}"
            sat = "SATURATED (Core)" if d.get("saturation_flag") else "NOMINAL (Linear)"
            source = d.get("source", "IRSA FITS Cutouts")
            print(f"{tgt:<22} | {str(exps):<10} | {w_str:<18} | {peak:<16} | {sat:<16} | {source}")
        else:
            print(f"{tgt:<22} | {'ERR':<10} | {'ERR':<18} | {'ERR':<16} | {'ERR':<16} | {d.get('message', 'Error')}")

    print("=" * 105)

    # Check cache directory size
    cache_dir = Path(__file__).resolve().parent.parent / "cache" / "cutouts"
    if cache_dir.exists():
        fits_files = list(cache_dir.glob("*.fits"))
        total_size_mb = sum(f.stat().st_size for f in fits_files) / (1024 * 1024)
        print(f"\n[Disk Cache Status] {len(fits_files)} FITS cutouts cached in {cache_dir} ({total_size_mb:.2f} MB)")

if __name__ == "__main__":
    test_targets()
