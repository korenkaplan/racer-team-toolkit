"""Slack configuration for online release discovery."""

import os

from dotenv import load_dotenv

from racer_team_toolkit.config import get_env_path

load_dotenv(get_env_path())

SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")

SLACK_RELEASE_CHANNEL = os.getenv(
    "SLACK_RELEASE_CHANNEL",
    "google-drive-releases",
)

SLACK_REDIRECT_URI = "http://localhost:8765/slack/callback"

SLACK_USER_SCOPES = (
    "channels:read",
    "channels:history",
    "groups:read",
    "groups:history",
)
