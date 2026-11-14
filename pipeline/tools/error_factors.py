"""What makes the wind forecast wrong? Forecast vs measured wind, broken down by conditions.

Pairs every archived WRF forecast hour with the wind measured at the same hour at
the two anemometers near Kanahā, then shows how the error changes with the wind
direction, the wind strength, the month, the hour, the air temperature, the
cloud cover and the lead time, and finds the combinations of conditions with the
smallest and largest errors (a small regression tree).

    cd pipeline
    python tools/error_factors.py --work /tmp/makani-errors          # fetches what's missing
    python tools/error_factors.py --work /tmp/makani-errors --csv     # also writes pairs.csv

Data (all public, cached in --work, so later runs are offline and quick):
- archive/ from the repo's `data` branch: forecast runs exactly as issued
  (archive/forecast/, Kanahā and Sprecks cells) and Kahului Harbor anemometer
  hours (archive/obs/1615680/, NOAA CO-OPS, from Oct 2025).
- WRF forecasts at the harbor and airport cells, for the same runs (PacIOOS
  THREDDS; ~600 small requests the first time, a few minutes).
- Kahului Airport (PHOG) hourly reports with air temperature and cloud cover
  (Iowa Environmental Mesonet ASOS archive; the NWS API keeps only 7 days).

Error = forecast - measured, in knots: positive means the model said more wind.
"Kiting hours" are 9 AM-5 PM HST. Each station is compared with its own model
cell; Kanahā's cell against the harbor gives the rider's view.

Two kinds of breakdown:
- by FORECAST conditions (direction and strength the model announced): usable
  before going, "when the model says 22 kn from ENE, expect ...";
- by MEASURED conditions: explains the error, but splitting on the measured
  strength builds in a bias (on calm hours any forecast looks too high), so read
  those rows with that in mind.

Stdlib only, Python 3.9+.
"""

from __future__ import annotations

import argparse
import csv
import glob
import io
import json
import math
import os
import sys
import tarfile
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from makani import thredds  # noqa: E402
from makani.net import http_get  # noqa: E402
from makani.ratings import ms_to_kn, uv_to_speed_dir  # noqa: E402

HST = timezone(timedelta(hours=-10))
KEY = "%Y-%m-%dT%H"
DATA_TARBALL = "https://codeload.github.com/Gillesoponopono/Makani/tar.gz/refs/heads/data"
IEM = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=PHOG&data=sknt&data=drct"
       "&data=tmpf&data=skyc1&data=skyc2&year1={y1}&month1={m1}&day1=1&year2={y2}&month2={m2}&day2={d2}"
       "&tz=Pacific%2FHonolulu&format=onlycomma&latlon=no&missing=null&trace=null&direct=no&report_type=3")
CELLS = {"harbor": (20.902, -156.46), "airport": (20.8925, -156.437)}  # WRF cells at the two anemometers
SECTORS = ["N", "NE", "ENE", "E", "SE", "S", "W", "NW"]
SECTOR_EDGES = [(337.5, 22.5), (22.5, 50), (50, 75), (75, 105), (105, 160), (160, 220), (220, 290), (290, 337.5)]
KN_EDGES = [10, 15, 20, 25]
T_EDGES = [22, 24, 26, 28]
SKY_RANK = {"CLR": 0, "SKC": 0, "FEW": 1, "SCT": 2, "BKN": 3, "OVC": 4, "VV": 4}


# ------------------------------------------------------------------ data

def fetch_archive(work: Path) -> Path:
    arch = work / "archive"
    if not (arch / "forecast").is_dir():
        print("downloading the data branch archive ...", flush=True)
        raw = urllib.request.urlopen(DATA_TARBALL, timeout=120).read()
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            for m in tar.getmembers():
                parts = m.name.split("/", 1)
                if len(parts) == 2 and parts[1].startswith("archive/") and m.isfile():
                    m.name = parts[1]
                    tar.extract(m, work)
    return arch


