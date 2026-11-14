"""Load the shared JSON config in <repo>/config."""

from __future__ import annotations

import json
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _load(name: str, config_dir: Path | None = None) -> dict[str, Any]:
    path = (config_dir or CONFIG_DIR) / name
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_spots(config_dir: Path | None = None) -> dict[str, Any]:
    return _load("spots.json", config_dir)


def load_ratings(config_dir: Path | None = None) -> dict[str, Any]:
    return _load("ratings.json", config_dir)


def local_tz(spots_cfg: dict[str, Any]) -> timezone:
    """Hawaii has no DST, so a fixed offset is exact."""
    return timezone(timedelta(hours=spots_cfg["utcOffsetHours"]), "HST")
