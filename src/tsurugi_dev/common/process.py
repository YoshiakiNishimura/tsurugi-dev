from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Iterable, Mapping


def quote(value: str) -> str:
    """Return a shell-escaped representation for display purposes."""
    return shlex.quote(value)


def command_text(
    command: Iterable[str | os.PathLike[str]], *, cwd: Path | None = None
) -> str:
    """Format a command exactly as it will be shown to the user."""
    cmd = [os.fspath(value) for value in command]
    display = " ".join(quote(value) for value in cmd)
    if cwd is not None:
        return f"(cd {quote(str(cwd))} && {display})"
    return display


def run(
    command: Iterable[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> None:
    """Run a command with check=True, or print it only when dry_run is enabled."""
    cmd = [os.fspath(value) for value in command]
    print(f"+ {command_text(cmd, cwd=cwd)}")
    if dry_run:
        return
    subprocess.run(
        cmd,
        cwd=cwd,
        env=dict(env) if env is not None else None,
        check=True,
    )


def capture(
    command: Iterable[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """Run a command and return stripped stdout."""
    result = subprocess.run(
        [os.fspath(value) for value in command],
        cwd=cwd,
        env=dict(env) if env is not None else None,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()
