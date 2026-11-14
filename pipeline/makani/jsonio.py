"""Small JSON file helpers shared by the pipeline."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def write_json_atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"), ensure_ascii=False)
    os.chmod(tmp, 0o644)  # mkstemp creates 0600
    os.replace(tmp, path)
