from makani import adjust

CAL = {"generated": "2026-11-14", "spots": {"kanaha": {
    "reference": "mean of the two anemometers",
    "test": {"maeRawDay": 4.4, "maeAdjDay": 2.8},
    "groups": {"trade-day": {"a": 3.57, "b": 0.541}, "trade-night": {"a": 3.18, "b": 0.411},
               "other-day": {"a": 3.25, "b": 0.697}, "other-night": {"a": 2.07, "b": 0.646}}}}}


def hour(t, kn, d):
    return {"t": t, "wrf": {"kn": kn, "dir": d}}


def test_situations():
    assert adjust.group(70, 14) == "trade-day"
    assert adjust.group(70, 22) == "trade-night"
    assert adjust.group(200, 7) == "other-day"
    assert adjust.group(None, 18) == "other-day"
    assert adjust.group(20, 6) == "other-night"


def test_apply_to_a_calibrated_spot():
    doc = {"id": "kanaha", "hours": [hour("2026-11-14T14:00:00-10:00", 25.0, 70),
                                     hour("2026-11-14T23:00:00-10:00", 20.0, 70),
                                     hour("2026-11-15T12:00:00-10:00", 1.0, 200)]}
    adjust.apply(CAL, doc)
    assert [h["wrf"]["knAdj"] for h in doc["hours"]] == [17.1, 11.4, 3.9]
    assert doc["adjusted"] == {"reference": "mean of the two anemometers", "fitted": "2026-11-14",
                               "maeRaw": 4.4, "maeAdj": 2.8, "transferredFrom": None}


def test_a_transferred_fit_gives_the_curve_without_figures():
    cal = {"generated": "2026-11-14", "spots": {"hookipa": {
        "reference": "no anemometer here", "transferredFrom": "sprecks",
        "groups": CAL["spots"]["kanaha"]["groups"]}}}
    doc = {"id": "hookipa", "hours": [hour("2026-11-14T14:00:00-10:00", 25.0, 70)]}
    adjust.apply(cal, doc)
    assert doc["hours"][0]["wrf"]["knAdj"] == 17.1
    assert doc["adjusted"]["transferredFrom"] == "sprecks" and doc["adjusted"]["maeAdj"] is None


def test_spots_without_calibration_get_nothing():
    doc = {"id": "lanai", "hours": [hour("2026-11-14T14:00:00-10:00", 25.0, 70)]}
    adjust.apply(CAL, doc)
    assert doc["adjusted"] is None and "knAdj" not in doc["hours"][0]["wrf"]
    adjust.apply(None, doc)
    assert doc["adjusted"] is None
