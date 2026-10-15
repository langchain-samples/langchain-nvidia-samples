"""OpenShell sandbox backend for deepagents.

Implements SandboxBackendProtocol backed by an OpenShell sandbox.
The OpenShell gateway is selected from the active cluster config
(~/.config/openshell/active_gateway) or OPENSHELL_GATEWAY env var.

Sandbox selection (controlled via env vars):
  OPENSHELL_SANDBOX_NAME  Connect to a pre-existing named sandbox.
                          Create one with: openshell sandbox create --name <name> --keep
  (not set)               Create a fresh sandbox for this run.

Usage:
  Authenticate first: openshell gateway start (or gateway select <existing>)
  Then run the agent: deepagents run src/agent.py:agent
"""

from __future__ import annotations

import base64
import os
import shlex
from typing import Any

from deepagents.backends import CompositeBackend, FilesystemBackend
from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox
from openshell import SandboxClient, SandboxSession

SANDBOX_NAME_ENV = "OPENSHELL_SANDBOX_NAME"


class OpenShellBackend(BaseSandbox):
    """deepagents SandboxBackendProtocol backed by an OpenShell sandbox.

    Wraps a live SandboxSession. All file operations (read, write, edit,
    grep, glob, ls) are inherited from BaseSandbox and executed as shell
    commands via execute(). Only execute(), upload_files(), and
    download_files() need concrete implementations.
    """

    def __init__(
        self,
        session: SandboxSession,
        *,
        default_timeout: int = 30 * 60,
    ) -> None:
        self._session = session
        self._default_timeout = default_timeout

    @property
    def id(self) -> str:
        return self._session.id

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        """Run a shell command in the OpenShell sandbox."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        result = self._session.exec(
            ["bash", "-c", command],
            timeout_seconds=effective_timeout,
        )
        output = result.stdout
        if result.stderr:
            output = f"{output}\n{result.stderr}" if output else result.stderr
        return ExecuteResponse(
            output=output,
            exit_code=result.exit_code,
            truncated=False,
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload files to the sandbox by piping raw bytes over SSH stdin."""
        responses = []
        for path, content in files:
            try:
                parent = shlex.quote(os.path.dirname(path) or ".")
                dest = shlex.quote(path)
                result = self._session.exec(
                    ["bash", "-c", f"mkdir -p {parent} && cat > {dest}"],
                    stdin=content,
                )
                if result.exit_code != 0:
                    responses.append(FileUploadResponse(path=path, error="permission_denied"))
                else:
                    responses.append(FileUploadResponse(path=path, error=None))
            except Exception:  # noqa: BLE001
                responses.append(FileUploadResponse(path=path, error="permission_denied"))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download files from the sandbox via base64 encoding."""
        responses = []
        for path in paths:
            try:
                result = self._session.exec(["base64", path])
                if result.exit_code != 0:
                    responses.append(
                        FileDownloadResponse(path=path, content=None, error="file_not_found")
                    )
                else:
                    content = base64.b64decode(result.stdout.strip())
                    responses.append(FileDownloadResponse(path=path, content=content, error=None))
            except Exception:  # noqa: BLE001
                responses.append(
                    FileDownloadResponse(path=path, content=None, error="file_not_found")
                )
        return responses


def create_backend(runtime: Any) -> CompositeBackend:
    """Backend factory: OpenShell sandbox + filesystem for memory/skills.

    Sandbox selection:
    - If OPENSHELL_SANDBOX_NAME is set: connect to that existing named sandbox.
      Pre-create one with: openshell sandbox create --name <name> --keep
    - Otherwise: create a fresh sandbox for this run and wait for it to be ready.

    The active OpenShell gateway is resolved from:
    1. OPENSHELL_GATEWAY env var
    2. ~/.config/openshell/active_gateway (set by: openshell gateway select <name>)

    Memory and skills live on the local filesystem (FilesystemBackend) so
    changes persist across restarts and can be committed back to git.
    """
    client = SandboxClient.from_active_cluster()

    sandbox_name = os.environ.get(SANDBOX_NAME_ENV)
    if sandbox_name:
        # Connect to a pre-existing sandbox (user manages lifecycle)
        ref = client.get(sandbox_name)
    else:
        # Create a fresh sandbox for this run; delete manually when done
        ref = client.create()
        ref = client.wait_ready(ref.name)

    session = SandboxSession(client, ref)

    return CompositeBackend(
        default=OpenShellBackend(session),
        routes={
            "/memory/": FilesystemBackend(root_dir="./src", virtual_mode=True),
            "/skills/": FilesystemBackend(root_dir="./skills", virtual_mode=True),
        },
    )
