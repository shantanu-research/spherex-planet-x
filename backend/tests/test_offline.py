"""Offline tests (no internet needed): python -m pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from track1 import archive, visits  # noqa: E402

FAKE = [
    # uri, t_start, t_end, band
    ["ibe/data/spherex/qr2/level2/a.fits", 60800.10, 60800.11, "SPHEREx-D2"],
    ["ibe/data/spherex/dr1/level2/a.fits", 60800.10, 60800.11, "SPHEREx-D2"],  # same exposure, newer
    ["ibe/data/spherex/qr3/level2/b.fits", 60800.50, 60800.51, "SPHEREx-D5"],
    ["ibe/data/spherex/qr3/level2/c.fits", 60985.20, 60985.21, "SPHEREx-D2"],  # ~6 months later
]


def fake_tap(query):
    assert "CONTAINS(POINT('ICRS'" in query
    return FAKE


def test_search_dedupes_and_builds_cutout_urls(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "CACHE_DIR", tmp_path)
    exps = archive.search(133.79, -7.24, 0.083, tap=fake_tap)
    assert len(exps) == 3
    assert exps[0].release == "dr1"
    assert exps[0].cutout_url.startswith("https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/")
    assert "?center=133.7900000,-7.2400000d&size=0.08300" in exps[0].cutout_url


def test_visits_split_at_gaps(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "CACHE_DIR", tmp_path)
    exps = visits.group_visits(archive.search(10, 20, tap=fake_tap))
    assert [e.visit for e in exps] == [0, 0, 1]
    s = visits.summarize(exps)
    assert len(s) == 2 and s[0]["n_exposures"] == 2


def test_query_filters():
    q = archive.build_query(1, 2, detector="5", t_min_mjd=60000, t_max_mjd=61000)
    assert "energy_bandpassname = 'SPHEREx-D5'" in q
    assert ">= 60000" in q and "<= 61000" in q


def test_api_observations(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from track1 import api
    monkeypatch.setattr(archive, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(archive, "_run_tap", fake_tap)
    r = TestClient(api.app).get("/api/observations", params={"ra": 10, "dec": 20})
    assert r.status_code == 200
    body = r.json()
    assert body["n_exposures"] == 3 and len(body["visits"]) == 2


def _fake_visits(counts):
    """counts e.g. [122, 124, 130] -> exposures in 3 visits ~180 days apart."""
    exps = []
    for v, n in enumerate(counts):
        for i in range(n):
            t = 60800 + v * 180 + i * 0.1
            exps.append(archive.Exposure("u", "c", t, t + 0.001, "", "SPHEREx-D5", "dr1", v))
    return exps


def test_limit_is_shared_across_visits():
    sel = visits.select_frames(_fake_visits([122, 124, 130]), limit=8)
    per = [sum(e.visit == v for e in sel) for v in range(3)]
    assert len(sel) == 8 and per == [3, 3, 2]


def test_per_visit_evenly_spaced():
    sel = visits.select_frames(_fake_visits([122, 124, 130]), per_visit=4)
    assert len(sel) == 12
    v0 = [e for e in sel if e.visit == 0]
    assert v0[0].t_start_mjd == 60800 and abs(v0[-1].t_start_mjd - (60800 + 121 * 0.1)) < 1e-9


def test_small_visit_gives_its_leftover_to_others():
    sel = visits.select_frames(_fake_visits([2, 50, 50]), limit=12)
    assert [sum(e.visit == v for e in sel) for v in range(3)] == [2, 5, 5]


def test_no_options_returns_everything():
    assert len(visits.select_frames(_fake_visits([3, 4]))) == 7


def test_detector_filter_reuses_one_cached_query(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "CACHE_DIR", tmp_path)
    calls = []
    def counting_tap(q):
        calls.append(q)
        return FAKE
    d5 = archive.search(10, 20, detector="D5", tap=counting_tap)
    d2 = archive.search(10, 20, detector="D2", tap=counting_tap)
    allx = archive.search(10, 20, tap=counting_tap)
    assert len(calls) == 1
    assert [e.detector for e in d5] == ["SPHEREx-D5"]
    assert {e.detector for e in d2} == {"SPHEREx-D2"} and len(allx) == 3


def test_targets_load_and_propagate():
    from track1.targets import load_targets
    ts = {t.slug: t for t in load_targets()}
    assert len(ts) == 5
    b = ts["barnard-s-star"]
    assert b.detectors == ["D1", "D2", "D3"] and b.epoch == 2000.0
    ra, dec = b.position_at(2025.9)
    assert abs((dec - b.dec_deg) * 3600 - 10.36 * 25.9) < 0.01      # ~268 arcsec north
    w = ts["wise-0855-0714"]
    assert w.epoch == 2010.5 and w.detectors == ["D5", "D6"]
    ra, dec = w.position_at(2025.9)
    assert 120 < (w.ra_deg - ra) * 3600 * 0.992 < 130                # ~2 arcmin west
    assert ts["r-draconis"].detectors == [f"D{i}" for i in range(1, 7)]


# ---------------- time-lapse / wavelength
def _items(n_weeks=20, per_week=12):
    import random
    random.seed(1)
    out = []
    for wk in range(n_weeks):
        for k in range(per_week):
            out.append({"t_start_mjd": 60800 + wk * 7 + k * 0.3, "wave_um": random.uniform(1.64, 2.42),
                        "on_detector": True})
    return out


def test_select_timelapse_same_wavelength_one_per_week():
    from track1 import timelapse
    import numpy as np
    edges = np.linspace(1.64, 2.42, 18)
    frames, ref, tol, cov = timelapse.select_timelapse(_items(), every_days=7, edges=edges)
    assert len(cov) == 17 and ref is not None
    assert all(abs(f["wave_um"] - ref) <= tol for f in frames)
    weeks = [int((f["t_start_mjd"] - 60800) // 7) for f in frames]
    assert len(weeks) == len(set(weeks))                      # at most one per week
    assert frames[0]["gap_days"] is None and all(f["gap_days"] > 0 for f in frames[1:])
    best = max(c["n_date_bins"] for c in cov)
    assert len(frames) == best                                 # picked the best-covered channel


def test_select_timelapse_fixed_wave_and_cap():
    from track1 import timelapse
    frames, ref, tol, _ = timelapse.select_timelapse(_items(), every_days=7, wave_um=2.0, tol_um=0.1, max_frames=5)
    assert ref == 2.0 and len(frames) <= 5 and all(abs(f["wave_um"] - 2.0) <= 0.1 for f in frames)


def test_wavelength_lookup_and_header_parse():
    from astropy.io import fits
    from track1 import wavelength
    X = [1, 1021, 2040]; Y = [1, 1021, 2040]
    wave = [[2.4, 2.4, 2.4], [2.0, 2.0, 2.0], [1.6, 1.6, 1.6]]
    table = {"X": X, "Y": Y, "wave": wave, "band": [[0.05] * 3] * 3}
    hdr = fits.Header()
    hdr.update({"EXTNAME": "IMAGE", "DETECTOR": 3, "NAXIS": 2, "NAXIS1": 2040, "NAXIS2": 2040,
                "CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN", "CRVAL1": 100.0, "CRVAL2": 20.0,
                "CRPIX1": 1021.0, "CRPIX2": 1021.0, "CDELT1": -6.15 / 3600, "CDELT2": 6.15 / 3600,
                "CRPIX1W": 1, "CRPIX2W": 1, "CRVAL1W": 1, "CRVAL2W": 1})
    w = wavelength.wavelength_at(hdr, 100.0, 20.0, table)
    assert w["on_detector"] and abs(w["raw_y"] - 1021) < 0.5 and abs(w["wave_um"] - 2.0) < 1e-6
    # header bytes as they arrive from an HTTP Range request
    prim = fits.PrimaryHDU().header.tostring()
    img = fits.ImageHDU(header=hdr).header.tostring()
    buf = (prim + img).encode() + b" " * 4000
    parsed = wavelength.parse_image_header(buf)
    assert parsed is not None and parsed["DETECTOR"] == 3


def test_measure_aperture_and_saturation_flag(tmp_path):
    import numpy as np
    from astropy.io import fits
    from track1 import timelapse
    hdr = fits.Header({"CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN", "CRVAL1": 10.0, "CRVAL2": 0.0,
                       "CRPIX1": 25.0, "CRPIX2": 25.0, "CDELT1": -6.15 / 3600, "CDELT2": 6.15 / 3600})
    img = np.full((49, 49), 5.0, dtype=np.float32)
    img[23:26, 23:26] += 10.0                                  # 9 px x 10 = 90 above background
    flags = np.zeros((49, 49), dtype=np.int32)
    fh = fits.Header({"MSKN0001": "OVERFLOW"})
    f = tmp_path / "c.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(img, hdr, name="IMAGE"),
                  fits.ImageHDU(flags, fh, name="FLAGS")]).writeto(f)
    m = timelapse.measure(f, 10.0, 0.0)
    assert m["usable"] and not m["saturated"] and abs(m["flux"] - 90) < 1e-3
    flags[24, 24] = 2                                           # OVERFLOW bit on the star
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(img, hdr, name="IMAGE"),
                  fits.ImageHDU(flags, fh, name="FLAGS")]).writeto(f, overwrite=True)
    m = timelapse.measure(f, 10.0, 0.0)
    assert m["saturated"] and not m["usable"] and "OVERFLOW" in m["flags"]
