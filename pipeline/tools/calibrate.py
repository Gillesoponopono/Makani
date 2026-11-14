"""Fit the "adjusted forecast": the model's wind corrected with what the anemometers measured.

For each spot that has a nearby anemometer, compares 14+ months of archived
forecasts with the measured wind at the same hours and fits, per situation, a
straight line  measured = a + b x forecast.  Situations: trade-wind direction
(30-100°) or not, day (7 AM-6 PM) or night, because the analysis in
error_factors.py found strength and direction to drive the error, and the
stations behave differently at night.

Reference wind:
- Kanahā, Sprecks: the mean of the Kahului Harbor (NOAA 1615680) and Kahului
  Airport (PHOG) anemometers, 2 km west and 1 km inland. Neither is on the
  beach, so the adjusted curve says "what the anemometers would show", not
  the beach itself.
- Kahului Harbor: the harbor anemometer, at the spot.
- Maui Sunset: the Kealia Pond weather station (USFWS refuge, HADS KPDH1,
  hourly, mph), 5 km north at the top of Kīhei, from the Iowa Environmental
  Mesonet HADS archive.
- Hoʻokipa and Keawakapu have no anemometer: they get their nearest fitted
  neighbour's correction (Sprecks, Maui Sunset), marked "transferred" and not
  checked.

Checked on a time split (fit before 2026-07, test after) before fitting on
everything. Writes config/calibration.json, which build.py applies (wrf.knAdj).

    cd pipeline
    python tools/calibrate.py --work /tmp/makani-errors     # same cache as error_factors.py
"""

from __future__ import annotations

import argparse
import csv
import glob
import urllib.request
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from error_factors import fetch_airport, fetch_archive, fetch_cells, forecasts, load_obs  # noqa: E402
from makani.adjust import group as situation  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPLIT = "2026-07-01"
LEADS = (0, 96)  # hours: what the site shows
B_RANGE = (0.2, 1.5)
HST = timezone(timedelta(hours=-10))
MPH_TO_KN = 0.868976
KEALIA = ("https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py?network=HI_DCP&stations=KPDH1"
          "&sts={start}T00:00Z&ets={end}T00:00Z&what=txt&delim=comma")
# Spots without an anemometer: (gets the fit of, label)
TRANSFERS = {"hookipa": "sprecks", "keawakapu": "maui-sunset"}


