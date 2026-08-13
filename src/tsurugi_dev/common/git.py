from __future__ import annotations

from pathlib import Path

from .process import run


def clone_repository_if_missing(
    repo: Path,
    url: str,
    *,
    dry_run: bool = False,
) -> bool:
    """Clone *url* into *repo* when absent.

    Returns True when a clone was (or, with dry_run, would be) performed.
    An existing path must already be a Git work tree; arbitrary existing
    directories are rejected rather than overwritten.
    """
    repo = repo.expanduser().absolute()
    if repo.exists():
        if not (repo / ".git").exists():
            raise RuntimeError(f"path exists but is not a Git work tree: {repo}")
        print(f"repository exists; clone skipped: {repo}")
        return False

    print(f"repository not found; cloning: {url} -> {repo}")
    if not dry_run:
        repo.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", url, str(repo)], dry_run=dry_run)
    return True


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
    repo = repo.expanduser().absolute()
    if pull:
        pull_ff_only(repo, dry_run=dry_run)
    if submodules:
        sync_submodules(repo, dry_run=dry_run)
        update_submodules(repo, jobs=jobs, dry_run=dry_run)
