from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from .common.git import clone_repository_if_missing, update_repository
from .config import (
    TSURUGIDB_REPOSITORY_URL,
    default_home,
    default_repo,
)
from .upstream import execute_build, resolve_layout


class TsurugiDevError(RuntimeError):
    """Raised when a public tsurugi-dev API operation fails."""


@dataclass(frozen=True)
class BuildRequest:
    """Programmatic build request for use by other setup tools.

    Defaults intentionally match the CLI so callers such as
    data-relay-grpc-grdma-test-setup do not need to duplicate tsurugi-dev policy.
    """

    repo: Path = field(default_factory=default_repo)
    home: Path = field(default_factory=default_home)
    prefix: Path | None = None
    build_type: str = "RelWithDebInfo"
    name: str | None = None
    parallel: str | int = "auto"
    ccache: bool = False
    tracy: bool = False
    altimeter: bool = False
    no_jemalloc: bool = False
    force_mpdecimal: bool = False
    build_all_compat: bool = True
    java_home: Path | None = None
    cmake_options: Sequence[str] = ()
    shirakami_options: Sequence[str] = ()
    component_dirs: Mapping[str, Path] = field(default_factory=dict)
    skip: Sequence[str] = ()
    replace_config: Sequence[str] = ()
    replace_home: bool = False
    verbose: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class BuildResult:
    home: Path
    install_dir: Path


def _namespace(request: BuildRequest) -> argparse.Namespace:
    return argparse.Namespace(
        repo=request.repo.expanduser().absolute(),
        home=request.home.expanduser().absolute(),
        prefix=request.prefix.expanduser().absolute() if request.prefix else None,
        build_type=request.build_type,
        name=request.name,
        parallel=request.parallel,
        ccache=request.ccache,
        tracy=request.tracy,
        altimeter=request.altimeter,
        no_jemalloc=request.no_jemalloc,
        force_mpdecimal=request.force_mpdecimal,
        legacy_build_all_compat=request.build_all_compat,
        java_home=request.java_home,
        cmake_option=list(request.cmake_options),
        shirakami_option=list(request.shirakami_options),
        component_dir=[
            (name, path.expanduser().resolve())
            for name, path in request.component_dirs.items()
        ],
        skip=list(request.skip),
        replace_config=list(request.replace_config),
        replace_home=request.replace_home,
        verbose=request.verbose,
        dry_run=request.dry_run,
    )


def full_build(request: BuildRequest | None = None) -> BuildResult:
    """Clean-build and install Tsurugi using the same defaults as the CLI."""
    actual = request or BuildRequest()
    args = _namespace(actual)
    rc = execute_build(args, clean=True)
    if rc != 0:
        raise TsurugiDevError(f"Tsurugi full build failed with status {rc}")
    layout = resolve_layout(args)
    return BuildResult(home=layout.home, install_dir=layout.install_dir)


def build(request: BuildRequest | None = None) -> BuildResult:
    """Incrementally build and install Tsurugi using the same defaults as the CLI."""
    actual = request or BuildRequest()
    args = _namespace(actual)
    rc = execute_build(args, clean=False)
    if rc != 0:
        raise TsurugiDevError(f"Tsurugi build failed with status {rc}")
    layout = resolve_layout(args)
    return BuildResult(home=layout.home, install_dir=layout.install_dir)


def update_source(
    repo: Path | None = None,
    *,
    pull: bool = True,
    jobs: int | None = None,
    dry_run: bool = False,
) -> Path:
    """Clone tsurugidb when missing, then synchronize pinned submodules."""
    target = (repo or default_repo()).expanduser().absolute()
    cloned = clone_repository_if_missing(
        target,
        TSURUGIDB_REPOSITORY_URL,
        dry_run=dry_run,
    )
    update_repository(
        target,
        pull=(pull and not cloned),
        jobs=jobs,
        dry_run=dry_run,
    )
    return target
