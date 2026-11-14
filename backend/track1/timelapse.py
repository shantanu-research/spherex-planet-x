"""Time-lapse of one sky position at ONE wavelength, sampled by date, with a light curve.

Steps (see build_timelapse):
1. all exposures of the position on one detector
2. wavelength at the target for each (wavelength.py, cheap header fetch)
3. choose the wavelength channel (1 of 17) with the most dates covered, unless given
4. keep exposures within +/- tol of that wavelength; one per `every_days` bin
   (the one closest to the reference wavelength) -> no invented frames, gaps are reported
5. download those cutouts and measure the target (aperture minus local background),
   flagging frames where the target pixels are saturated (OVERFLOW / NONLINEAR flags)
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from . import archive, cutouts, wavelength

BAD_FOR_PHOTOMETRY = ("OVERFLOW", "NONLINEAR", "SUR_ERROR", "NONFUNC", "MISSING_DATA", "PERSIST")


# ---------------------------------------------------------------- selection (pure, testable)
def coverage_by_channel(items: list[dict], edges, every_days: float) -> list[dict]:
    """items: dicts with wave_um, t_start_mjd. Returns per-channel number of date bins covered."""
    t0 = min(i["t_start_mjd"] for i in items) if items else 0
    out = []
    for k in range(len(edges) - 1):
        lo, hi = edges[k], edges[k + 1]
        bins = {int((i["t_start_mjd"] - t0) // every_days) for i in items if lo <= i["wave_um"] < hi}
        out.append({"channel": k + 1, "wave_lo_um": round(float(lo), 4), "wave_hi_um": round(float(hi), 4),
                    "wave_center_um": round(float((lo + hi) / 2), 4), "n_date_bins": len(bins)})
    return out


def select_timelapse(items: list[dict], every_days: float = 7.0, wave_um: float | None = None,
                     tol_um: float | None = None, edges=None, max_frames: int | None = None):
    """Pick one exposure per date bin at (nearly) the same wavelength.

    Returns (frames, reference_wave_um, tol_um, coverage).
    """
    items = [i for i in items if i.get("on_detector", True) and i.get("wave_um") is not None]
    if not items:
        return [], None, None, []
    if edges is None:
        w = [i["wave_um"] for i in items]
        edges = np.linspace(min(w), max(w) + 1e-9, 18)
    coverage = coverage_by_channel(items, edges, every_days)
    width = float(edges[1] - edges[0])
    if wave_um is None:
        best = max(coverage, key=lambda c: c["n_date_bins"])
        wave_um = best["wave_center_um"]
    tol_um = tol_um if tol_um is not None else width / 2
    keep = [i for i in items if abs(i["wave_um"] - wave_um) <= tol_um]
    if not keep:
        return [], wave_um, tol_um, coverage
    t0 = min(i["t_start_mjd"] for i in items)
    bins: dict[int, dict] = {}
    for i in keep:
        b = int((i["t_start_mjd"] - t0) // every_days)
        if b not in bins or abs(i["wave_um"] - wave_um) < abs(bins[b]["wave_um"] - wave_um):
            bins[b] = i
    frames = [bins[b] for b in sorted(bins)]
    if max_frames and len(frames) > max_frames:
        idx = np.linspace(0, len(frames) - 1, max_frames).round().astype(int)
        frames = [frames[k] for k in sorted(set(idx))]
    prev = None
    for f in frames:
        f["gap_days"] = None if prev is None else round(f["t_start_mjd"] - prev, 2)
        prev = f["t_start_mjd"]
    return frames, round(float(wave_um), 4), round(float(tol_um), 4), coverage


# ---------------------------------------------------------------- photometry
def flag_names(flags_header) -> dict[int, str]:
    names = {}
    for k, v in flags_header.items():
        if k.startswith("MSKN"):
            names[int(k[4:])] = str(v).strip()
    return names


def measure(path, ra: float, dec: float, r_ap: float = 2.5, r_in: float = 5.0, r_out: float = 8.0) -> dict:
    """Aperture sum minus median local background (relative units: MJy/sr x pixels)."""
    with fits.open(path) as h:
        img = h["IMAGE"].data.astype(float)
        flags = h["FLAGS"].data.astype(np.int64)
        names = flag_names(h["FLAGS"].header)
        x, y = WCS(h["IMAGE"].header).all_world2pix(ra, dec, 0)
    yy, xx = np.indices(img.shape)
    r = np.hypot(xx - float(x), yy - float(y))
    ap, ann = r <= r_ap, (r >= r_in) & (r <= r_out)
    if not ap.any() or not (0 <= x < img.shape[1] and 0 <= y < img.shape[0]):
        return {"flux": None, "flags": ["OFF_CUTOUT"], "saturated": False, "usable": False}
    bits = int(np.bitwise_or.reduce(flags[ap].ravel()))
    present = sorted({names.get(b, f"BIT{b}") for b in range(32) if bits >> b & 1})
    good_bg = ann & np.isfinite(img)
    bg = float(np.nanmedian(img[good_bg])) if good_bg.any() else 0.0
    vals = img[ap]
    flux = float(np.nansum(vals - bg)) if np.isfinite(vals).any() else None
    bad = [f for f in present if f in BAD_FOR_PHOTOMETRY]
    return {"flux": flux, "background": bg, "flags": present,
            "saturated": any(f in ("OVERFLOW", "NONLINEAR") for f in present),
            "usable": flux is not None and not bad}


# ---------------------------------------------------------------- orchestration
async def build_timelapse(exps, ra: float, dec: float, det: str, every_days: float = 7.0,
                          wave_um: float | None = None, tol_um: float | None = None,
                          max_frames: int | None = 120, download: bool = True) -> dict:
    name = archive._detector_name(det)          # "D5", "5", "SPHEREx-D5" -> "SPHEREx-D5"
    det_n = int(name[-1])
    cand = [e for e in exps if e.detector == name]
    if not cand:
        return {"error": f"No {name} exposures at this position", "frames": []}
    headers = await wavelength.fetch_headers([e.image_url for e in cand])
    try:
        table = wavelength.lvf_table(det_n)
    except FileNotFoundError:
        # no cached cutout of this detector yet: download one, then read its wavelength map
        await cutouts.fetch_all([cand[0].cutout_url])
        table = wavelength.lvf_table(det_n)
    items, n_no_header = [], 0
    for e, hdr in zip(cand, headers):
        if hdr is None:
            n_no_header += 1
            continue
        d = e.to_dict()
        d.update(wavelength.wavelength_at(hdr, ra, dec, table))
        items.append(d)
    frames, ref, tol, coverage = select_timelapse(
        items, every_days, wave_um, tol_um, edges=wavelength.channel_edges(table), max_frames=max_frames)
    if download and frames:
        res = await cutouts.fetch_all([f["cutout_url"] for f in frames])
        for f, r in zip(frames, res):
            f["file_url"] = f"/files/{r['file']}" if r["file"] else None
            f["error"] = r["error"]
            if r["file"]:
                try:
                    f.update(measure(cutouts.CUTOUT_DIR / r["file"], ra, dec))
                except Exception as ex:
                    f.update({"flux": None, "usable": False, "flags": [f"MEASURE_ERROR: {ex}"]})
        good = [f["flux"] for f in frames if f.get("usable") and f.get("flux")]
        med = float(np.median(good)) if good else None
        for f in frames:
            f["flux_norm"] = (round(f["flux"] / med, 4)
                              if med and f.get("usable") and f.get("flux") is not None else None)
    span = (frames[-1]["t_start_mjd"] - frames[0]["t_start_mjd"]) if len(frames) > 1 else 0
    return {"ra": ra, "dec": dec, "detector": name, "every_days": every_days,
            "reference_wave_um": ref, "tolerance_um": tol,
            "n_candidates": len(cand), "n_without_header": n_no_header,
            "n_frames": len(frames), "span_days": round(span, 1),
            "n_usable_photometry": sum(1 for f in frames if f.get("usable")),
            "channels": coverage, "frames": frames}


def run(exps, ra, dec, det, **kw) -> dict:
    return asyncio.run(build_timelapse(exps, ra, dec, det, **kw))
