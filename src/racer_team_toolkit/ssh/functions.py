"""Reusable SSH operations."""

import socket

import paramiko

from racer_team_toolkit.ssh.config import (
    SSH_HOST,
    SSH_PASSWORD,
    SSH_PORT,
    SSH_USERNAME,
)


def is_ssh_server_reachable(
    host: str = SSH_HOST,
    port: int = SSH_PORT,
    timeout: float = 3.0,
) -> bool:
    """Return whether an SSH server can be reached."""

    try:
        with socket.create_connection(
            (host, port),
            timeout=timeout,
        ):
            return True

    except OSError:
        return False


def connect_to_server(
    host: str = SSH_HOST,
    port: int = SSH_PORT,
    username: str = SSH_USERNAME,
    password: str | None = SSH_PASSWORD,
) -> paramiko.SSHClient | None:
    """Connect to an SSH server."""

    if not password:
        print("[!] SSH_PASSWORD is missing from the .env file.")
        return None

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=5,
            look_for_keys=False,
            allow_agent=False,
        )

    except paramiko.AuthenticationException:
        print("[!] SSH authentication failed.")
        return None

    except (
        paramiko.SSHException,
        socket.timeout,
        OSError,
    ) as error:
        print(f"[!] SSH connection failed: {error}")
        return None

    return ssh


def run_remote_command(
    ssh: paramiko.SSHClient,
    command: str,
) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, and stderr."""

    _, stdout, stderr = ssh.exec_command(command)

    exit_code = stdout.channel.recv_exit_status()

    output = stdout.read().decode().strip()

    error = stderr.read().decode().strip()

    return (
        exit_code,
        output,
        error,
    )
