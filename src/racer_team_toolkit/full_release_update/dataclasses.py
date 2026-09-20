"""Dataclasses for the full release update flow."""

from dataclasses import dataclass
from pathlib import Path

from racer_team_toolkit.apk_installer.functions import InstallationPlan
from racer_team_toolkit.config import AndroidDevice


@dataclass
class ReleaseUpdatePlan:
    """Selected APK and JAR inputs for one release update."""

    connected_devices: list[AndroidDevice]
    apk_plan: list[InstallationPlan]
    apk_source_folder: Path | None
    jar_file: Path | None
    jar_source_folder: Path | None
    install_apk: bool = True
    upload_jar: bool = True

    @property
    def source_folders_differ(self) -> bool:
        """Return whether enabled APK and JAR inputs came from different folders."""

        return (
            self.install_apk
            and self.upload_jar
            and self.apk_source_folder is not None
            and self.jar_source_folder is not None
            and self.apk_source_folder != self.jar_source_folder
        )
