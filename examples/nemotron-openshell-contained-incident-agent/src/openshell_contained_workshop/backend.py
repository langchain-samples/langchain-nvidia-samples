"""Deep Agents backend for a process already running inside OpenShell."""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path
from typing import Any

from deepagents.backends import CompositeBackend, FilesystemBackend
from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox

from .observability import end_trace, optional_trace, redact_text

DEFAULT_TIMEOUT_ENV = "OPENSHELL_DEFAULT_TIMEOUT_SECONDS"
OUTPUT_PREVIEW_CHARS_ENV = "LANGSMITH_OUTPUT_PREVIEW_CHARS"


def _default_timeout() -> int:
    try:
        return int(os.getenv(DEFAULT_TIMEOUT_ENV, "1800"))
    except ValueError:
        return 1800


def _output_preview_chars() -> int:
    try:
        return max(0, int(os.getenv(OUTPUT_PREVIEW_CHARS_ENV, "1000")))
    except ValueError:
        return 1000


def _combined_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    def normalize(value: str | bytes | None) -> str:
        if value is None:
            return ""
        return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value

    return "\n".join(part for part in (normalize(stdout), normalize(stderr)) if part)


class ContainedRuntimeBackend(BaseSandbox):
    """Execute directly in the current process's OpenShell security boundary.

    This backend deliberately does not use ``SandboxClient``. The runner, parent
    Deep Agent, subagents, and every subprocess are already inside OpenShell.
    """

    def __init__(self, *, default_timeout: int | None = None, workdir: str = "/sandbox") -> None:
        self._default_timeout = default_timeout or _default_timeout()
        self._workdir = workdir

    @property
    def id(self) -> str:
        return os.getenv("OPENSHELL_SANDBOX_NAME") or socket.gethostname()

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        """Run a shell command inside the current OpenShell sandbox."""

        effective_timeout = self._default_timeout if timeout is None else timeout
        subprocess_timeout = None if effective_timeout == 0 else effective_timeout
        with optional_trace(
            name="openshell.contained.execute",
            run_type="tool",
            inputs={"command": command, "timeout_seconds": effective_timeout},
            tags=["openshell", "contained-runtime", "execute"],
            metadata={"sandbox_id": self.id, "execution_boundary": "openshell-contained"},
        ) as run:
            try:
                completed = subprocess.run(
                    ["bash", "-lc", "bash -s"],
                    input=command,
                    text=True,
                    capture_output=True,
                    cwd=self._workdir,
                    timeout=subprocess_timeout,
                    check=False,
                )
                output = _combined_output(completed.stdout, completed.stderr)
                response = ExecuteResponse(
                    output=output,
                    exit_code=completed.returncode,
                    truncated=False,
                )
            except subprocess.TimeoutExpired as exc:
                output = _combined_output(exc.stdout, exc.stderr)
                suffix = f"Command timed out after {effective_timeout} seconds."
                response = ExecuteResponse(
                    output=f"{output}\n{suffix}" if output else suffix,
                    exit_code=124,
                    truncated=False,
                )
            end_trace(
                run,
                outputs={
                    "exit_code": response.exit_code,
                    "output_preview": redact_text(
                        response.output,
                        max_chars=_output_preview_chars(),
                    ),
                },
            )
            return response

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Write bytes locally; OpenShell's outer filesystem policy remains authoritative."""

        responses: list[FileUploadResponse] = []
        with optional_trace(
            name="openshell.contained.upload_files",
            run_type="tool",
            inputs={"paths": [path for path, _ in files]},
            tags=["openshell", "contained-runtime", "filesystem"],
            metadata={"sandbox_id": self.id},
        ) as run:
            for path, content in files:
                try:
                    destination = Path(path)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(content)
                    error = None
                except FileNotFoundError:
                    error = "file_not_found"
                except PermissionError:
                    error = "permission_denied"
                except IsADirectoryError:
                    error = "is_directory"
                except (OSError, ValueError):
                    error = "invalid_path"
                responses.append(FileUploadResponse(path=path, error=error))
            end_trace(
                run,
                outputs={
                    "uploaded": [item.path for item in responses if item.error is None],
                    "failed": [item.path for item in responses if item.error is not None],
                },
            )
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Read bytes locally from paths visible inside OpenShell."""

        responses: list[FileDownloadResponse] = []
        with optional_trace(
            name="openshell.contained.download_files",
            run_type="tool",
            inputs={"paths": paths},
            tags=["openshell", "contained-runtime", "filesystem"],
            metadata={"sandbox_id": self.id},
        ) as run:
            for path in paths:
                try:
                    content = Path(path).read_bytes()
                    responses.append(FileDownloadResponse(path=path, content=content, error=None))
                except FileNotFoundError:
                    responses.append(
                        FileDownloadResponse(path=path, content=None, error="file_not_found")
                    )
                except PermissionError:
                    responses.append(
                        FileDownloadResponse(path=path, content=None, error="permission_denied")
                    )
                except IsADirectoryError:
                    responses.append(
                        FileDownloadResponse(path=path, content=None, error="is_directory")
                    )
                except (OSError, ValueError):
                    responses.append(
                        FileDownloadResponse(path=path, content=None, error="invalid_path")
                    )
            end_trace(
                run,
                outputs={
                    "downloaded": [item.path for item in responses if item.error is None],
                    "failed": [item.path for item in responses if item.error is not None],
                },
            )
        return responses


def create_backend(runtime: Any) -> CompositeBackend:
    """Route writable work to /sandbox and baked workshop materials to /app."""

    del runtime
    return CompositeBackend(
        default=ContainedRuntimeBackend(),
        routes={
            "/skills/": FilesystemBackend(root_dir="/app/skills", virtual_mode=True),
            "/workshop/": FilesystemBackend(root_dir="/app/workshop", virtual_mode=True),
        },
    )