def fetch_cells(work: Path, inits: list[datetime]) -> None:
    out_dir = work / "cells"
    out_dir.mkdir(exist_ok=True)
    todo = [i for i in inits if not (out_dir / f"{thredds.run_id(i)}.json").exists()]
    if not todo:
        return
    print(f"fetching harbor/airport cell forecasts for {len(todo)} runs from THREDDS ...", flush=True)

    def one(init: datetime) -> None:
        rec = {}
        try:
            for name, (la, lo) in CELLS.items():
                rows = thredds.parse_point_csv(http_get(thredds.point_url(init, la, lo), timeout=60, retries=3, backoff=5))
                rec[name] = [(t.strftime("%Y-%m-%dT%H:%M:%SZ"), u, v) for t, u, v in rows]
        except Exception as exc:  # one missing run is fine
            print(f"  {thredds.run_id(init)}: {exc}", flush=True)
            return
        (out_dir / f"{thredds.run_id(init)}.json").write_text(
            json.dumps({"init": init.strftime("%Y-%m-%dT%H:%M:%SZ"), "cells": rec}))

    with ThreadPoolExecutor(2) as ex:
        list(ex.map(one, todo))


def fetch_airport(work: Path, first: date, last: date) -> Path:
    path = work / "phog_iem.csv"
    if not path.exists():
        print("downloading Kahului Airport history (Iowa Environmental Mesonet) ...", flush=True)
        url = IEM.format(y1=first.year, m1=first.month, y2=last.year, m2=last.month, d2=last.day)
        path.write_bytes(urllib.request.urlopen(url, timeout=180).read())
    return path


def load_obs(arch: Path, phog_csv: Path) -> tuple[dict, dict]:
    harbor = {}
    for f in glob.glob(str(arch / "obs" / "1615680" / "*.json")):
        for k, v in json.load(open(f))["hours"].items():
            if v.get("kn") is not None:
                harbor[k] = {"kn": v["kn"], "dir": v.get("dir")}
    airport = {}
    for r in csv.DictReader(open(phog_csv)):
        if r["sknt"] in ("null", ""):
            continue
        t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M") + timedelta(minutes=30)  # 13:54 report -> 14:00
        num = lambda s: None if s in ("null", "", None) else float(s)  # noqa: E731
        tf = num(r.get("tmpf"))
        sky = max((SKY_RANK.get(r.get(c) or "", -1) for c in ("skyc1", "skyc2")), default=-1)
        airport[t.strftime(KEY)] = {"kn": float(r["sknt"]), "dir": num(r["drct"]),
                                    "tairC": None if tf is None else (tf - 32) * 5 / 9,
                                    "sky": sky if sky >= 0 else None}
    return harbor, airport


def forecasts(arch: Path, work: Path) -> dict[str, list[tuple[str, float, float, int]]]:
    """source -> [(valid HST hour key, lead h, kn, dir)]"""
    out: dict[str, list] = defaultdict(list)
    for f in sorted(glob.glob(str(arch / "forecast" / "*.json"))):
        run = json.load(open(f))
        init = datetime.fromisoformat(run["init"].replace("Z", "+00:00"))
        start = datetime.fromisoformat(run["start"])
        for sid in ("kanaha", "sprecks"):
            sp = run["spots"].get(sid)
            for i, (kn, d) in enumerate(zip(sp["kn"], sp["dir"]) if sp else []):
                if kn is not None:
                    t = start + timedelta(hours=i)
                    out[sid].append((t.astimezone(HST).strftime(KEY), (t - init).total_seconds() / 3600, kn, d))
    for f in sorted(glob.glob(str(work / "cells" / "*.json"))):
        rec = json.load(open(f))
        init = datetime.fromisoformat(rec["init"].replace("Z", "+00:00"))
        for cell, rows in rec["cells"].items():
            for ts, u, v in rows:
                if u is None or v is None:
                    continue
                t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                ms, d = uv_to_speed_dir(u, v)
                out[cell + "-cell"].append((t.astimezone(HST).strftime(KEY), (t - init).total_seconds() / 3600,
                                            ms_to_kn(ms), d))
    return out


