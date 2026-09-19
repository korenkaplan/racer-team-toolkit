"""Central configuration for the Racer Team Toolkit."""

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


def get_env_path() -> Path:
    """Return the .env path for development or packaged builds."""

    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / ".env"  # type: ignore[attr-defined]

    return Path.cwd() / ".env"


load_dotenv(get_env_path())


@dataclass
class AndroidDevice:
    """Represents an Android device connected to the computer."""

    name: str
    serial: str
    remote_log_path: str
    file_prefix: str
    apk_name_pattern: str
    package_name: str
    permissions: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeviceTypeConfig:
    """Configuration shared by all devices of the same type."""

    name: str
    remote_log_path: str
    file_prefix: str
    apk_name_pattern: str
    package_name: str
    permissions: tuple[str, ...] = ()


# Shared ADB and device settings.
today_str = datetime.now().strftime("%d-%m-%Y")
home = Path.home()
onedrive_desktop = home / "OneDrive" / "Desktop"
standard_desktop = home / "Desktop"
VIDEO_FILE_PREFIX = "VIDEO"
DESKTOP_PATH = onedrive_desktop if onedrive_desktop.exists() else standard_desktop
LOCAL_DUMP_DIR = str(DESKTOP_PATH / f"Reff_{today_str}")
VIDEO_REMOTE_PATH = "/sdcard/Eyesatop-Records/Screen-Videos"
DEVICE_MODEL_RULES = {
    "ISR": ("rcpad",),
    "RACER": ("djircplus",),
    "TABLET": ("smx",),
    "BLACK_WIDOW": (),
}
DEVICE_TYPE_CONFIGS = {
    "RACER": DeviceTypeConfig(
        name="Racer Controller",
        remote_log_path="/sdcard/Records",
        file_prefix="RACER",
        apk_name_pattern="app-dynamic-msdk5-debug*.apk",
        package_name="io.eyesatop.app.dynamic.msdk5",
    ),
    "ISR": DeviceTypeConfig(
        name="ISR Controller",
        remote_log_path="/sdcard/Records",
        file_prefix="ISR",
        apk_name_pattern="flytogether-autel-msdk-25-debug*.apk",
        package_name="io.eyesatop.apps.flytogetherautelmsdk25",
    ),
    "TABLET": DeviceTypeConfig(
        name="Tablet",
        remote_log_path="/sdcard/Records",
        file_prefix="TABLET",
        apk_name_pattern="app-dynamic-areal-control-debug*.apk",
        package_name="io.eyesatop.apps.dynamic_areal_control",
    ),
    "BLACK_WIDOW": DeviceTypeConfig(
        name="Black Widow Phone",
        remote_log_path="/sdcard/Records",
        file_prefix="Black-widow",
        apk_name_pattern="app-flytogether-redcat-blackwidow-debug*.apk",
        package_name="io.eyesatop.apps.dynamic_areal_control",
    ),
}

# REFF extraction settings.
PROJECT_STATUS = os.getenv(
    "RACER_TOOLKIT_STATUS",
    "development",
)
MAX_FLIGHT_TIME_DIFF = 120
MAX_VIDEO_TIME_DIFF = 300
MAX_DEVICE_TIME_DIFF_SECONDS = 60
SUPPORTED_DEVICE_TYPES = ("RACER", "TABLET", "ISR")

# Main menu settings.
TOOL_MENU_CHOICES = [
    "REFF & Video Extractor",
    "APK Installer",
    "JAR Management",
    "Folders Reset",
    "Exit",
]
APK_INSTALLER_HEADER = "Select a folder to install APKs from:"
APK_INSTALLER_APPROVAL_CHOICES = ["Yes", "Choose another folder", "Cancel"]
JAR_MANAGEMENT_HEADER = "Select a JAR management option:"
REFF_EXTRACTOR_HEADER = "REFF & Video Extractor"
REFF_EXTRACTOR_CHOICES = [
    "REFF Only",
    "REFF & Videos",
    "Return to Main Menu",
]
JAR_MANAGEMENT_CHOICES = ["Upload JAR", "Restart JAR", "Return to Main Menu"]


__all__ = [
    "APK_INSTALLER_HEADER",
    "APK_INSTALLER_APPROVAL_CHOICES",
    "AndroidDevice",
    "DESKTOP_PATH",
    "JAR_MANAGEMENT_CHOICES",
    "JAR_MANAGEMENT_HEADER",
    "LOCAL_DUMP_DIR",
    "MAX_FLIGHT_TIME_DIFF",
    "MAX_VIDEO_TIME_DIFF",
    "PROJECT_STATUS",
    "SUPPORTED_DEVICE_TYPES",
    "TOOL_MENU_CHOICES",
    "VIDEO_REMOTE_PATH",
    "DEVICE_MODEL_RULES",
    "VIDEO_FILE_PREFIX",
]
