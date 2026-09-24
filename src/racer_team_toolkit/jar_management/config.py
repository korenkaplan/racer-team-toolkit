"""Configuration for JAR Management."""

from dotenv import load_dotenv

load_dotenv()

REMOTE_JAR_DIRECTORY = "/home/pod/run.d"
JAR_FILENAME = "racer-groundlord.jar"
RUN_JAVA_COMMAND = "sudo utils/run_java.sh"
RUN_JAVA_SCRIPT_PATH = "/home/pod/utils/run_java.sh"

CAMERA_MODE_SHARPEYE = "SharpEye Mode"
CAMERA_MODE_RTSP = "RTSP Mode"

CAMERA_MODE_COMMANDS = {
    CAMERA_MODE_SHARPEYE: (
        "-model Lumenier -sdkType betaflight "
        "-camera racer-airlord-rtsp-tcp "
        "-imuRecord imuRecord "
        "-targeting SHARPEYES "
        "-airlordHost 192.168.144.8 "
        "-airlordPort 5001"
    ),
    CAMERA_MODE_RTSP: (
        "-model Lumenier -sdkType betaflight -camera lumenier-rtsp -imuRecord imuRecord"
    ),
}
