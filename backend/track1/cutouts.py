"""Download cutouts in parallel (max 8 at once), with retries and an on-disk cache."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import httpx

CUTOUT_DIR = Path(__file__).resolve().parent.parent / "cache" / "cutouts"
MAX_PARALLEL = 8
RETRIES = 5          # IRSA returns 503 "busy" under load; back off 3, 6, 12, 24 s
TIMEOUT_S = 90.0


def cache_path(url: str) -> Path:
    return CUTOUT_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".fits")


async def _fetch_one(client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str) -> dict:
    path = cache_path(url)
    if path.exists() and path.stat().st_size > 0:
        return {"url": url, "file": path.name, "cached": True, "error": None}
    async with sem:
        err = None
        for attempt in range(RETRIES):
            try:
                r = await client.get(url)
                r.raise_for_status()
                tmp = path.with_suffix(".part")
                tmp.write_bytes(r.content)
                tmp.replace(path)
                return {"url": url, "file": path.name, "cached": False, "error": None}
            except Exception as ex:  # network hiccup, 5xx, timeout
                err = f"{type(ex).__name__}: {ex}"
                if attempt < RETRIES - 1:
                    await asyncio.sleep(3 * 2 ** attempt)
        return {"url": url, "file": None, "cached": False, "error": err}


async def fetch_all(urls: list[str], max_parallel: int = MAX_PARALLEL) -> list[dict]:
    CUTOUT_DIR.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(max_parallel)
    async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=True) as client:
        return await asyncio.gather(*[_fetch_one(client, sem, u) for u in urls])
