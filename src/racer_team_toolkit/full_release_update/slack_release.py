"""Slack release discovery operations."""

import re

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from racer_team_toolkit.full_release_update.dataclasses import (
    OnlineRelease,
)
from racer_team_toolkit.full_release_update.slack_config import (
    SLACK_RELEASE_CHANNEL,
    SLACK_TOKEN,
)

RELEASE_TAG_PATTERN = re.compile(
    r"Release Tag\s*[:\n]\s*([^\n]+)",
    re.IGNORECASE,
)

DIRECTORY_PATTERN = re.compile(
    r"Directory\s*[:\n]\s*([^\n]+)",
    re.IGNORECASE,
)

FOLDER_LINK_PATTERN = re.compile(
    r"https://drive\.google\.com/[^\s>|]+",
)


def is_supported_release(
    release_tag: str,
) -> bool:
    """Return whether the release tag is relevant to the Racer toolkit."""

    release_tag_lower = release_tag.lower()

    return "cstrike" in release_tag_lower or "s2s" in release_tag_lower


def parse_release_message(
    text: str,
    timestamp: float,
) -> OnlineRelease | None:
    """Parse one Slack release message."""

    release_tag_match = RELEASE_TAG_PATTERN.search(
        text,
    )

    directory_match = DIRECTORY_PATTERN.search(
        text,
    )

    folder_link_match = FOLDER_LINK_PATTERN.search(
        text,
    )

    if release_tag_match is None or directory_match is None or folder_link_match is None:
        return None

    release_tag = release_tag_match.group(1).strip()

    if not is_supported_release(
        release_tag,
    ):
        return None

    return OnlineRelease(
        release_tag=release_tag,
        directory=directory_match.group(1).strip(),
        folder_url=folder_link_match.group(0),
        timestamp=timestamp,
    )


def get_slack_client() -> WebClient | None:
    """Create the Slack Web API client."""

    if not SLACK_TOKEN:
        return None

    return WebClient(
        token=SLACK_TOKEN,
    )


def find_channel_id(
    client: WebClient,
    channel_name: str = SLACK_RELEASE_CHANNEL,
) -> str | None:
    """Return the Slack channel ID for a channel name."""

    cursor: str | None = None

    try:
        while True:
            response = client.conversations_list(
                types="public_channel,private_channel",
                limit=200,
                cursor=cursor,
            )

            channels = response.get(
                "channels",
                [],
            )

            for channel in channels:
                if channel.get("name") == channel_name:
                    return channel.get("id")

            metadata = response.get(
                "response_metadata",
                {},
            )

            cursor = metadata.get(
                "next_cursor",
            )

            if not cursor:
                break

    except SlackApiError:
        return None

    return None


def get_recent_slack_messages(
    client: WebClient,
    channel_id: str,
    limit: int = 50,
) -> list[dict]:
    """Return recent messages from the release channel."""

    try:
        response = client.conversations_history(
            channel=channel_id,
            limit=limit,
        )

    except SlackApiError:
        return []

    return list(
        response.get(
            "messages",
            [],
        )
    )
