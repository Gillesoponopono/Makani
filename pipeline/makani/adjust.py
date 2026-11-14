"""The "adjusted forecast": the model's wind corrected with measured wind.

config/calibration.json (written by tools/calibrate.py from 14+ months of
archived forecasts vs the Kahului Harbor and Airport anemometers) gives, per
spot and situation, measured = a + b x forecast. Situations: trade-wind
direction (30-100°) or not, day (7 AM-6 PM) or night.

Each hour of a calibrated spot gets `wrf.knAdj`; the document gets an
`adjusted` block (reference, typical miss before/after on the test period).
Spots without an anemometer can carry a neighbour's fit ("transferredFrom"):
they get the curve, with no before/after figures since nothing checks it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def group(direction: float | None, local_hour: int) -> str:
    trade = direction is not None and 30 <= direction <= 100
    return f"{'trade' if trade else 'other'}-{'day' if 7 <= local_hour <= 18 else 'night'}"


def adjusted_kn(cal_spot: dict[str, Any], kn: float, direction: float | None, local_hour: int) -> float | None:
    g = cal_spot["groups"].get(group(direction, local_hour))
    if g is None:
        return None
    return round(max(0.0, g["a"] + g["b"] * kn), 1)


def apply(cal: dict[str, Any] | None, doc: dict[str, Any]) -> None:
    spot = (cal or {}).get("spots", {}).get(doc["id"])
    if not spot:
        doc["adjusted"] = None
        return
    for h in doc["hours"]:
        hour = datetime.fromisoformat(h["t"]).hour  # timestamps are already local (HST)
        h["wrf"]["knAdj"] = adjusted_kn(spot, h["wrf"]["kn"], h["wrf"]["dir"], hour)
    t = spot.get("test") or {}
    doc["adjusted"] = {
        "reference": spot["reference"],
        "fitted": cal.get("generated"),
        "maeRaw": t.get("maeRawDay"),  # kiting hours, on months the fit didn't see
        "maeAdj": t.get("maeAdjDay"),
        "transferredFrom": spot.get("transferredFrom"),
    }
