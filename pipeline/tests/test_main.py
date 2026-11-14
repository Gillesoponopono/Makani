"""Decision logic of the hourly pass (network calls replaced by fakes)."""

from datetime import datetime, timedelta, timezone

import pytest

from makani import archive, build as build_mod, obs, thredds
from makani.jsonio import write_json_atomic
from makani.net import FetchError


@pytest.fixture
def calls(monkeypatch, tmp_path):
    rec = {"build": 0, "thredds": [], "obs": 0, "new_run": False, "obs_updated": 2, "runs_added": 1,
           "erddap_down": False}

    def fake_build(out, force=False, now=None):
        rec["build"] += 1
        if rec["erddap_down"]:
            raise FetchError("Connection timed out")
        return rec["new_run"] or force

    def fake_thredds(out, spots, tz, now, days=10, **kw):
        rec["thredds"].append(days)
        return {"status": "ok", "added": rec["runs_added"], "pending": [], "errors": 0}

    def fake_obs(out, stations, tz, now, days=7, **kw):
        rec["obs"] += 1
        return {"PHOG": {"status": "ok", "updated": rec["obs_updated"]}}

    monkeypatch.setattr(build_mod, "build", fake_build)
    monkeypatch.setattr(thredds, "update_forecast_archive", fake_thredds)
    monkeypatch.setattr(obs, "update_obs", fake_obs)
    gh_out = tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh_out))
    rec["out"] = tmp_path / "data"
    rec["gh_out"] = gh_out
    (rec["out"] / "archive" / "forecast").mkdir(parents=True)
    (rec["out"] / "archive" / "forecast" / "2026-11-11T00Z.json").write_text(
        '{"run": "2026-11-11T00Z", "init": "2026-11-11T00:00:00Z", '
        '"start": "2026-11-10T20:00:00-10:00", "hours": 163, "spots": {}}')
    return rec


def run(calls, *extra, expect_rc=0):
    calls["gh_out"].write_text("")
    assert build_mod.main(["--out", str(calls["out"]), *extra]) == expect_rc
    return calls["gh_out"].read_text().strip()


def test_quiet_hour_is_one_cheap_check(calls):
    archive.write_index(calls["out"], obs_status={"PHOG": {"status": "ok"}},
                        now=datetime.now(timezone.utc) - timedelta(hours=2))
    out = run(calls, "--obs-every-hours", "6")
    assert calls["build"] == 1          # only the coverage-end check inside build()
    assert calls["thredds"] == [] and calls["obs"] == 0
    assert out == "changed=false"


def test_observations_refresh_when_due(calls):
    archive.write_index(calls["out"], obs_status={"PHOG": {"status": "ok"}},
                        now=datetime.now(timezone.utc) - timedelta(hours=5, minutes=40))
    assert run(calls, "--obs-every-hours", "6") == "changed=true"
    assert calls["obs"] == 1 and calls["thredds"] == []


def test_new_run_triggers_archive_scan(calls):
    calls["new_run"] = True
    calls["obs_updated"] = 0
    archive.write_index(calls["out"], obs_status={"PHOG": {"status": "ok"}}, now=datetime.now(timezone.utc))
    assert run(calls, "--obs-every-hours", "6") == "changed=true"
    assert calls["thredds"] == [10] and calls["obs"] == 0


def test_backfill_scans_even_without_new_run(calls):
    calls["obs_updated"] = 0
    assert run(calls, "--forecast-days", "400", "--obs-days", "400") == "changed=true"
    assert calls["thredds"] == [400] and calls["obs"] == 1


def test_nothing_new_anywhere_is_unchanged(calls):
    calls["obs_updated"] = 0
    calls["runs_added"] = 0
    assert run(calls, "--forecast-days", "400") == "changed=false"


def _meta(calls, hours_old):
    stamp = (datetime.now(timezone.utc) - timedelta(hours=hours_old)).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_json_atomic(calls["out"] / "meta.json", {"generatedAt": stamp})


def test_erddap_outage_keeps_site_and_still_updates_observations(calls):
    calls["erddap_down"] = True
    _meta(calls, hours_old=5)
    assert run(calls) == "changed=true"   # observations still merged
    assert calls["obs"] == 1 and calls["thredds"] == []


def test_erddap_outage_fails_only_when_site_data_is_stale(calls):
    calls["erddap_down"] = True
    calls["obs_updated"] = 0
    _meta(calls, hours_old=30)
    assert run(calls, expect_rc=1) == "changed=false"
