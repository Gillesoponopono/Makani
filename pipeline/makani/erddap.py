"""Minimal ERDDAP griddap client for the PacIOOS WRF Maui-Oahu dataset (wrf_mo).

Stdlib only. The server can be slow or return proxy errors, so every request
has a long timeout and retries with backoff.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, Sequence

from .net import FetchError, Fetcher, http_get

BASE_URL = "https://pae-paha.pacioos.hawaii.edu/erddap"
DATASET = "wrf_mo"

__all__ = ["ErddapError", "Fetcher", "http_get", "coverage_end", "point_series", "griddap_url", "parse_table"]


class ErddapError(FetchError):
    pass


def _axis(start: str, stop: str, stride: int = 1) -> str:
    return f"[({start}):{stride}:({stop})]"


def griddap_url(variables: Sequence[str], time_start: str, lat: tuple[float, float],
                lon: tuple[float, float], time_end: str = "last", stride: int = 1,
                fmt: str = "json") -> str:
    """Build a griddap query. Times are ISO-8601 UTC strings or 'last'."""
    axes = (_axis(time_start, time_end)
            + _axis(f"{lat[0]:g}", f"{lat[1]:g}", stride)
            + _axis(f"{lon[0]:g}", f"{lon[1]:g}", stride))
    query = ",".join(v + axes for v in variables)
    return f"{BASE_URL}/griddap/{DATASET}.{fmt}?" + urllib.parse.quote(query, safe="(),:")


def parse_table(raw: bytes) -> list[dict[str, Any]]:
    """Parse ERDDAP .json table output into a list of row dicts."""
    try:
        doc = json.loads(raw)
    except ValueError as exc:  # proxy error pages come back as HTML
        raise ErddapError(f"non-JSON response: {raw[:200]!r}") from exc
    table = doc["table"]
    cols = table["columnNames"]
    return [dict(zip(cols, row)) for row in table["rows"]]


def coverage_end(fetch: Fetcher = http_get) -> str:
    """time_coverage_end of the dataset: changes whenever a new model run lands."""
    raw = fetch(f"{BASE_URL}/info/{DATASET}/index.csv").decode("utf-8", "replace")
    for line in raw.splitlines():
        parts = line.split(",", 4)
        if len(parts) == 5 and parts[1] == "NC_GLOBAL" and parts[2] == "time_coverage_end":
            return parts[4].strip().strip('"')
    raise ErddapError("time_coverage_end not found in dataset info")


def point_series(lat: float, lon: float, time_start: str, variables: Sequence[str],
                 fetch: Fetcher = http_get) -> list[dict[str, Any]]:
    """Hourly rows for the grid cell nearest (lat, lon), from time_start to the end of the run."""
    url = griddap_url(variables, time_start, (lat, lat), (lon, lon))
    return parse_table(fetch(url))
