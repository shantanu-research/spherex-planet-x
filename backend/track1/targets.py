"""Load the team's test targets and move each to where it is during the SPHEREx data.

test_targets.csv (data/reference/ in the team repo) gives positions at a catalogue
epoch plus proper motion in arcsec/yr. Fast movers have shifted by arcminutes since
then (Barnard's Star ~4.5', WISE 0855 ~2'), so we propagate before searching.
Parallax (< 1 arcsec) is ignored: far below a 6.15" SPHEREx pixel.
"""
from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV_PATHS = [
    ROOT / "data" / "test_targets.csv",
    ROOT.parent / "data" / "reference" / "test_targets.csv",  # when inside the team repo's backend/
]
SPHEREX_MID_EPOCH = 2025.9  # data so far spans ~2025.35 to ~2026.5


@dataclass
class Target:
    name: str
    slug: str
    ra_deg: float
    dec_deg: float
    epoch: float
    pmra_cosdec: float   # arcsec/yr
    pmdec: float         # arcsec/yr
    detectors: list[str]
    object_type: str
    notes: str

    def position_at(self, year: float) -> tuple[float, float]:
        dt = year - self.epoch
        dec = self.dec_deg + self.pmdec * dt / 3600.0
        ra = self.ra_deg + self.pmra_cosdec * dt / 3600.0 / math.cos(math.radians(self.dec_deg))
        return ra % 360.0, dec

    def to_dict(self) -> dict:
        return asdict(self)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _epoch(text: str) -> float:
    m = re.search(r"(\d{4}(?:\.\d+)?)", text or "")
    return float(m.group(1)) if m else 2000.0   # "approx" -> assume J2000


def _float(text: str) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _detectors(text: str) -> list[str]:
    text = (text or "").strip().upper()
    m = re.fullmatch(r"D(\d)\s*-\s*D(\d)", text)
    if m:
        return [f"D{i}" for i in range(int(m.group(1)), int(m.group(2)) + 1)]
    found = re.findall(r"D(\d)", text)
    return [f"D{i}" for i in found] or [f"D{i}" for i in range(1, 7)]   # "All"


def load_targets(path: str | Path | None = None) -> list[Target]:
    paths = [Path(path)] if path else DEFAULT_CSV_PATHS
    for p in paths:
        if p.exists():
            with open(p, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            return [Target(
                name=r["name"], slug=_slug(r["name"]),
                ra_deg=float(r["ra_deg"]), dec_deg=float(r["dec_deg"]),
                epoch=_epoch(r.get("coord_epoch", "")),
                pmra_cosdec=_float(r.get("pmra_cosdec_arcsec_per_yr")),
                pmdec=_float(r.get("pmdec_arcsec_per_yr")),
                detectors=_detectors(r.get("best_detectors", "")),
                object_type=r.get("object_type", ""), notes=r.get("notes", ""),
            ) for r in rows]
    raise FileNotFoundError(f"test_targets.csv not found in {[str(p) for p in paths]}")