def pairs(fc: list, obs: dict, airport: dict, lead=(24, 72), hours=(9, 17)) -> list[dict]:
    rows = []
    for k, ld, kn, d in fc:
        h = int(k[11:13])
        if not (lead[0] <= ld < lead[1] and hours[0] <= h <= hours[1]) or k not in obs:
            continue
        o = obs[k]
        env = airport.get(k, {})
        rows.append({"t": k, "month": int(k[5:7]), "hour": h, "lead": ld, "fc_kn": kn, "fc_dir": d,
                     "obs_kn": o["kn"], "obs_dir": o.get("dir"), "tairC": env.get("tairC"), "sky": env.get("sky"),
                     "err": kn - o["kn"]})
    return rows


# ------------------------------------------------------------------ stats

def sector(d):
    if d is None:
        return None
    d %= 360
    for name, (a, b) in zip(SECTORS, SECTOR_EDGES):
        if (a <= d < b) if a < b else (d >= a or d < b):
            return name
    return None


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))]


def summary(rows):
    e = [r["err"] for r in rows]
    n = len(e)
    mo = sum(r["obs_kn"] for r in rows) / n
    mae = sum(map(abs, e)) / n
    return {"n": n, "bias": sum(e) / n, "mae": mae, "rel": mae / mo if mo else float("nan"),
            "p10": pct(e, 0.1), "p90": pct(e, 0.9), "w3": sum(abs(x) <= 3 for x in e) / n, "obs": mo}


def line(label, s):
    return (f"  {label:22s} n={s['n']:5d}  bias {s['bias']:+5.1f}  MAE {s['mae']:4.1f} kn ({s['rel']:4.0%} of measured "
            f"{s['obs']:4.1f})  80% of errors in [{s['p10']:+5.1f}, {s['p90']:+5.1f}]  within 3 kn {s['w3']:4.0%}")


def breakdown(rows, title, key, order=None, min_n=60):
    groups = defaultdict(list)
    for r in rows:
        g = key(r)
        if g is not None:
            groups[g].append(r)
    keys = order if order else sorted(groups)
    print(f"\n{title}")
    for g in keys:
        if len(groups.get(g, [])) >= min_n:
            print(line(str(g), summary(groups[g])))
    return groups


def influence(rows, key):
    """Share of the error explained by a factor: MAE after removing the overall bias
    vs after removing each group's own bias (how much a per-group correction helps)."""
    gb = defaultdict(list)
    for r in rows:
        g = key(r)
        gb[g].append(r["err"])
    overall = sum(r["err"] for r in rows) / len(rows)
    base = sum(abs(r["err"] - overall) for r in rows) / len(rows)
    means = {g: sum(v) / len(v) for g, v in gb.items()}
    after = sum(abs(r["err"] - means[key(r)]) for r in rows) / len(rows)
    # spread: how different the typical error size is between groups (largest vs smallest MAE, groups >= 60)
    maes = [sum(map(abs, v)) / len(v) for v in gb.values() if len(v) >= 60]
    return base, after, (min(maes), max(maes)) if maes else (float("nan"),) * 2


# ------------------------------------------------------------------ regression tree

FEATURES = {
    "forecast direction": lambda r: sector(r["fc_dir"]),
    "forecast strength": lambda r: r["fc_kn"],
    "month": lambda r: r["month"],
    "hour": lambda r: r["hour"],
    "air temperature": lambda r: r["tairC"],
    "cloud cover": lambda r: r["sky"],
}
NUMERIC = {"forecast strength", "month", "hour", "air temperature", "cloud cover"}


