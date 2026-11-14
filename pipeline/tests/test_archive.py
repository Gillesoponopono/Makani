import json
from datetime import datetime, timedelta, timezone

from makani import archive
from makani.jsonio import write_json_atomic


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def run_file(tmp_path, run, legacy=False):
    rec = {"run": run, "start": "2026-11-10T20:00:00-10:00", "hours": 163, "spots": {}}
    if not legacy:
        rec["init"] = run[:13] + ":00:00Z"
    write_json_atomic(tmp_path / "archive" / "forecast" / f"{run}.json", rec)


def test_migrate_removes_only_legacy_records(tmp_path):
    run_file(tmp_path, "2026-11-18T00Z", legacy=True)   # M1 format, named by coverage end
    run_file(tmp_path, "2026-11-11T00Z")
    assert archive.migrate_legacy(tmp_path) == 1
    assert [p.name for p in (tmp_path / "archive" / "forecast").iterdir()] == ["2026-11-11T00Z.json"]
    assert archive.migrate_legacy(tmp_path) == 0


def test_index_lists_runs_and_obs_and_keeps_last_good_status(tmp_path):
    run_file(tmp_path, "2026-11-10T00Z")
    run_file(tmp_path, "2026-11-11T00Z")
    write_json_atomic(tmp_path / "archive" / "obs" / "PHOG" / "2026-11.json", {"hours": {}})
    t0 = utc(2026, 11, 14, 4)

    idx = archive.write_index(tmp_path, obs_status={"PHOG": {"status": "ok", "updated": 3}},
                              forecast_status={"status": "ok", "added": 2}, now=t0)
    assert [r["run"] for r in idx["forecastRuns"]] == ["2026-11-10T00Z", "2026-11-11T00Z"]
    assert idx["obs"] == {"PHOG": ["2026-11"]}
    assert idx["obsStatus"]["PHOG"]["lastOkAt"] == "2026-11-14T04:00:00Z"
    assert idx["forecastStatus"]["added"] == 2

    # Nothing checked this time: statuses carried over unchanged.
    idx = archive.write_index(tmp_path, now=t0 + timedelta(hours=1))
    assert idx["obsStatus"]["PHOG"]["checkedAt"] == "2026-11-14T04:00:00Z"
    assert idx["forecastStatus"]["checkedAt"] == "2026-11-14T04:00:00Z"

    # Failure keeps the last good time.
    idx = archive.write_index(tmp_path, obs_status={"PHOG": {"status": "error"}},
                              forecast_status={"status": "error"}, now=t0 + timedelta(hours=6))
    assert idx["obsStatus"]["PHOG"]["lastOkAt"] == "2026-11-14T04:00:00Z"
    assert idx["forecastStatus"]["lastOkAt"] == "2026-11-14T04:00:00Z"
    assert archive.count_files(tmp_path) == 3


def test_obs_checked_hours_ago_uses_oldest_station(tmp_path):
    assert archive.obs_checked_hours_ago(tmp_path, utc(2026, 11, 14)) is None
    archive.write_index(tmp_path, obs_status={"PHOG": {"status": "ok"}}, now=utc(2026, 11, 14, 0))
    archive.write_index(tmp_path, obs_status={"1615680": {"status": "ok"}}, now=utc(2026, 11, 14, 3))
    assert archive.obs_checked_hours_ago(tmp_path, utc(2026, 11, 14, 5)) == 5.0
    json.loads((tmp_path / "archive" / "index.json").read_text())
