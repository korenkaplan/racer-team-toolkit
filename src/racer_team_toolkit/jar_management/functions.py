"""SSH and JAR management functions."""

from pathlib import Path

import paramiko
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TransferSpeedColumn,
)
from rich.status import Status

from racer_team_toolkit.jar_management.config import (
    CAMERA_MODE_COMMANDS,
    CAMERA_MODE_MARKERS,
    CAMERA_MODE_RTSP,
    CAMERA_MODE_SHARPEYE,
    JAR_FILENAME,
    REMOTE_JAR_DIRECTORY,
    RUN_JAVA_SCRIPT_PATH,
)
from racer_team_toolkit.ssh.config import (
    SSH_HOST,
    SSH_PASSWORD,
    SSH_PORT,
)
from racer_team_toolkit.ssh.functions import (
    connect_to_server,
    is_ssh_server_reachable,
    run_remote_command,
)
from racer_team_toolkit.ui.functions import select_menu

console = Console()


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


def verify_groundlord_started(
    ssh: paramiko.SSHClient,
) -> bool:
    """Verify that racer-groundlord.jar is actually running."""

    exit_code, output, error = run_remote_command(
        ssh,
        "pgrep -af racer-groundlord.jar",
    )

    if exit_code != 0:
        if error:
            print(f"[!] Failed to check Racer Groundlord process: {error}")
        return False

    return "racer-groundlord.jar" in output


def build_camera_mode_script(
    script_text: str,
    camera_mode: str,
) -> str:
    """Return run_java.sh with the selected supported camera mode enabled."""

    if camera_mode not in CAMERA_MODE_COMMANDS:
        raise ValueError(f"Unsupported camera mode: {camera_mode}")

    camera_lines = {
        mode: f'RUN_CMD="$RUN_CMD {arguments}"' for mode, arguments in CAMERA_MODE_COMMANDS.items()
    }
    found_modes: set[str] = set()
    updated_lines: list[str] = []
    insertion_index: int | None = None
    insertion_indent = "    "

    for line in script_text.splitlines(keepends=True):
        newline = "\n" if line.endswith("\n") else ""
        content = line[:-1] if newline else line
        indentation = content[: len(content) - len(content.lstrip())]
        stripped = content.lstrip()
        candidate = stripped[1:].lstrip() if stripped.startswith("#") else stripped

        matched_mode = next(
            (
                mode
                for mode, marker in CAMERA_MODE_MARKERS.items()
                if candidate.startswith('RUN_CMD="$RUN_CMD ') and marker in candidate
            ),
            None,
        )

        if matched_mode is None:
            updated_lines.append(line)
            continue

        if insertion_index is None:
            insertion_index = len(updated_lines)
            insertion_indent = indentation

        found_modes.add(matched_mode)
        selected_line = camera_lines[matched_mode]

        if matched_mode != camera_mode:
            selected_line = f"#{selected_line}"

        updated_lines.append(f"{indentation}{selected_line}{newline}")

    missing_modes = [mode for mode in camera_lines if mode not in found_modes]

    if missing_modes:
        if insertion_index is None:
            raise ValueError("No supported camera source lines were found in run_java.sh.")

        insert_at = insertion_index

        for mode in missing_modes:
            selected_line = camera_lines[mode]

            if mode != camera_mode:
                selected_line = f"#{selected_line}"

            updated_lines.insert(
                insert_at,
                f"{insertion_indent}{selected_line}\n",
            )
            insert_at += 1

    return "".join(updated_lines)


def get_camera_mode_from_script(script_text: str) -> str | None:
    """Return the currently active supported camera mode."""

    for line in script_text.splitlines():
        stripped = line.strip()

        if stripped.startswith("#"):
            continue

        if not stripped.startswith('RUN_CMD="$RUN_CMD '):
            continue

        for mode, marker in CAMERA_MODE_MARKERS.items():
            if marker in stripped:
                return mode

    return None


def read_run_java_script(
    ssh: paramiko.SSHClient,
) -> str:
    """Read the remote run_java.sh script."""

    with ssh.open_sftp() as sftp:
        with sftp.open(RUN_JAVA_SCRIPT_PATH, "r") as remote_file:
            content = remote_file.read()

    if isinstance(content, bytes):
        return content.decode("utf-8")

    return content


