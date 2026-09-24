"""Tests for camera source switching in run_java.sh."""

from racer_team_toolkit.jar_management.config import (
    CAMERA_MODE_RTSP,
    CAMERA_MODE_SHARPEYE,
)
from racer_team_toolkit.jar_management.functions import (
    build_camera_mode_script,
    get_camera_mode_from_script,
)


BASE_SCRIPT = """#!/bin/bash
if [[ "$JAR_BASENAME" == "racer-groundlord.jar" ]]; then
    #RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight -camera atalef"
    #RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight -camera racer-airlord-rtsp-tcp -imuRecord imuRecord -targeting SHARPEYES -airlordHost 192.168.144.8 -airlordPort 5001"
    RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight -camera lumenier-rtsp -imuRecord imuRecord"
    #RUN_CMD="$RUN_CMD -model EDI_READY -sdkType MAVLINK -camera skydroid"
fi
"""


def test_switch_to_sharpeye_mode() -> None:
    """SharpEye becomes active and RTSP becomes commented."""

    updated = build_camera_mode_script(
        BASE_SCRIPT,
        CAMERA_MODE_SHARPEYE,
    )

    assert (
        '    RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight '
        '-camera racer-airlord-rtsp-tcp -imuRecord imuRecord '
        '-targeting SHARPEYES -airlordHost 192.168.144.8 -airlordPort 5001"'
        in updated
    )
    assert (
        '    #RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight '
        '-camera lumenier-rtsp -imuRecord imuRecord"'
        in updated
    )
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

    assert (
        '    #RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight '
        '-camera racer-airlord-rtsp-tcp -imuRecord imuRecord '
        '-targeting SHARPEYES -airlordHost 192.168.144.8 -airlordPort 5001"'
        in updated
    )
    assert (
        '    RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight '
        '-camera lumenier-rtsp -imuRecord imuRecord"'
        in updated
    )
    assert get_camera_mode_from_script(updated) == CAMERA_MODE_RTSP


def test_switch_preserves_other_camera_lines() -> None:
    """Unrelated Atalef and Skydroid lines are not changed."""

    updated = build_camera_mode_script(
        BASE_SCRIPT,
        CAMERA_MODE_SHARPEYE,
    )

    assert (
        '    #RUN_CMD="$RUN_CMD -model Lumenier -sdkType betaflight -camera atalef"'
        in updated
    )
    assert (
        '    #RUN_CMD="$RUN_CMD -model EDI_READY -sdkType MAVLINK -camera skydroid"'
        in updated
    )