def fetch_kealia(work: Path, first: date, last: date) -> dict[str, dict]:
    """Kealia Pond hourly wind by HST hour key (kn), from the IEM HADS archive (cached)."""
    path = work / "kealia_hads.csv"
    if not path.exists():
        print("downloading Kealia Pond history (Iowa Environmental Mesonet HADS) ...", flush=True)
        url = KEALIA.format(start=first.isoformat(), end=(last + timedelta(days=1)).isoformat())
        path.write_bytes(urllib.request.urlopen(url, timeout=240).read())
    out = {}
    for r in csv.DictReader(open(path)):
        if not r.get("USIRGZZ"):
            continue
        t = datetime.strptime(r["utc_valid"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        t = (t + timedelta(minutes=30)).replace(minute=0, second=0)  # :20 reading -> nearest hour
        out[t.astimezone(HST).strftime("%Y-%m-%dT%H")] = {"kn": float(r["USIRGZZ"]) * MPH_TO_KN}
    return out


def fit(rows):
    n = len(rows)
    mf = sum(f for f, _ in rows) / n
    mo = sum(o for _, o in rows) / n
    var = sum((f - mf) ** 2 for f, _ in rows)
    b = sum((f - mf) * (o - mo) for f, o in rows) / var if var else 1.0
    b = max(B_RANGE[0], min(B_RANGE[1], b))
    return {"a": round(mo - b * mf, 2), "b": round(b, 3), "n": n}


def apply(g, kn):
    return max(0.0, g["a"] + g["b"] * kn)


def pairs_for(fc, reference):
    out = []
    for k, lead, kn, d in fc:
        if not (LEADS[0] <= lead < LEADS[1]):
            continue
        o = reference(k)
        if o is not None:
            out.append((k, situation(d, int(k[11:13])), kn, o))
    return out


def mae(xs):
    return sum(map(abs, xs)) / len(xs) if xs else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "config" / "calibration.json")
    args = ap.parse_args()
    work = args.work
    work.mkdir(parents=True, exist_ok=True)
    arch = fetch_archive(work)
    inits = sorted(datetime.strptime(os.path.basename(f)[:13], "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
                   for f in glob.glob(str(arch / "forecast" / "*.json")))
    fetch_cells(work, inits)
    harbor, airport = load_obs(arch, fetch_airport(work, inits[0].date(), date.today()))
    kealia = fetch_kealia(work, inits[0].date(), date.today())
    fc = forecasts(arch, work)

    def both(k):
        if k in harbor and k in airport:
            return (harbor[k]["kn"] + airport[k]["kn"]) / 2
        return None

    setups = {
        "kanaha": (fc["kanaha"], both, "mean of the Kahului Harbor (NOAA 1615680) and Kahului Airport (PHOG) anemometers"),
        "sprecks": (fc["sprecks"], both, "mean of the Kahului Harbor (NOAA 1615680) and Kahului Airport (PHOG) anemometers"),
        "harbor": (fc["harbor-cell"], lambda k: harbor[k]["kn"] if k in harbor else None,
                   "Kahului Harbor anemometer (NOAA 1615680)"),
        "maui-sunset": (fc["maui-sunset"], lambda k: kealia[k]["kn"] if k in kealia else None,
                        "Kealia Pond weather station (USFWS refuge, 5 km north, by a pond inland of the beach)"),
    }
    out = {"generated": date.today().isoformat(), "tool": "pipeline/tools/calibrate.py",
           "model": "measured = a + b x forecast, per group (trade 30-100° or other) x (day 7-18 h or night)",
           "runs": [inits[0].strftime("%Y-%m-%d"), inits[-1].strftime("%Y-%m-%d")], "spots": {}}
    for sid, (series, ref, ref_label) in setups.items():
        rows = pairs_for(series, ref)
        train = [r for r in rows if r[0] < SPLIT]
        test = [r for r in rows if r[0] >= SPLIT]
        fits_train = {g: fit([(kn, o) for _, gg, kn, o in train if gg == g]) for g in {r[1] for r in train}}
        raw_err = [kn - o for _, g, kn, o in test]
        adj_err = [apply(fits_train[g], kn) - o for _, g, kn, o in test if g in fits_train]
        day = [r for r in test if 9 <= int(r[0][11:13]) <= 17]
        raw_day = [kn - o for _, g, kn, o in day]
        adj_day = [apply(fits_train[g], kn) - o for _, g, kn, o in day if g in fits_train]
        fits = {g: fit([(kn, o) for _, gg, kn, o in rows if gg == g]) for g in sorted({r[1] for r in rows})}
        out["spots"][sid] = {
            "reference": ref_label,
            "pairs": len(rows),
            "test": {"from": SPLIT, "maeRaw": round(mae(raw_err), 2), "maeAdj": round(mae(adj_err), 2),
                     "maeRawDay": round(mae(raw_day), 2), "maeAdjDay": round(mae(adj_day), 2),
                     "biasRaw": round(sum(raw_err) / len(raw_err), 2), "biasAdj": round(sum(adj_err) / len(adj_err), 2)},
            "groups": fits,
        }
        t = out["spots"][sid]["test"]
        print(f"{sid:8s} {len(rows):6d} pairs; test after {SPLIT}: MAE {t['maeRaw']:.1f} -> {t['maeAdj']:.1f} kn "
              f"(9-5: {t['maeRawDay']:.1f} -> {t['maeAdjDay']:.1f}), bias {t['biasRaw']:+.1f} -> {t['biasAdj']:+.1f}")
        for g, f in fits.items():
            print(f"         {g:12s} measured = {f['a']:+.2f} + {f['b']:.3f} x forecast  (n={f['n']})")
    names = {"sprecks": "Sprecks", "maui-sunset": "Maui Sunset"}
    for sid, src in TRANSFERS.items():
        out["spots"][sid] = {
            "reference": f"no anemometer here: the {names[src]} correction, transferred",
            "transferredFrom": src,
            "groups": out["spots"][src]["groups"],
        }
        print(f"{sid:8s} gets {src}'s fit (no anemometer)")
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")


if __name__ == "__main__":
    main()
