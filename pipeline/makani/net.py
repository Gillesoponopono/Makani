"""HTTP GET with a User-Agent, long timeout and retries (stdlib only)."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Callable

from . import USER_AGENT

Fetcher = Callable[[str], bytes]


class FetchError(RuntimeError):
    pass


def http_get(url: str, timeout: float = 300.0, retries: int = 3, backoff: float = 15.0) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            # 4xx (bad query, no data in range) won't fix itself; 5xx/proxy errors might.
            if exc.code < 500:
                raise FetchError(f"HTTP {exc.code} for {url}: {exc.read()[:300]!r}") from exc
            last = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
        if attempt < retries - 1:
            time.sleep(backoff * (3 ** attempt))
    raise FetchError(f"giving up after {retries} attempts: {url}: {last}")
