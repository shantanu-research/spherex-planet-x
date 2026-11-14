"""Plot notes/<slug>_lightcurve.csv (written by precache_timelapse.py) as flux_norm vs date.

Run: python scripts/plot_lightcurve.py iz-dra
Writes notes/<slug>_lightcurve.png. Only frames flagged usable are drawn as filled points;
saturated / flagged frames are shown as open grey markers (never interpolated).
Needs matplotlib (not part of the API requirements).
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main():
    slug = sys.argv[1] if len(sys.argv) > 1 else "iz-dra"
    rows = list(csv.DictReader(open(ROOT / "notes" / f"{slug}_lightcurve.csv")))
    dets = sorted({r["detector"] for r in rows})
    fig, axes = plt.subplots(len(dets), 1, figsize=(9, 2.8 * len(dets)), sharex=True, squeeze=False)
    for ax, det in zip(axes[:, 0], dets):
        rs = [r for r in rows if r["detector"] == det]
        good = [r for r in rs if r["usable"] == "True" and r["flux_norm"]]
        bad = [r for r in rs if not (r["usable"] == "True" and r["flux_norm"])]
        d = lambda r: datetime.fromisoformat(r["date"])  # noqa: E731
        ax.plot([d(r) for r in good], [float(r["flux_norm"]) for r in good], "o", ms=4, color="#2a6fdb",
                label=f"usable ({len(good)})")
        if bad:
            ax.plot([d(r) for r in bad], [1.0] * len(bad), "o", ms=4, mfc="none", color="#999",
                    label=f"flagged / saturated ({len(bad)})")
        waves = [float(r["wave_um"]) for r in rs if r["wave_um"]]
        wl = f"{min(waves):.3f}-{max(waves):.3f} um" if waves else ""
        ax.set_ylabel("flux / median")
        ax.set_title(f"{det}  ({wl}, one frame per week)", fontsize=10, loc="left")
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(alpha=0.3)
    fig.suptitle(f"SPHEREx same-wavelength light curve: {slug}", fontsize=12)
    fig.tight_layout()
    out = ROOT / "notes" / f"{slug}_lightcurve.png"
    fig.savefig(out, dpi=120)
    print(out)


if __name__ == "__main__":
    main()
