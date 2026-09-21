"""Shared SSH configuration."""

import os

from dotenv import load_dotenv

load_dotenv()

SSH_HOST = "192.168.30.1"
SSH_PORT = 22
SSH_USERNAME = "pod"
SSH_PASSWORD = os.getenv("SSH_PASSWORD")