def set_camera_mode(
    ssh: paramiko.SSHClient,
    camera_mode: str,
) -> tuple[bool, str]:
    """Enable one supported camera mode in run_java.sh."""

    try:
        current_script = read_run_java_script(ssh)
        updated_script = build_camera_mode_script(
            current_script,
            camera_mode,
        )

        if updated_script == current_script:
            return True, f"{camera_mode} is already active."

        with ssh.open_sftp() as sftp:
            with sftp.open(RUN_JAVA_SCRIPT_PATH, "w") as remote_file:
                remote_file.write(updated_script)

        return True, f"Camera source updated to {camera_mode}."

    except (OSError, paramiko.SSHException, UnicodeDecodeError, ValueError) as error:
        return False, str(error)


def get_current_camera_mode() -> str | None:
    """Return the currently configured camera mode from run_java.sh."""

    if not is_ssh_server_reachable():
        return None

    ssh = connect_to_server()

    if ssh is None:
        return None

    try:
        script_text = read_run_java_script(ssh)
        return get_camera_mode_from_script(script_text)

    except (OSError, paramiko.SSHException, UnicodeDecodeError):
        return None

    finally:
        ssh.close()


def change_camera_mode(
    camera_mode: str,
) -> bool:
    """Update the camera mode and restart Racer Groundlord."""

    if camera_mode not in (CAMERA_MODE_SHARPEYE, CAMERA_MODE_RTSP):
        console.print(f"[red]✗[/red] Unsupported camera mode: {camera_mode}")
        return False

    with Status(
        "Checking server connection...",
        console=console,
        spinner="dots",
    ) as status:
        if not is_ssh_server_reachable():
            console.print(f"[red]✗[/red] Server is not reachable at {SSH_HOST}:{SSH_PORT}.")
            return False

        console.print("[green]✓[/green] Server reachable")
        status.update("Connecting to server...")

        ssh = connect_to_server()

        if ssh is None:
            return False

        console.print("[green]✓[/green] Connected to server")

        try:
            status.update(f"Setting camera source to {camera_mode}...")

            success, message = set_camera_mode(
                ssh,
                camera_mode,
            )

            if not success:
                console.print(f"[red]✗[/red] Failed to update camera source: {message}")
                return False

            console.print(f"[green]✓[/green] {message}")

            status.update("Stopping running JAR processes...")

            if not stop_screen_sessions(ssh):
                return False

            if not verify_screen_stopped(ssh):
                return False

            console.print("[green]✓[/green] Existing processes stopped")
            status.update("Starting Java processes...")

            success, _ = run_java_script(ssh)

            if not success:
                return False

            console.print("[green]✓[/green] Java startup command completed")
            status.update("Verifying Racer Groundlord...")

            if not verify_groundlord_started(ssh):
                console.print("[red]✗[/red] Racer Groundlord did not start successfully.")
                return False

            console.print("[green]✓[/green] Racer Groundlord is running")
            return True

        finally:
            ssh.close()


def restart_jar() -> bool:
    """Restart the Racer Groundlord JAR on the remote server."""

    with Status(
        "Checking server connection...",
        console=console,
        spinner="dots",
    ) as status:
        if not is_ssh_server_reachable():
            console.print(f"[red]✗[/red] SSH server is not reachable at {SSH_HOST}:{SSH_PORT}.")
            return False

        console.print("[green]✓[/green] Server reachable")

        status.update("Connecting to server...")

        ssh = connect_to_server()

        if ssh is None:
            return False

        console.print("[green]✓[/green] Connected to server")

        try:
            status.update("Stopping running JAR processes...")

            if not stop_screen_sessions(ssh):
                return False

            if not verify_screen_stopped(ssh):
                return False

            console.print("[green]✓[/green] Existing processes stopped")

            status.update("Starting Java processes...")

            success, _ = run_java_script(ssh)

            if not success:
                return False

            console.print("[green]✓[/green] Java startup command completed")

            status.update("Verifying Racer Groundlord...")

            if not verify_groundlord_started(ssh):
                console.print("[red]✗[/red] Racer Groundlord did not start successfully.")
                return False

            console.print("[green]✓[/green] Racer Groundlord is running")

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


