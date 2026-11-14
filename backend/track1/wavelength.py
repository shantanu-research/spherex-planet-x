"""Wavelength at the target for each exposure, cheaply.

SPHEREx uses linear variable filters: the wavelength changes across each detector
(mostly along Y). So the same star is seen at a different wavelength in every
exposure, depending on where it lands on the detector. Comparing frames over time
is only fair ("like with like colour") if they share a wavelength.

How it works:
- The wavelength map (WCS-WAVE extension) is a fixed per-detector calibration table
  (9 x 14 control points in raw detector pixels). We read it once per detector from any
  cached cutout and keep it in cache/lvf/D<n>.json.
- Where the target lands on the detector comes from each exposure's IMAGE header
  (TAN-SIP WCS). We fetch only the first 46 KB of the full image with an HTTP Range
  request (~1.7 s, vs 4 MB cutout / 66 MB image) and cache it in cache/headers/.
Validated on real R Draconis D3 data: header-only wavelength == cutout wavelength (0.0 nm).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import warnings
from pathlib import Path

import httpx
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from . import cutouts

CACHE = cutouts.CUTOUT_DIR.parent
LVF_DIR = CACHE / "lvf"
HDR_DIR = CACHE / "headers"
HEADER_BYTES = 46080           # 16 FITS blocks: PRIMARY + IMAGE header with room to spare
DETECTOR_PIXELS = 2040

warnings.filterwarnings("ignore", module="astropy.wcs")


# ---------------------------------------------------------------- wavelength map
def lvf_from_hdul(hdul) -> dict:
    t = hdul["WCS-WAVE"].data
    vals = np.asarray(t["VALUES"][0], dtype=float)          # (14 Y, 9 X, 2) -> [wave, bandwidth]
    return {"X": [float(v) for v in t["X"][0]], "Y": [float(v) for v in t["Y"][0]],
            "wave": vals[..., 0].tolist(), "band": vals[..., 1].tolist()}


def lvf_table(det: int, search_dir: Path | None = None) -> dict:
    """Per-detector wavelength map, from cache or extracted from any cached cutout."""
    LVF_DIR.mkdir(parents=True, exist_ok=True)
    f = LVF_DIR / f"D{det}.json"
    if f.exists():
        return json.loads(f.read_text())
    for p in sorted((search_dir or cutouts.CUTOUT_DIR).glob("*.fits")):
        try:
            if int(fits.getheader(p, "IMAGE").get("DETECTOR", -1)) != det:
                continue
            with fits.open(p) as h:
                table = lvf_from_hdul(h)
            f.write_text(json.dumps(table))
            return table
        except Exception:
            continue
    raise FileNotFoundError(f"No cached cutout for detector D{det} to read its wavelength map from")


def _bilinear(X, Y, V, x, y) -> float:
    X, Y, V = np.asarray(X), np.asarray(Y), np.asarray(V)
    ix = int(np.clip(np.searchsorted(X, x) - 1, 0, len(X) - 2))
    iy = int(np.clip(np.searchsorted(Y, y) - 1, 0, len(Y) - 2))
    tx = (x - X[ix]) / (X[ix + 1] - X[ix])
    ty = (y - Y[iy]) / (Y[iy + 1] - Y[iy])
    return float(V[iy, ix] * (1 - tx) * (1 - ty) + V[iy, ix + 1] * tx * (1 - ty)
                 + V[iy + 1, ix] * (1 - tx) * ty + V[iy + 1, ix + 1] * tx * ty)


def channel_edges(table: dict, n: int = 17) -> np.ndarray:
    w = np.asarray(table["wave"])
    return np.linspace(w.min(), w.max(), n + 1)


# ---------------------------------------------------------------- target position
def raw_xy(hdr: fits.Header, ra: float, dec: float) -> tuple[float, float]:
    """Target position in raw detector pixels (the wavelength table's coordinates)."""
    x0, y0 = WCS(hdr).all_world2pix(ra, dec, 0)
    x = (float(x0) + 1 - hdr.get("CRPIX1W", 1)) * hdr.get("CDELT1W", 1) + hdr.get("CRVAL1W", 1)
    y = (float(y0) + 1 - hdr.get("CRPIX2W", 1)) * hdr.get("CDELT2W", 1) + hdr.get("CRVAL2W", 1)
    return x, y


def wavelength_at(hdr: fits.Header, ra: float, dec: float, table: dict | None = None) -> dict:
    det = int(hdr.get("DETECTOR"))
    table = table or lvf_table(det)
    x, y = raw_xy(hdr, ra, dec)
    on = 1 <= x <= DETECTOR_PIXELS and 1 <= y <= DETECTOR_PIXELS
    return {"detector": det, "raw_x": round(x, 1), "raw_y": round(y, 1), "on_detector": on,
            "wave_um": round(_bilinear(table["X"], table["Y"], table["wave"], x, y), 5),
            "bandwidth_um": round(_bilinear(table["X"], table["Y"], table["band"], x, y), 5)}


# ---------------------------------------------------------------- header fetch
def parse_image_header(buf: bytes) -> fits.Header | None:
    txt = buf.decode("ascii", "replace")
    cards, out = [], []
    for i in range(0, len(txt) - 79, 80):
        card = txt[i:i + 80]
        cards.append(card)
        if card.rstrip() == "END":
            out.append("".join(cards))
            cards = []
    for h in out:
        hdr = fits.Header.fromstring(h)
        if hdr.get("EXTNAME") == "IMAGE":
            return hdr
    return None


def _hdr_path(url: str) -> Path:
    return HDR_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".hdr")


async def _fetch_header(client, sem, url: str) -> fits.Header | None:
    p = _hdr_path(url)
    if p.exists():
        return parse_image_header(p.read_bytes())
    async with sem:
        for attempt in range(cutouts.RETRIES):
            try:
                r = await client.get(url, headers={"Range": f"bytes=0-{HEADER_BYTES - 1}"})
                r.raise_for_status()
                buf = r.content[:HEADER_BYTES]
                hdr = parse_image_header(buf)
                if hdr is not None:
                    p.write_bytes(buf)
                return hdr
            except Exception:
                if attempt < cutouts.RETRIES - 1:
                    await asyncio.sleep(3 * 2 ** attempt)
    return None


async def fetch_headers(urls: list[str], max_parallel: int = cutouts.MAX_PARALLEL) -> list:
    HDR_DIR.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(max_parallel)
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        return await asyncio.gather(*[_fetch_header(client, sem, u) for u in urls])
