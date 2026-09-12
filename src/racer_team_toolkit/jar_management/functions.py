"""SSH and JAR management functions."""

import socket
from pathlib import Path

import paramiko

from racer_team_toolkit.jar_management.config import SSH_HOST, SSH_PASSWORD, SSH_PORT, SSH_USERNAME
from racer_team_toolkit.ui.functions import select_menu


def is_ssh_server_reachable(
    host: str = SSH_HOST,
    port: int = SSH_PORT,
    timeout: float = 3.0,
) -> bool:
    """Return whether the SSH server can be reached on the configured port."""

    try:
        with socket.create_connection(
            (host, port),
            timeout=timeout,
        ):
            return True

    except OSError:
        return False


def connect_to_server() -> paramiko.SSHClient | None:
    """Connect to the JAR server over SSH."""

    if not SSH_PASSWORD:
        print("[!] SSH_PASSWORD is missing from the .env file.")
        return None

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=SSH_HOST,
            port=SSH_PORT,
            username=SSH_USERNAME,
            password=SSH_PASSWORD,
            timeout=5,
            look_for_keys=False,
            allow_agent=False,
        )

    except paramiko.AuthenticationException:
        print("[!] SSH authentication failed.")
        return None

    except (paramiko.SSHException, socket.timeout, OSError) as error:
        print(f"[!] SSH connection failed: {error}")
        return None

    return ssh


def run_remote_command(
    ssh: paramiko.SSHClient,
    command: str,
) -> tuple[int, str, str]:
    """Run a command on the SSH server and return exit code, stdout, and stderr."""

    _, stdout, stderr = ssh.exec_command(command)

    exit_code = stdout.channel.recv_exit_status()

    output = stdout.read().decode().strip()
    error = stderr.read().decode().strip()

    return exit_code, output, error


def stop_screen_sessions(ssh: paramiko.SSHClient) -> bool:
    """Stop all running screen sessions on the server."""

    exit_code, _, error = run_remote_command(
        ssh,
        "killall screen",
    )

    if exit_code not in (0, 1):
        print(f"[!] Failed to stop screen sessions: {error}")
        return False

    return True


def verify_screen_stopped(ssh: paramiko.SSHClient) -> bool:
    """Verify that no screen sessions are currently running."""

    _, output, error = run_remote_command(
        ssh,
        "screen -ls",
    )

    combined_output = f"{output}\n{error}".lower()

    if "no sockets found" in combined_output:
        return True

    if "there is a screen on" in combined_output:
        print("[!] A screen session is still running.")
        return False

    if "there are screens on" in combined_output:
        print("[!] Screen sessions are still running.")
        return False

    print(f"[!] Could not verify screen status:\n{combined_output.strip()}")
    return False


def run_java_script(
    ssh: paramiko.SSHClient,
) -> tuple[bool, str]:
    """Start the Java processes using the server's run_java script."""

    if not SSH_PASSWORD:
        return False, "SSH_PASSWORD is missing from the .env file."

    stdin, stdout, stderr = ssh.exec_command("sudo -S utils/run_java.sh")

    stdin.write(f"{SSH_PASSWORD}\n")
    stdin.flush()

    exit_code = stdout.channel.recv_exit_status()

    output = stdout.read().decode().strip()
    error = stderr.read().decode().strip()

    combined_output = f"{output}\n{error}".strip()

    if exit_code != 0:
        print(f"[!] Failed to run Java script:\n{combined_output}")
        return False, combined_output

    return True, combined_output


def verify_groundlord_started(output: str) -> bool:
    """Verify that racer-groundlord.jar was started successfully."""

    required_messages = [
        "Found /home/pod/run.d/racer-groundlord.jar",
        "Running as racer groundlord",
    ]

    return all(message in output for message in required_messages)


def restart_jar() -> bool:
    """Restart the Racer Groundlord JAR on the remote server."""

    if not is_ssh_server_reachable():
        print(f"[!] SSH server is not reachable at {SSH_HOST}:{SSH_PORT}.")
        return False

    ssh = connect_to_server()

    if ssh is None:
        return False

    try:
        if not stop_screen_sessions(ssh):
            return False

        if not verify_screen_stopped(ssh):
            return False

        success, output = run_java_script(ssh)

        if not success:
            return False

        if not verify_groundlord_started(output):
            print("[!] Racer Groundlord did not start successfully.")
            return False
        return True

    finally:
        ssh.close()


def select_jar_file() -> Path | None:
    """Let the user select a Groundlord JAR from Downloads."""

    downloads_directory = Path.home() / "Downloads"

    jar_files = sorted(
        path
        for path in downloads_directory.iterdir()
        if path.is_file() and path.name == "racer-groundlord.jar"
    )

    folders = sorted(
        path
        for path in downloads_directory.iterdir()
        if path.is_dir() and folder_contains_groundlord_jar(path)
    )

    choices = [
        *(f"📁 {folder.name}" for folder in folders),
        *(f"📦 {jar_file.name}" for jar_file in jar_files),
        "Cancel",
    ]

    choice = select_menu(
        "Select JAR:",
        choices,
    )

    if choice is None or choice == "Cancel":
        return None

    if choice.startswith("📦 "):
        return downloads_directory / choice.removeprefix("📦 ")

    if choice.startswith("📁 "):
        selected_folder = downloads_directory / choice.removeprefix("📁 ")

        return next(
            selected_folder.rglob("racer-groundlord.jar"),
            None,
        )

    return None


def folder_contains_groundlord_jar(folder: Path) -> bool:
    """Return whether a folder contains racer-groundlord.jar in its tree."""

    return any(
        path.is_file() and path.name == "racer-groundlord.jar"
        for path in folder.rglob("racer-groundlord.jar")
    )