def upload_jar_file(
    ssh: paramiko.SSHClient,
    local_jar_path: Path,
) -> bool:
    """Upload the selected Groundlord JAR with transfer progress."""

    remote_jar_path = f"{REMOTE_JAR_DIRECTORY}/{JAR_FILENAME}"

    try:
        with ssh.open_sftp() as sftp:
            with Progress(
                "[progress.description]{task.description}",
                BarColumn(),
                TaskProgressColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                console=console,
            ) as progress:
                task_id = progress.add_task(
                    "Uploading JAR",
                    total=local_jar_path.stat().st_size,
                )

                def update_progress(
                    transferred: int,
                    total: int,
                ) -> None:
                    progress.update(
                        task_id,
                        completed=transferred,
                        total=total,
                    )

                sftp.put(
                    str(local_jar_path),
                    remote_jar_path,
                    callback=update_progress,
                )

    except (OSError, paramiko.SSHException) as error:
        console.print(f"[red]✗[/red] Failed to upload JAR: {error}")
        return False

    return True


def upload_jar() -> bool:
    """Upload a new Groundlord JAR and restart the Java processes."""

    with Status(
        "Checking server connection...",
        console=console,
        spinner="dots",
    ) as status:
        if not is_ssh_server_reachable():
            console.print(f"[red]✗[/red] Server is not reachable at {SSH_HOST}:{SSH_PORT}.")
            return False

        console.print("[green]✓[/green] Server reachable")

        status.update("Connecting to server...")

        ssh = connect_to_server()

        if ssh is None:
            return False

        console.print("[green]✓[/green] Connected to server")

        try:
            status.update("Stopping running JAR processes...")

            if not stop_screen_sessions(ssh):
                return False

            if not verify_screen_stopped(ssh):
                return False

            console.print("[green]✓[/green] Existing processes stopped")

            # Only now ask the user which JAR to upload.
            local_jar_path = select_jar_file()

            if local_jar_path is None:
                console.print("[yellow]Upload cancelled.[/yellow]")
                return False

            console.print(f"\nSelected: [bold]{local_jar_path.name}[/bold]\n")

            if not upload_jar_file(
                ssh,
                local_jar_path,
            ):
                return False

            console.print("[green]✓[/green] JAR upload completed")

            status.update("Starting Java processes...")

            success, _ = run_java_script(ssh)

            if not success:
                return False

            console.print("[green]✓[/green] Java startup command completed")

            status.update("Verifying Racer Groundlord...")

            if not verify_groundlord_started(ssh):
                console.print("[red]✗[/red] Racer Groundlord did not start successfully.")
                return False

            console.print("[green]✓[/green] Racer Groundlord is running")

            return True

        finally:
            ssh.close()


def upload_selected_jar(
    local_jar_path: Path,
) -> bool:
    """Upload a preselected Groundlord JAR and restart the Java processes."""

    if not local_jar_path.is_file():
        console.print(f"[red]✗[/red] JAR file does not exist: {local_jar_path}")
        return False

    with Status(
        "Checking server connection...",
        console=console,
        spinner="dots",
    ) as status:
        if not is_ssh_server_reachable():
            console.print(f"[red]✗[/red] Server is not reachable at {SSH_HOST}:{SSH_PORT}.")
            return False

        console.print("[green]✓[/green] Server reachable")

        status.update("Connecting to server...")

        ssh = connect_to_server()

        if ssh is None:
            return False

        console.print("[green]✓[/green] Connected to server")

        try:
            status.update("Stopping running JAR processes...")

            if not stop_screen_sessions(ssh):
                return False

            if not verify_screen_stopped(ssh):
                return False

            console.print("[green]✓[/green] Existing processes stopped")

            console.print(f"\nSelected: [bold]{local_jar_path.name}[/bold]\n")

            if not upload_jar_file(
                ssh,
                local_jar_path,
            ):
                return False

            console.print("[green]✓[/green] JAR upload completed")

            status.update("Starting Java processes...")

            success, _ = run_java_script(ssh)

            if not success:
                return False

            console.print("[green]✓[/green] Java startup command completed")

            status.update("Verifying Racer Groundlord...")

            if not verify_groundlord_started(ssh):
                console.print("[red]✗[/red] Racer Groundlord did not start successfully.")
                return False

            console.print("[green]✓[/green] Racer Groundlord is running")

            return True

        finally:
            ssh.close()
