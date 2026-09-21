"""Configuration for JAR Management."""

from dotenv import load_dotenv

load_dotenv()

REMOTE_JAR_DIRECTORY = "/home/pod/run.d"
JAR_FILENAME = "racer-groundlord.jar"
RUN_JAVA_COMMAND = "sudo utils/run_java.sh"
