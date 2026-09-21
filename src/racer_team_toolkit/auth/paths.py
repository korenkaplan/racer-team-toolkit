"""Local paths for per-user authentication data."""

from pathlib import Path


def get_user_config_directory() -> Path:
    """Return the local Racer Team Toolkit config directory."""

    return Path.home() / ".racer-team-toolkit"


def get_slack_token_path() -> Path:
    """Return the local Slack token path."""

    return get_user_config_directory() / "slack_token.json"
