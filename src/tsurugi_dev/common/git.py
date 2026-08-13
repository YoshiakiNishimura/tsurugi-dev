from __future__ import annotations

from pathlib import Path

from .process import run


def pull_ff_only(repo: Path, *, dry_run: bool = False) -> None:
    """Fast-forward a Git work tree without creating merge commits."""
    run(["git", "pull", "--ff-only"], cwd=repo, dry_run=dry_run)


def sync_submodules(repo: Path, *, dry_run: bool = False) -> None:
    """Synchronize submodule URLs from .gitmodules."""
    run(["git", "submodule", "sync", "--recursive"], cwd=repo, dry_run=dry_run)


def update_submodules(
    repo: Path,
    *,
    jobs: int | None = None,
    dry_run: bool = False,
) -> None:
    """Checkout the exact recursively pinned submodule revisions."""
    if jobs is not None and jobs < 1:
        raise ValueError("jobs must be >= 1")
    command = ["git", "submodule", "update", "--init", "--recursive"]
    if jobs is not None:
        command += ["--jobs", str(jobs)]
    run(command, cwd=repo, dry_run=dry_run)


def update_repository(
    repo: Path,
    *,
    pull: bool = True,
    submodules: bool = True,
    jobs: int | None = None,
    dry_run: bool = False,
) -> None:
    """Update a repository and optionally synchronize its pinned submodules."""
    repo = repo.expanduser().resolve()
    if pull:
        pull_ff_only(repo, dry_run=dry_run)
    if submodules:
        sync_submodules(repo, dry_run=dry_run)
        update_submodules(repo, jobs=jobs, dry_run=dry_run)
