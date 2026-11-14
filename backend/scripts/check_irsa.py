"""Hour-0 check against the REAL archive. Run: python scripts/check_irsa.py

1. lists SPHEREx collections (to see if DR1 is there)
2. lists the columns of spherex.plane (so we know what else we can select)
3. finds exposures at a test position, groups visits, times the query
4. downloads 3 cutouts, opens one, and writes its headers to notes/real_header.txt
"""
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from track1 import archive, cutouts, visits  # noqa: E402

# Position used in IRSA's own cutout tutorial: known to have SPHEREx coverage.
RA, DEC, SIZE = 210.80227, 54.34895, 0.083
if len(sys.argv) >= 3:
    RA, DEC = float(sys.argv[1]), float(sys.argv[2])

notes = ROOT / "notes"
notes.mkdir(exist_ok=True)

print("== 1. SPHEREx collections ==")
try:
    print(archive.list_collections())
except Exception as ex:
    print("  failed:", ex)

print("\n== 2. Columns in spherex.plane ==")
try:
    from astroquery.ipac.irsa import Irsa
    cols = Irsa.list_columns("spherex.plane")
    print("  ", ", ".join(cols.keys()))
    (notes / "plane_columns.txt").write_text("\n".join(f"{k}: {v}" for k, v in cols.items()))
except Exception as ex:
    print("  failed:", ex)

print(f"\n== 3. Exposures at RA={RA}, Dec={DEC} ==")
t0 = time.time()
exps = archive.search(RA, DEC, SIZE, use_cache=False)
exps = visits.group_visits(exps)
print(f"  {len(exps)} exposures in {time.time() - t0:.1f} s")
for v in visits.summarize(exps):
    print(f"  visit {v['visit']}: {v['n_exposures']} exposures, {v['first'][:10]} -> {v['last'][:10]}, {v['detectors']}")
for e in exps[:3]:
    print("  ", e.t_start_iso, e.detector, e.release, e.cutout_url[:110], "...")

if not exps:
    sys.exit("No exposures found - check the query / position.")

print("\n== 4. Download 3 cutouts ==")
t0 = time.time()
res = asyncio.run(cutouts.fetch_all([e.cutout_url for e in exps[:3]]))
print(f"  done in {time.time() - t0:.1f} s:", [(r["file"], r["error"]) for r in res])

ok = [r for r in res if r["file"]]
if ok:
    from astropy.io import fits
    path = cutouts.CUTOUT_DIR / ok[0]["file"]
    print(f"  file size: {path.stat().st_size / 1e6:.2f} MB")
    with fits.open(path) as hdul:
        hdul.info()
        with open(notes / "real_header.txt", "w") as f:
            for h in hdul:
                f.write(f"===== {h.name} =====\n{h.header.tostring(sep=chr(10))}\n\n")
    print(f"\nHeaders saved to {notes / 'real_header.txt'}")
print("\nAll good if you see exposures, visits and a downloaded file above.")
