"""Configuration for IMU recordings extraction."""

from dotenv import load_dotenv

load_dotenv()

IMU_REMOTE_DIRECTORY = "/home/pod/imuRecord"
IMU_FILE_PREFIX = "imu_"
IMU_FILE_SUFFIX = ".csv"
