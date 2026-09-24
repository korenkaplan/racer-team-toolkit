"""Tests for camera source switching in run_java.sh."""

from racer_team_toolkit.jar_management.config import (
    CAMERA_MODE_RTSP,
    CAMERA_MODE_SHARPEYE,
)
from racer_team_toolkit.jar_management.functions import (
    build_camera_mode_script,
    get_camera_mode_from_script,
)

SHARPEYE_LINE = (
    'RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight '
    '-camera racer-airlord-rtsp-tcp -imuRecord imuRecord '
    '-targeting SHARPEYES -airlordHost 192.168.144.8 -airlordPort 5001"'
)
RTSP_LINE = (
    'RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight '
    '-camera lumenier-rtsp -imuRecord imuRecord"'
)
ATALEF_LINE = 'RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight -camera atalef"'
SKYDROID_LINE = 'RUN_CMD="$RUN_CMD -model EDI_READY -sdkType MAVLINK -camera skydroid"'

BASE_SCRIPT = "\n".join(
    [
        "#!/bin/bash",
        'if [[ "$JAR_BASENAME" == "racer-groundlord.jar" ]]; then',
        f"    #{ATALEF_LINE}",
        f"    #{SHARPEYE_LINE}",
        f"    {RTSP_LINE}",
        f"    #{SKYDROID_LINE}",
        "fi",
        "",
    ]
)


def test_switch_to_sharpeye_mode() -> None:
    """SharpEye becomes active and RTSP becomes commented."""

    updated = build_camera_mode_script(
        BASE_SCRIPT,
        CAMERA_MODE_SHARPEYE,
    )

    assert f"    {SHARPEYE_LINE}" in updated
    assert f"    #{RTSP_LINE}" in updated
    assert get_camera_mode_from_script(updated) == CAMERA_MODE_SHARPEYE


def test_switch_to_rtsp_mode() -> None:
    """RTSP becomes active and SharpEye becomes commented."""

    sharpeye_script = build_camera_mode_script(
        BASE_SCRIPT,
        CAMERA_MODE_SHARPEYE,
    )

    updated = build_camera_mode_script(
        sharpeye_script,
        CAMERA_MODE_RTSP,
    )

    assert f"    #{SHARPEYE_LINE}" in updated
    assert f"    {RTSP_LINE}" in updated
    assert get_camera_mode_from_script(updated) == CAMERA_MODE_RTSP


def test_switch_preserves_other_camera_lines() -> None:
    """Unrelated Atalef and Skydroid lines are not changed."""

    updated = build_camera_mode_script(
        BASE_SCRIPT,
        CAMERA_MODE_SHARPEYE,
    )

    assert f"    #{ATALEF_LINE}" in updated
    assert f"    #{SKYDROID_LINE}" in updated


def test_switch_adds_missing_supported_mode() -> None:
    """A missing supported camera line is restored next to the existing one."""

    script_without_sharpeye = "\n".join(
        [
            "#!/bin/bash",
            'if [[ "$JAR_BASENAME" == "racer-groundlord.jar" ]]; then',
            f"    {RTSP_LINE}",
            "fi",
            "",
        ]
    )

    updated = build_camera_mode_script(
        script_without_sharpeye,
        CAMERA_MODE_SHARPEYE,
    )

    assert f"    {SHARPEYE_LINE}" in updated
    assert f"    #{RTSP_LINE}" in updated
    assert get_camera_mode_from_script(updated) == CAMERA_MODE_SHARPEYE
