"""Build same-wavelength weekly time-lapses (+ light curves) for a target.

Run: python scripts/precache_timelapse.py                  (R Draconis, all 6 detectors)
     python scripts/precache_timelapse.py "rw aur" D1 D4    (target name part, detectors)
     python scripts/precache_timelapse.py "iz dra" D5 D6    (also searches data/variable_targets.csv)

Writes cache/timelapse/<slug>_D<n>.json (served by /api/precached/timelapse) and
notes/<slug>_lightcurve.csv (one row per frame, all detectors).
"""
import asyncio
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from track1 import archive, timelapse, visits  # noqa: E402
from track1.targets import SPHEREX_MID_EPOCH, load_targets  # noqa: E402

SIZE_DEG = 0.1
EVERY_DAYS = 7.0
OUT = ROOT / "cache" / "timelapse"
NOTES = ROOT / "notes"
VARIABLES_CSV = ROOT / "data" / "variable_targets.csv"


def main():
    args = sys.argv[1:]
    key = args[0].lower() if args and not args[0].upper().startswith("D") else "draconis"
    dets = [a.upper() for a in args if a.upper().startswith("D") and a[1:].isdigit()] or [f"D{i}" for i in range(1, 7)]
    targets = load_targets()
    if VARIABLES_CSV.exists():
        targets += load_targets(VARIABLES_CSV)   # extra variable stars picked from AAVSO VSX
    t = next(t for t in targets if key in t.name.lower())
    ra, dec = t.position_at(SPHEREX_MID_EPOCH)
    print(f"Time-lapse for {t.name} at ({ra:.4f}, {dec:.4f}), detectors {dets}, one frame per {EVERY_DAYS:g} days",
          flush=True)
    t0 = time.time()
    exps = visits.group_visits(archive.search(ra, dec, SIZE_DEG))
    print(f"search: {len(exps)} exposures in {time.time() - t0:.0f} s", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    NOTES.mkdir(exist_ok=True)
    rows, summary = [], []
    for det in dets:
        t1 = time.time()
        try:
            res = asyncio.run(timelapse.build_timelapse(exps, ra, dec, det, every_days=EVERY_DAYS))
        except Exception as ex:
            print(f"  {det}: FAILED {type(ex).__name__}: {ex}", flush=True)
            summary.append((det, "-", "-", "-", "-", f"FAILED {type(ex).__name__}"))
            continue
        res["slug"] = t.slug
        res["target"] = t.name
        (OUT / f"{t.slug}_{det}.json").write_text(json.dumps(res, indent=1))
        fr = res["frames"]
        good = [f["flux_norm"] for f in fr if f.get("flux_norm") is not None]
        amp = f"{min(good):.2f}-{max(good):.2f}" if good else "-"
        n_sat = sum(1 for f in fr if f.get("saturated"))
        print(f"  {det}: {res['n_candidates']} candidates -> {res['n_frames']} frames at "
              f"{res['reference_wave_um']} um (+/-{res['tolerance_um']}), span {res['span_days']} d, "
              f"usable photometry {res['n_usable_photometry']}, saturated {n_sat}, "
              f"flux range {amp} ({time.time() - t1:.0f} s)", flush=True)
        summary.append((det, res["n_frames"], res["span_days"], res["reference_wave_um"],
                        f"{res['n_usable_photometry']}/{res['n_frames']}", amp))
        for f in fr:
            rows.append({"date": f["t_start_iso"][:19], "mjd": round(f["t_start_mjd"], 5), "detector": det,
                         "wave_um": f["wave_um"], "flux_rel": f.get("flux"), "flux_norm": f.get("flux_norm"),
                         "saturated": f.get("saturated"), "usable": f.get("usable"),
                         "flags": " ".join(f.get("flags", [])), "file_url": f.get("file_url")})

    lc = NOTES / f"{t.slug}_lightcurve.csv"
    if rows:
        with open(lc, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: (r["detector"], r["mjd"])))
    print("\n==================== SUMMARY ====================")
    print(f"{'det':4} {'frames':>6} {'span_d':>7} {'wave_um':>8} {'usable':>8}  flux_norm range")
    for s in summary:
        print(f"{s[0]:4} {s[1]!s:>6} {s[2]!s:>7} {s[3]!s:>8} {s[4]!s:>8}  {s[5]}")
    print(f"Light curve: {lc}")
    print(f"Total time: {(time.time() - t0) / 60:.1f} min")
    print("TIMELAPSE_DONE")


if __name__ == "__main__":
    main()