def best_split(rows, target, min_leaf):
    """Best single split on the sum of squared target deviations: (sse, label, opposite label, goes_left)."""
    best = None
    for name, f in FEATURES.items():
        vals = [(f(r), target(r)) for r in rows if f(r) is not None]
        if len(vals) < 2 * min_leaf:
            continue
        if name in NUMERIC:
            ordered = sorted(vals, key=lambda x: x[0])
            keyed = [(v, y) for v, y in ordered]
        else:  # categories ranked by mean target, then split like a number
            cats = defaultdict(list)
            for v, y in vals:
                cats[v].append(y)
            rank = sorted(cats, key=lambda c: sum(cats[c]) / len(cats[c]))
            keyed = sorted(((rank.index(v), y) for v, y in vals), key=lambda x: x[0])
        ys = [y for _, y in keyed]
        m, s_tot, sq_tot = len(ys), sum(ys), sum(y * y for y in ys)
        s_left = sq_left = 0.0
        for i in range(1, m):
            s_left += ys[i - 1]
            sq_left += ys[i - 1] ** 2
            if i < min_leaf or m - i < min_leaf or keyed[i][0] == keyed[i - 1][0]:
                continue
            sse = (sq_left - s_left ** 2 / i) + ((sq_tot - sq_left) - (s_tot - s_left) ** 2 / (m - i))
            if best is None or sse < best[0]:
                thr = keyed[i][0]
                if name in NUMERIC:
                    best = (sse, f"{name} < {thr:.0f}", f"{name} >= {thr:.0f}",
                            (lambda f, thr: lambda r: f(r) is not None and f(r) < thr)(f, thr))
                else:
                    left = set(rank[:thr])
                    best = (sse, f"{name} in {{{', '.join(sorted(map(str, left)))}}}",
                            f"{name} not in {{{', '.join(sorted(map(str, left)))}}}",
                            (lambda f, left: lambda r: f(r) in left)(f, left))
    return best


def grow(rows, target, depth, min_leaf, path=()):
    split = best_split(rows, target, min_leaf) if depth > 0 else None
    if split is None:
        return [(path, rows)]
    _, label, neg, goes_left = split
    left = [r for r in rows if goes_left(r)]
    right = [r for r in rows if not goes_left(r)]
    if len(left) < min_leaf or len(right) < min_leaf:
        return [(path, rows)]
    return grow(left, target, depth - 1, min_leaf, path + (label,)) + \
        grow(right, target, depth - 1, min_leaf, path + (neg,))


def tree_report(rows, title, depth=3, min_leaf=150):
    print(f"\n{title} (regression tree on the error size, leaves of {min_leaf}+ hours):")
    leaves = grow(rows, lambda r: abs(r["err"]), depth, min_leaf)
    out = []
    for path, rs in leaves:
        s = summary(rs)
        out.append((s["mae"], " & ".join(path) or "all", s))
    for _, label, s in sorted(out, key=lambda x: x[0]):
        print(f"  MAE {s['mae']:4.1f} kn ({s['rel']:4.0%})  bias {s['bias']:+4.1f}  80% in [{s['p10']:+5.1f}, {s['p90']:+5.1f}]"
              f"  n={s['n']:4d}  <- {label}")


# ------------------------------------------------------------------ main

def report(name, rows):
    print("\n" + "=" * 100)
    print(f"{name}: forecast made 1-2 days ahead, kiting hours")
    print(line("all hours", summary(rows)))

    trades = lambda r: r["fc_dir"] is not None and 30 <= r["fc_dir"] <= 100  # noqa: E731
    breakdown(rows, "By FORECAST direction:", lambda r: sector(r["fc_dir"]), SECTORS)
    breakdown(rows, "By FORECAST strength:", lambda r: _bin(r["fc_kn"], KN_EDGES, "kn"), _bin_labels(KN_EDGES, "kn"))
    breakdown([r for r in rows if trades(r)], "Trade-wind forecasts (30-100°) by FORECAST strength:",
              lambda r: _bin(r["fc_kn"], KN_EDGES, "kn"), _bin_labels(KN_EDGES, "kn"))
    breakdown(rows, "By MEASURED direction:", lambda r: sector(r["obs_dir"]), SECTORS)
    breakdown(rows, "By MEASURED strength (see the note in the header):", lambda r: _bin(r["obs_kn"], KN_EDGES, "kn"),
              _bin_labels(KN_EDGES, "kn"))
    breakdown(rows, "By month:", lambda r: f"{r['month']:02d}")
    breakdown(rows, "By season:", lambda r: "dry May-Sep" if 5 <= r["month"] <= 9 else "wet Oct-Apr")
    breakdown(rows, "By hour:", lambda r: f"{r['hour']:02d}h")
    breakdown(rows, "By air temperature at the airport:", lambda r: _bin(r["tairC"], T_EDGES, "°C"),
              _bin_labels(T_EDGES, "°C"))
    breakdown(rows, "By cloud cover at the airport:", lambda r: {0: "clear", 1: "few clouds", 2: "scattered",
                                                              3: "broken", 4: "overcast"}.get(r["sky"]),
              ["clear", "few clouds", "scattered", "broken", "overcast"])
    breakdown(rows, "By lead time:", lambda r: f"{int(r['lead'] // 24)} day(s) ahead")

    print("\nInfluence of each factor (MAE once a per-group bias correction is applied; lower = the factor "
          "explains more of the error):")
    for label, key in [("forecast direction", lambda r: sector(r["fc_dir"])),
                       ("forecast strength", lambda r: _bin(r["fc_kn"], KN_EDGES, "kn")),
                       ("direction x strength", lambda r: (sector(r["fc_dir"]), _bin(r["fc_kn"], KN_EDGES, "kn"))),
                       ("month", lambda r: r["month"]),
                       ("hour", lambda r: r["hour"]),
                       ("air temperature", lambda r: _bin(r["tairC"], T_EDGES, "°C")),
                       ("cloud cover", lambda r: r["sky"])]:
        base, after, (lo, hi) = influence(rows, key)
        print(f"  {label:22s} {base:4.2f} -> {after:4.2f} kn ({(base - after) / base:5.1%} better); "
              f"typical error from {lo:.1f} to {hi:.1f} kn between groups")

    tree_report(rows, "Conditions with the smallest and largest errors")


