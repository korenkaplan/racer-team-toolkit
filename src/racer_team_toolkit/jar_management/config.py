"""Configuration for JAR Management."""

import os

from dotenv import load_dotenv

load_dotenv()

SSH_HOST = "192.168.30.1"
SSH_PORT = 22
SSH_USERNAME = "pod"
SSH_PASSWORD = os.getenv("SSH_PASSWORD")
JAR_FILENAME = "racer-groundlord.jar"
REMOTE_JAR_DIRECTORY = "/home/pod/run.d"

RUN_JAVA_COMMAND = "sudo utils/run_java.sh"
