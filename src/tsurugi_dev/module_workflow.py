from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .common.process import capture, run
from .common.system import auto_parallel
from .config import BUILD_DIRS, COMPONENT_ENV


def _git_success(command: list[str], *, cwd: Path) -> bool:
    return (
        subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def _git_capture(repo: Path, *args: str) -> str:
    return capture(["git", *args], cwd=repo)


def _git_status_porcelain(repo: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Preserve the leading XY status columns; only remove trailing line breaks.
    return result.stdout.rstrip("\r\n")


def component_name(value: str) -> str:
    if value not in COMPONENT_ENV:
        raise argparse.ArgumentTypeError(
            f"unknown component {value!r}; choose one of: {', '.join(sorted(COMPONENT_ENV))}"
        )
    return value


def component_path(repo: Path, component: str) -> Path:
    component_name(component)
    path = repo / component
    if not path.is_dir():
        raise RuntimeError(
            f"component checkout not found: {path}; run 'tsurugi-dev update' first"
        )
    if not _git_success(["git", "rev-parse", "--git-dir"], cwd=path):
        raise RuntimeError(f"component is not a Git work tree: {path}")
    return path


def _branch(path: Path) -> str:
    return _git_capture(path, "branch", "--show-current")


def _head(path: Path) -> str:
    return _git_capture(path, "rev-parse", "HEAD")


def _is_clean(path: Path) -> bool:
    return not _git_status_porcelain(path)


def _require_clean(path: Path, component: str) -> None:
    status = _git_status_porcelain(path)
    if status:
        raise RuntimeError(
            f"{component} has uncommitted changes; commit/stash them before changing Git state:\n"
            f"{status}"
        )


def _remote_ref_exists(path: Path, remote: str, branch: str) -> bool:
    return _git_success(
        ["git", "show-ref", "--verify", "--quiet", f"refs/remotes/{remote}/{branch}"],
        cwd=path,
    )


def _local_ref_exists(path: Path, branch: str) -> bool:
    return _git_success(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=path,
    )


def _is_ancestor(path: Path, ancestor: str, descendant: str) -> bool:
    return _git_success(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=path
    )


def _pinned_sha(repo: Path, component: str) -> str | None:
    try:
        line = _git_capture(repo, "ls-files", "--stage", "--", component)
    except subprocess.CalledProcessError:
        return None
    if not line:
        return None
    fields = line.split(None, 3)
    if len(fields) < 2 or fields[0] != "160000":
        return None
    return fields[1]


def component_development_state(
    repo: Path,
    component: str,
    *,
    base: str = "master",
    remote: str = "origin",
) -> tuple[bool, str]:
    """Return whether a submodule is safe for superproject submodule operations.

    Safe states are deliberately narrow:
      * normal detached HEAD exactly at the superproject-pinned gitlink, or
      * clean base branch with no commits ahead of remote/base.

    Any other named branch is considered active development.
    """
    path = component_path(repo, component)
    if not _is_clean(path):
        return False, "working tree is dirty"

    branch = _branch(path)
    head = _head(path)
    if not branch:
        pinned = _pinned_sha(repo, component)
        if pinned is not None and head == pinned:
            return True, f"pinned detached HEAD {head[:12]}"
        if _remote_ref_exists(path, remote, base):
            remote_head = _git_capture(path, "rev-parse", f"{remote}/{base}")
            if head == remote_head:
                return True, f"detached HEAD at {remote}/{base} {head[:12]}"
        return False, (
            f"detached HEAD {head[:12]} is neither the superproject-pinned commit "
            f"nor {remote}/{base}"
        )

    if branch != base:
        return False, f"development branch {branch!r} is checked out"

    if _remote_ref_exists(path, remote, base):
        remote_ref = f"{remote}/{base}"
        if not _is_ancestor(path, head, remote_ref):
            return False, f"{base} contains commits not in {remote_ref}"
        if head == _git_capture(path, "rev-parse", remote_ref):
            return True, f"clean {base}, synchronized with {remote_ref}"
        return True, f"clean {base}, behind {remote_ref}"

    return True, f"clean {base} (remote tracking ref not available)"


def assert_component_development_finished(
    repo: Path,
    component: str,
    *,
    base: str = "master",
    remote: str = "origin",
) -> None:
    safe, reason = component_development_state(
        repo, component, base=base, remote=remote
    )
    if safe:
        return
    raise RuntimeError(
        f"{component} is not in a development-finished state: {reason}\n"
        f"After the component PR is merged, run:\n"
        f"  tsurugi-dev dev finish {component}\n"
        f"Then retry the submodule/update operation."
    )


def assert_no_active_development(
    repo: Path,
    *,
    base: str = "master",
    remote: str = "origin",
) -> None:
    failures: list[str] = []
    for component in COMPONENT_ENV:
        path = repo / component
        if not path.is_dir() or not _git_success(
            ["git", "rev-parse", "--git-dir"], cwd=path
        ):
            continue
        safe, reason = component_development_state(
            repo, component, base=base, remote=remote
        )
        if not safe:
            failures.append(f"{component}: {reason}")
    if failures:
        detail = "\n".join(f"  - {item}" for item in failures)
        raise RuntimeError(
            "active/incomplete component development was detected; refusing to run a "
            "submodule checkout that could replace the current component HEAD:\n"
            f"{detail}\n"
            "Finish each component first with 'tsurugi-dev dev finish COMPONENT'."
        )


def _switch_base(path: Path, base: str, remote: str, *, dry_run: bool = False) -> None:
    if _local_ref_exists(path, base):
        run(["git", "switch", base], cwd=path, dry_run=dry_run)
    else:
        run(
            ["git", "switch", "-c", base, "--track", f"{remote}/{base}"],
            cwd=path,
            dry_run=dry_run,
        )
    run(
        ["git", "merge", "--ff-only", f"{remote}/{base}"],
        cwd=path,
        dry_run=dry_run,
    )


def dev_status(args: argparse.Namespace) -> int:
    repo: Path = args.repo
    components = [args.component] if args.component else list(COMPONENT_ENV)
    for component in components:
        path = repo / component
        if not path.is_dir() or not _git_success(
            ["git", "rev-parse", "--git-dir"], cwd=path
        ):
            if args.component:
                raise RuntimeError(f"component checkout not found: {path}")
            continue
        branch = _branch(path) or "(detached)"
        head = _head(path)
        pinned = _pinned_sha(repo, component)
        safe, reason = component_development_state(
            repo, component, base=args.base, remote=args.remote
        )
        print(f"{component}:")
        print(f"  branch: {branch}")
        print(f"  HEAD:   {head[:12]}")
        print(f"  pinned: {pinned[:12] if pinned else '(unknown)'}")
        print(f"  state:  {'finished' if safe else 'development'} ({reason})")
    return 0


def dev_start(args: argparse.Namespace) -> int:
    repo: Path = args.repo
    component = args.component
    path = component_path(repo, component)
    _require_clean(path, component)
    safe, reason = component_development_state(
        repo, component, base=args.base, remote=args.remote
    )
    if not safe:
        raise RuntimeError(
            f"cannot start new development for {component}: {reason}\n"
            f"Finish the current work first with 'tsurugi-dev dev finish {component}'."
        )
    if not _git_success(["git", "check-ref-format", "--branch", args.branch], cwd=path):
        raise RuntimeError(f"invalid Git branch name: {args.branch!r}")
    if _local_ref_exists(path, args.branch):
        raise RuntimeError(f"local branch already exists in {component}: {args.branch}")

    run(["git", "fetch", args.remote, "--prune"], cwd=path, dry_run=args.dry_run)
    _switch_base(path, args.base, args.remote, dry_run=args.dry_run)
    run(["git", "switch", "-c", args.branch], cwd=path, dry_run=args.dry_run)
    print(f"development started: {component} -> {args.branch}")
    return 0


def dev_push(args: argparse.Namespace) -> int:
    path = component_path(args.repo, args.component)
    _require_clean(path, args.component)
    branch = _branch(path)
    if not branch:
        raise RuntimeError(
            f"{args.component} is detached; no development branch to push"
        )
    if branch == args.base:
        raise RuntimeError(
            f"{args.component} is on {args.base}; refusing development push"
        )
    run(
        ["git", "push", "-u", args.remote, branch],
        cwd=path,
        dry_run=args.dry_run,
    )
    return 0


def dev_finish(args: argparse.Namespace) -> int:
    repo: Path = args.repo
    component = args.component
    path = component_path(repo, component)
    _require_clean(path, component)
    branch = _branch(path)

    if not branch:
        run(["git", "fetch", args.remote, "--prune"], cwd=path, dry_run=args.dry_run)
        pinned = _pinned_sha(repo, component)
        head = _head(path)
        if pinned is not None and head == pinned:
            print(f"{component}: already in normal pinned submodule state")
            return 0
        if _remote_ref_exists(path, args.remote, args.base):
            remote_head = _git_capture(path, "rev-parse", f"{args.remote}/{args.base}")
            if head == remote_head:
                _switch_base(path, args.base, args.remote, dry_run=args.dry_run)
                print(f"{component}: development-finished state ({args.base})")
                return 0
        raise RuntimeError(
            f"{component} is detached at an unknown commit; refusing to guess which development state it belongs to"
        )

    run(["git", "fetch", args.remote, "--prune"], cwd=path, dry_run=args.dry_run)
    if branch == args.base:
        _switch_base(path, args.base, args.remote, dry_run=args.dry_run)
        print(f"{component}: development-finished state ({args.base})")
        return 0

    if not args.dry_run:
        merged = _is_ancestor(path, branch, f"{args.remote}/{args.base}")
        if not merged and not args.force_delete:
            raise RuntimeError(
                f"{component} branch {branch!r} is not an ancestor of "
                f"{args.remote}/{args.base}. The PR may not be merged, or GitHub may have "
                "used squash/rebase merge. Verify the PR is merged, then rerun with "
                "--force-delete only when it is safe to discard the local branch."
            )

    _switch_base(path, args.base, args.remote, dry_run=args.dry_run)
    delete_flag = "-D" if args.force_delete else "-d"
    run(["git", "branch", delete_flag, branch], cwd=path, dry_run=args.dry_run)
    print(f"development finished: {component}; deleted {branch}; now on {args.base}")
    return 0


def test_component(args: argparse.Namespace) -> int:
    component = args.component
    path = component_path(args.repo, component)
    if args.build_dir:
        build_dir = args.build_dir.expanduser()
        if not build_dir.is_absolute():
            build_dir = path / build_dir
    else:
        rel_dirs = BUILD_DIRS.get(component)
        if not rel_dirs:
            raise RuntimeError(
                f"no default CMake/CTest build directory is registered for {component}; "
                "use --build-dir PATH"
            )
        build_dir = path / rel_dirs[0]

    build_dir = build_dir.absolute()
    if not build_dir.is_dir():
        raise RuntimeError(
            f"CTest build directory not found: {build_dir}; build {component} first"
        )

    if args.parallel == "auto":
        jobs = auto_parallel().jobs
    else:
        jobs = int(args.parallel)
    command = [
        "ctest",
        "--test-dir",
        str(build_dir),
        "--output-on-failure",
        "-j",
        str(jobs),
    ]
    if args.regex:
        command += ["-R", args.regex]
    run(command, dry_run=args.dry_run)
    return 0


def _parent_changes_other_than_component(repo: Path, component: str) -> list[str]:
    status = _git_status_porcelain(repo)
    unexpected: list[str] = []
    for line in status.splitlines():
        if len(line) < 4:
            unexpected.append(line)
            continue
        xy = line[:2]
        path = line[3:]
        # A component checked out at a different gitlink appears as an unstaged
        # modification in the superproject. That is expected before the bump.
        if path == component and xy[0] == " " and xy[1] == "M":
            continue
        unexpected.append(line)
    return unexpected


def submodule_update(args: argparse.Namespace) -> int:
    repo: Path = args.repo
    component = args.component
    component_path(repo, component)
    assert_component_development_finished(
        repo, component, base=args.base, remote=args.remote
    )

    parent_branch = _branch(repo)
    if not parent_branch:
        raise RuntimeError(
            "tsurugidb parent repository is detached; switch to a branch first"
        )
    unexpected = _parent_changes_other_than_component(repo, component)
    if unexpected:
        detail = "\n".join(f"  {line}" for line in unexpected)
        raise RuntimeError(
            "tsurugidb parent repository has unrelated changes; refusing automatic "
            f"submodule commit:\n{detail}"
        )

    print(f"parent branch: {parent_branch}")
    print(f"component:     {component}")
    run(
        ["git", "submodule", "update", "--remote", component],
        cwd=repo,
        dry_run=args.dry_run,
    )
    run(["git", "add", "--", component], cwd=repo, dry_run=args.dry_run)

    if not args.dry_run and _git_success(
        ["git", "diff", "--cached", "--quiet", "--", component], cwd=repo
    ):
        print(
            f"{component}: already points at the remote-tracking commit; no parent commit needed"
        )
        return 0

    run(["git", "commit", "-m", args.message], cwd=repo, dry_run=args.dry_run)
    if not args.no_push:
        run(["git", "push"], cwd=repo, dry_run=args.dry_run)
    return 0