def _bin(v, edges, unit):
    if v is None:
        return None
    return _bin_labels(edges, unit)[sum(v >= e for e in edges)]


def _bin_labels(edges, unit):
    return [f"< {edges[0]} {unit}"] + [f"{a}-{b} {unit}" for a, b in zip(edges, edges[1:])] + [f">= {edges[-1]} {unit}"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--work", type=Path, required=True, help="cache directory")
    ap.add_argument("--csv", action="store_true", help="also write pairs.csv (all pairs, all leads, all hours)")
    args = ap.parse_args()
    work = args.work
    work.mkdir(parents=True, exist_ok=True)

    arch = fetch_archive(work)
    inits = sorted(datetime.strptime(os.path.basename(f)[:13], "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
                   for f in glob.glob(str(arch / "forecast" / "*.json")))
    fetch_cells(work, inits)
    phog = fetch_airport(work, inits[0].date(), date.today())
    harbor, airport = load_obs(arch, phog)
    fc = forecasts(arch, work)
    print(f"{len(inits)} forecast runs ({inits[0]:%Y-%m-%d} to {inits[-1]:%Y-%m-%d}); "
          f"{len(harbor)} harbor hours, {len(airport)} airport hours measured")

    sets = {
        "Kahului Harbor anemometer vs its model cell": pairs(fc["harbor-cell"], harbor, airport),
        "Kahului Airport anemometer vs its model cell": pairs(fc["airport-cell"], airport, airport),
        "Kahului Harbor anemometer vs the Kanaha forecast (rider's view)": pairs(fc["kanaha"], harbor, airport),
    }
    for name, rows in sets.items():
        report(name, rows)

    if args.csv:
        out = work / "pairs.csv"
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["station", "forecast", "valid_hst", "lead_h", "month", "hour", "fc_kn", "fc_dir",
                        "obs_kn", "obs_dir", "air_temp_c", "cloud_0_4", "error_kn"])
            for st, obs, src in [("harbor", harbor, "harbor-cell"), ("airport", airport, "airport-cell"),
                                 ("harbor", harbor, "kanaha"), ("airport", airport, "kanaha"),
                                 ("harbor", harbor, "sprecks"), ("airport", airport, "sprecks")]:
                for r in pairs(fc[src], obs, airport, lead=(0, 200), hours=(0, 23)):
                    w.writerow([st, src, r["t"], round(r["lead"]), r["month"], r["hour"], round(r["fc_kn"], 1),
                                r["fc_dir"], r["obs_kn"], r["obs_dir"],
                                None if r["tairC"] is None else round(r["tairC"], 1), r["sky"], round(r["err"], 1)])
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
