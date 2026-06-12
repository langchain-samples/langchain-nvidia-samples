"""OpenShell backend adapter for Deep Agents."""

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

from .observability import end_trace, optional_trace, redact_text

SANDBOX_NAME_ENV = "OPENSHELL_SANDBOX_NAME"
DEFAULT_TIMEOUT_ENV = "OPENSHELL_DEFAULT_TIMEOUT_SECONDS"
OUTPUT_PREVIEW_CHARS_ENV = "LANGSMITH_OUTPUT_PREVIEW_CHARS"


class OpenShellBackend(BaseSandbox):
    """Deep Agents sandbox backend backed by an OpenShell sandbox session."""

    def __init__(self, session: SandboxSession, *, default_timeout: int) -> None:
        self._session = session
        self._default_timeout = default_timeout

    @property
    def id(self) -> str:
        return self._session.id

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        """Run a shell command in OpenShell and expose a redacted trace span."""

        effective_timeout = timeout or self._default_timeout
        with optional_trace(
            name="openshell.execute",
            run_type="tool",
            inputs={"command": command, "timeout_seconds": effective_timeout},
            tags=["openshell", "sandbox", "execute"],
            metadata={"sandbox_id": self.id},
        ) as run:
            result = self._session.exec(
                ["bash", "-lc", "bash -s"],
                stdin=command.encode("utf-8"),
                timeout_seconds=effective_timeout,
            )
            output = result.stdout
            if result.stderr:
                output = f"{output}\n{result.stderr}" if output else result.stderr
            end_trace(
                run,
                outputs={
                    "exit_code": result.exit_code,
                    "output_preview": redact_text(output, max_chars=_output_preview_chars()),
                },
            )
            return ExecuteResponse(
                output=output,
                exit_code=result.exit_code,
                truncated=False,
            )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload files into OpenShell using stdin so file contents stay out of logs."""

        responses: list[FileUploadResponse] = []
        with optional_trace(
            name="openshell.upload_files",
            run_type="tool",
            inputs={"paths": [path for path, _ in files]},
            tags=["openshell", "sandbox", "filesystem"],
            metadata={"sandbox_id": self.id},
        ) as run:
            for path, content in files:
                try:
                    parent = shlex.quote(os.path.dirname(path) or ".")
                    destination = shlex.quote(path)
                    result = self._session.exec(
                        ["bash", "-lc", f"mkdir -p {parent} && cat > {destination}"],
                        stdin=content,
                        timeout_seconds=self._default_timeout,
                    )
                    error = None if result.exit_code == 0 else "upload_failed"
                except Exception:  # noqa: BLE001 - backend protocol wants per-file errors
                    error = "upload_failed"
                responses.append(FileUploadResponse(path=path, error=error))
            end_trace(
                run,
                outputs={
                    "uploaded": [r.path for r in responses if r.error is None],
                    "failed": [r.path for r in responses if r.error is not None],
                },
            )
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download files from OpenShell via base64 encoding."""

        responses: list[FileDownloadResponse] = []
        with optional_trace(
            name="openshell.download_files",
            run_type="tool",
            inputs={"paths": paths},
            tags=["openshell", "sandbox", "filesystem"],
            metadata={"sandbox_id": self.id},
        ) as run:
            for path in paths:
                try:
                    result = self._session.exec(
                        ["base64", path],
                        timeout_seconds=self._default_timeout,
                    )
                    if result.exit_code != 0:
                        responses.append(
                            FileDownloadResponse(
                                path=path,
                                content=None,
                                error="file_not_found",
                            )
                        )
                        continue
                    responses.append(
                        FileDownloadResponse(
                            path=path,
                            content=base64.b64decode(result.stdout),
                            error=None,
                        )
                    )
                except Exception:  # noqa: BLE001 - backend protocol wants per-file errors
                    responses.append(
                        FileDownloadResponse(
                            path=path,
                            content=None,
                            error="file_not_found",
                        )
                    )
            end_trace(
                run,
                outputs={
                    "downloaded": [r.path for r in responses if r.error is None],
                    "failed": [r.path for r in responses if r.error is not None],
                },
            )
        return responses


def _default_timeout() -> int:
    raw = os.getenv(DEFAULT_TIMEOUT_ENV, "1800")
    try:
        return int(raw)
    except ValueError:
        return 1800


def _output_preview_chars() -> int:
    raw = os.getenv(OUTPUT_PREVIEW_CHARS_ENV, "1000")
    try:
        return max(0, int(raw))
    except ValueError:
        return 1000


def _resolve_sandbox(client: SandboxClient) -> Any:
    sandbox_name = os.getenv(SANDBOX_NAME_ENV)
    with optional_trace(
        name="openshell.resolve_sandbox",
        run_type="tool",
        inputs={"sandbox_name": sandbox_name or "<fresh>"},
        tags=["openshell", "sandbox", "lifecycle"],
    ) as run:
        if sandbox_name:
            client.get(sandbox_name)
            ref = client.wait_ready(sandbox_name)
        else:
            ref = client.create()
            ref = client.wait_ready(ref.name)
        end_trace(run, outputs={"sandbox": getattr(ref, "name", sandbox_name or "<fresh>")})
        return ref


def create_backend(runtime: Any) -> CompositeBackend:
    """Create a hybrid backend.

    Normal tool execution is routed to OpenShell. Skills and notebook materials
    stay on the local filesystem so participants can edit and commit them as
    source files.
    """

    client = SandboxClient.from_active_cluster()
    ref = _resolve_sandbox(client)
    session = SandboxSession(client, ref)
    sandbox = OpenShellBackend(session, default_timeout=_default_timeout())

    return CompositeBackend(
        default=sandbox,
        routes={
            "/skills/": FilesystemBackend(root_dir="./skills", virtual_mode=True),
            "/workshop/": FilesystemBackend(root_dir="./workshop", virtual_mode=True),
        },
    )
