"""Group exposures into visits: split the time-sorted list wherever the gap exceeds ~30 days."""
from __future__ import annotations

GAP_DAYS = 30.0


def group_visits(exps, gap_days: float = GAP_DAYS):
    exps = sorted(exps, key=lambda e: e.t_start_mjd)
    visit, last = 0, None
    for e in exps:
        if last is not None and e.t_start_mjd - last > gap_days:
            visit += 1
        e.visit = visit
        last = e.t_start_mjd
    return exps


def _spread(items: list, n: int) -> list:
    """Pick n items evenly spaced through the list (keeps first and last)."""
    if n >= len(items):
        return list(items)
    if n == 1:
        return [items[len(items) // 2]]
    step = (len(items) - 1) / (n - 1)
    return [items[round(i * step)] for i in range(n)]


def select_frames(exps, per_visit: int | None = None, limit: int | None = None):
    """Choose frames so every visit is represented.

    per_visit: at most this many per visit, evenly spaced in time.
    limit:     overall cap, filled round-robin across visits (never all from one visit).
    """
    by_visit: dict[int, list] = {}
    for e in sorted(exps, key=lambda e: e.t_start_mjd):
        by_visit.setdefault(e.visit, []).append(e)
    groups = [by_visit[v] for v in sorted(by_visit)]
    if per_visit:
        groups = [_spread(g, per_visit) for g in groups]
    total = sum(len(g) for g in groups)
    if limit and total > limit:
        # share the limit evenly; leftovers go to visits that still have frames
        quota = [0] * len(groups)
        left = limit
        while left > 0:
            for i, g in enumerate(groups):
                if left and quota[i] < len(g):
                    quota[i] += 1
                    left -= 1
        groups = [_spread(g, q) for g, q in zip(groups, quota) if q]
    return sorted((e for g in groups for e in g), key=lambda e: e.t_start_mjd)


def summarize(exps) -> list[dict]:
    out: dict[int, dict] = {}
    for e in exps:
        v = out.setdefault(e.visit, {"visit": e.visit, "n_exposures": 0,
                                     "first": e.t_start_iso, "last": e.t_start_iso,
                                     "detectors": set()})
        v["n_exposures"] += 1
        v["last"] = e.t_start_iso
        v["detectors"].add(e.detector)
    for v in out.values():
        v["detectors"] = sorted(v["detectors"])
    return [out[k] for k in sorted(out)]
