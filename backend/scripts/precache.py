"""Pre-cache the demo targets so the demo works even if NASA's archive is slow or down.

Run: python scripts/precache.py            (all targets in test_targets.csv)
     python scripts/precache.py wise       (only targets whose name contains "wise")

For each target: propagate proper motion to the SPHEREx epoch, run ONE archive
search (cached for all detectors), download PER_VISIT frames per visit for each of
the target's best detectors, and write cache/targets/<slug>.json (the manifest the
API serves at /api/precached).
"""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from track1 import archive, cutouts, visits  # noqa: E402
from track1.targets import SPHEREX_MID_EPOCH, load_targets  # noqa: E402

SIZE_DEG = 0.1      # 6 arcmin: room for fast movers to drift within the data span
PER_VISIT = 4
OUT = ROOT / "cache" / "targets"


def precache(t) -> dict:
    ra, dec = t.position_at(SPHEREX_MID_EPOCH)
    print(f"\n=== {t.name}  (catalogue {t.ra_deg:.4f}, {t.dec_deg:.4f} @ {t.epoch}"
          f" -> {ra:.4f}, {dec:.4f} @ {SPHEREX_MID_EPOCH})", flush=True)
    t0 = time.time()
    exps = visits.group_visits(archive.search(ra, dec, SIZE_DEG))
    print(f"  search: {len(exps)} exposures, {len(visits.summarize(exps))} visits"
          f" in {time.time() - t0:.0f} s", flush=True)

    per_det = {}
    for det in t.detectors:
        name = f"SPHEREx-{det}"
        sel = visits.select_frames([e for e in exps if e.detector == name], per_visit=PER_VISIT)
        t1 = time.time()
        res = asyncio.run(cutouts.fetch_all([e.cutout_url for e in sel]))
        frames = []
        for e, r in zip(sel, res):
            d = e.to_dict()
            d["file_url"] = f"/files/{r['file']}" if r["file"] else None
            d["error"] = r["error"]
            frames.append(d)
        ok = sum(f["file_url"] is not None for f in frames)
        print(f"  {det}: {ok}/{len(frames)} cutouts in {time.time() - t1:.0f} s", flush=True)
        per_det[det] = frames

    manifest = {
        "target": t.to_dict(), "ra": ra, "dec": dec, "epoch_used": SPHEREX_MID_EPOCH,
        "size_deg": SIZE_DEG, "per_visit": PER_VISIT,
        "n_exposures": len(exps), "visits": visits.summarize(exps),
        "frames_by_detector": per_det,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{t.slug}.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def main():
    targets = load_targets()
    if len(sys.argv) > 1:
        key = sys.argv[1].lower()
        targets = [t for t in targets if key in t.name.lower()]
    print(f"Pre-caching {len(targets)} targets: {[t.name for t in targets]}", flush=True)
    t0 = time.time()
    summary = []
    for t in targets:
        try:
            m = precache(t)
            n_ok = sum(f["file_url"] is not None for fr in m["frames_by_detector"].values() for f in fr)
            n_all = sum(len(fr) for fr in m["frames_by_detector"].values())
            summary.append((t.name, m["n_exposures"], len(m["visits"]), f"{n_ok}/{n_all}", "OK"))
        except Exception as ex:
            print(f"  FAILED: {type(ex).__name__}: {ex}", flush=True)
            summary.append((t.name, "-", "-", "-", f"FAILED: {type(ex).__name__}"))
    print("\n==================== SUMMARY ====================")
    print(f"{'target':22} {'exposures':>9} {'visits':>6} {'cutouts':>9}  status")
    for name, n, v, c, s in summary:
        print(f"{name:22} {n!s:>9} {v!s:>6} {c:>9}  {s}")
    print(f"Total time: {(time.time() - t0) / 60:.1f} min")
    print("PRECACHE_DONE")


if __name__ == "__main__":
    main()
