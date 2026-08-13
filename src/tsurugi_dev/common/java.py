from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True)
class JavaRuntime:
    """Resolved Java runtime suitable for build-time tools."""

    home: Path
    executable: Path
    major: int
    source: str


def _parse_java_major(text: str) -> int | None:
    # Handles both modern `openjdk 17.0.x` and old `java version "1.8..."` forms.
    match = re.search(r'(?:openjdk|java)\s+version\s+"?([0-9]+)(?:\.([0-9]+))?', text)
    if not match:
        match = re.search(r"openjdk\s+([0-9]+)(?:\.([0-9]+))?", text)
    if not match:
        return None
    first = int(match.group(1))
    second = int(match.group(2) or 0)
    return second if first == 1 and second else first


def java_major(java: Path | str, *, env: Mapping[str, str] | None = None) -> int | None:
    """Return the Java major version reported by *java*, or None on failure."""
    try:
        result = subprocess.run(
            [os.fspath(java), "-version"],
            env=dict(env) if env is not None else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError:
        return None
    return _parse_java_major(result.stdout)


def java_home_from_executable(java: Path) -> Path:
    """Infer JAVA_HOME from a .../bin/java executable path."""
    return java.resolve().parent.parent


def _runtime_from_home(home: Path, *, source: str) -> JavaRuntime | None:
    java = home / "bin" / "java"
    if not java.is_file():
        return None
    major = java_major(java)
    if major is None:
        return None
    return JavaRuntime(
        home=home.resolve(), executable=java.resolve(), major=major, source=source
    )


def _iter_jvm_homes(jvm_root: Path = Path("/usr/lib/jvm")) -> Iterable[Path]:
    if not jvm_root.is_dir():
        return ()
    return sorted((p for p in jvm_root.iterdir() if p.is_dir()), key=lambda p: p.name)


def current_java_runtime(env: Mapping[str, str] | None = None) -> JavaRuntime | None:
    """Resolve the Java runtime currently selected by PATH."""
    environment = dict(os.environ if env is None else env)
    path = environment.get("PATH")
    executable: str | None = None
    if path:
        for entry in path.split(os.pathsep):
            candidate = Path(entry) / "java"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                executable = str(candidate)
                break
    if executable is None:
        return None
    java = Path(executable).resolve()
    major = java_major(java, env=environment)
    if major is None:
        return None
    return JavaRuntime(
        home=java_home_from_executable(java),
        executable=java,
        major=major,
        source="PATH",
    )


def select_java_runtime(
    *,
    min_major: int = 17,
    preferred_major: int = 17,
    explicit_home: Path | None = None,
    env: Mapping[str, str] | None = None,
    jvm_root: Path = Path("/usr/lib/jvm"),
) -> JavaRuntime | None:
    """Select a Java runtime at least *min_major*.

    Resolution order is intentionally deterministic:
      1. explicit_home
      2. $TSURUGI_DEV_JAVA_HOME
      3. current PATH java, when already suitable
      4. $JAVA_HOME, when suitable
      5. installed JDKs under /usr/lib/jvm, preferring preferred_major

    This does not mutate os.environ.
    """
    environment = dict(os.environ if env is None else env)

    if explicit_home is not None:
        runtime = _runtime_from_home(explicit_home.expanduser(), source="--java-home")
        if runtime is None:
            raise RuntimeError(f"invalid Java home: {explicit_home}")
        if runtime.major < min_major:
            raise RuntimeError(
                f"Java {min_major}+ required, but {explicit_home} provides Java {runtime.major}"
            )
        return runtime

    configured = environment.get("TSURUGI_DEV_JAVA_HOME")
    if configured:
        runtime = _runtime_from_home(
            Path(configured).expanduser(), source="TSURUGI_DEV_JAVA_HOME"
        )
        if runtime is not None and runtime.major >= min_major:
            return runtime

    current = current_java_runtime(environment)
    if current is not None and current.major >= min_major:
        return current

    java_home = environment.get("JAVA_HOME")
    if java_home:
        runtime = _runtime_from_home(Path(java_home).expanduser(), source="JAVA_HOME")
        if runtime is not None and runtime.major >= min_major:
            return runtime

    candidates: list[JavaRuntime] = []
    for home in _iter_jvm_homes(jvm_root):
        runtime = _runtime_from_home(home, source=str(jvm_root))
        if runtime is not None and runtime.major >= min_major:
            candidates.append(runtime)

    if not candidates:
        return None

    candidates.sort(
        key=lambda runtime: (
            0 if runtime.major == preferred_major else 1,
            runtime.major,
            str(runtime.home),
        )
    )
    return candidates[0]


def apply_java_runtime(env: Mapping[str, str], runtime: JavaRuntime) -> dict[str, str]:
    """Return a copy of *env* with JAVA_HOME/PATH selecting *runtime*."""
    result = dict(env)
    result["JAVA_HOME"] = str(runtime.home)
    current_path = result.get("PATH", "")
    java_bin = str(runtime.home / "bin")
    entries = [entry for entry in current_path.split(os.pathsep) if entry]
    entries = [entry for entry in entries if entry != java_bin]
    result["PATH"] = os.pathsep.join([java_bin, *entries])
    return result
