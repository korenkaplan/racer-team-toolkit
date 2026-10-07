"""Release planning and independent APK/JAR execution regressions."""

from io import StringIO
from threading import Event
from unittest.mock import Mock

import pytest
from rich.console import Console

from racer_team_toolkit.apk_installer.functions import InstallationResult
from racer_team_toolkit.full_release_update import functions as release
from tests.test_apk_installer import make_device


@pytest.mark.parametrize("connected", [False, True])
@pytest.mark.parametrize("has_jar", [False, True])
def test_plan_only_offers_jar_for_reachable_ronen(tmp_path, monkeypatch, connected, has_jar):
    monkeypatch.setattr(release, "is_ssh_server_reachable", lambda **_: connected)
    if has_jar:
        (tmp_path / "racer-groundlord.jar").touch()
    plan = release.build_release_update_plan(tmp_path, [make_device()])
    assert plan.upload_jar == (connected and has_jar)
    stream = StringIO()
    monkeypatch.setattr(release, "console", Console(file=stream))
    release.print_release_update_plan(plan)
    assert ("Racer Groundlord" in stream.getvalue()) == connected
    if not connected:
        prompt = Mock(side_effect=AssertionError("Must not prompt for a disconnected target"))
        upload = Mock(side_effect=AssertionError("Must not upload to a disconnected target"))
        monkeypatch.setattr(release, "select_menu", prompt)
        monkeypatch.setattr(release, "upload_selected_jar", upload)
        assert release.resolve_missing_jar(plan)
        release.change_jar_file(plan, tmp_path / "replacement.jar")
        assert not plan.upload_jar
        assert release.run_jar_update(plan) is None
        prompt.assert_not_called()
        upload.assert_not_called()


@pytest.mark.parametrize("apk_failed", [False, True])
@pytest.mark.parametrize("jar_raises", [False, True])
def test_updates_overlap_and_fail_independently(tmp_path, monkeypatch, apk_failed, jar_raises):
    monkeypatch.setattr(release, "is_ssh_server_reachable", lambda **_: True)
    (tmp_path / "racer-groundlord.jar").touch()
    (tmp_path / "app-debug-test.apk").touch()
    device = make_device()
    plan = release.build_release_update_plan(tmp_path, [device])
    apk_started, jar_started = Event(), Event()
    apk_result = InstallationResult(device, "failed" if apk_failed else "success")

    def install(*_, **__):
        apk_started.set()
        assert jar_started.wait(2), "JAR must start before APK finishes"
        return [apk_result]

    def upload(*_, **__):
        jar_started.set()
        assert apk_started.wait(2), "APK must start before JAR finishes"
        if jar_raises:
            raise OSError("connection lost")
        return True

    monkeypatch.setattr(release, "run_apk_updates", install)
    monkeypatch.setattr(release, "upload_selected_jar", upload)
    report = Mock()
    monkeypatch.setattr(release, "print_release_update_results", report)
    release.execute_release_update(plan)
    report.assert_called_once_with(plan, [apk_result], not jar_raises)
