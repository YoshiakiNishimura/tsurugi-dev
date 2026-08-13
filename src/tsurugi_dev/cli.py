from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .common.git import clone_repository_if_missing, update_repository
from .common.process import quote
from .config import (
    TSURUGIDB_REPOSITORY_URL,
    default_config,
    default_home,
    default_repo,
    default_workspace,
    is_tsurugidb_source,
)
from .upstream import (
    build,
    clean,
    doctor,
    full_build,
    parse_component_dir,
    parse_parallel,
    safe_name,
    verify,
)


def repo_path(value: str) -> Path:
    return Path(value).expanduser().absolute()


def add_home_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--home",
        type=Path,
        default=default_home(),
        help=(
            "Tsurugi home/alias (default: $TSURUGI_HOME, otherwise "
            "$TSURUGI_DEV_WORKSPACE/tsurugi)"
        ),
    )


def add_component_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--component-dir",
        action="append",
        type=parse_component_dir,
        default=[],
        metavar="COMPONENT=PATH",
        help="use an external checkout for one component (repeatable)",
    )


def add_layout_arguments(parser: argparse.ArgumentParser) -> None:
    add_home_argument(parser)
    parser.add_argument(
        "--prefix",
        type=Path,
        help="upstream installation parent directory (default: parent of TSURUGI_HOME)",
    )
    parser.add_argument(
        "--build-type",
        choices=("Debug", "Release", "RelWithDebInfo"),
        default="RelWithDebInfo",
        help="CMake build type (default: RelWithDebInfo)",
    )
    parser.add_argument(
        "--name",
        type=safe_name,
        help="upstream version/name (default: dev-<build-type>)",
    )


def add_build_arguments(parser: argparse.ArgumentParser) -> None:
    add_layout_arguments(parser)
    parser.add_argument(
        "--parallel",
        type=parse_parallel,
        default="auto",
        metavar="auto|N",
        help="parallel build jobs (default: auto from CPU affinity and MemAvailable)",
    )
    parser.add_argument(
        "--ccache", action="store_true", help="use ccache as compiler launcher"
    )
    parser.add_argument("--tracy", action="store_true", help="pass -DTRACY_ENABLE=ON")
    parser.add_argument(
        "--altimeter", action="store_true", help="pass -DENABLE_ALTIMETER=ON"
    )
    parser.add_argument(
        "--no-jemalloc", action="store_true", help="disable jemalloc in bootstrap"
    )
    parser.add_argument(
        "--force-mpdecimal",
        action="store_true",
        help="force bundled mpdecimal installation",
    )
    parser.add_argument(
        "--legacy-build-all-compat",
        action="store_true",
        help=(
            "temporary compatibility mode: force C++20 for Jogasaki Arrow/Parquet "
            "objects and prefer $TSURUGI_DEV_WORKSPACE/.opt in CMAKE_PREFIX_PATH"
        ),
    )
    parser.add_argument(
        "--cmake-option",
        action="append",
        default=[],
        metavar="-DNAME=VALUE",
        help="append to TG_COMMON_CMAKE_BUILD_OPTIONS (repeatable)",
    )
    parser.add_argument(
        "--shirakami-option",
        action="append",
        default=[],
        metavar="-DNAME=VALUE",
        help="append to TG_SHIRAKAMI_OPTIONS (repeatable)",
    )
    add_component_argument(parser)
    parser.add_argument(
        "--skip",
        action="append",
        choices=("server", "nativelib", "tanzawa", "harinoki", "grpc"),
        default=[],
        help="skip an upstream install group (repeatable)",
    )
    parser.add_argument(
        "--replace-config",
        action="append",
        default=[],
        metavar="SECTION.KEY=VALUE",
        help="forward a config replacement to upstream --replaceconfig (repeatable)",
    )
    parser.add_argument(
        "--replace-home",
        action="store_true",
        help="replace an existing non-symlink TSURUGI_HOME after a successful build (destructive)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="enable verbose upstream output"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print commands without executing"
    )


def command_update(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().absolute()
    cloned = clone_repository_if_missing(
        repo,
        TSURUGIDB_REPOSITORY_URL,
        dry_run=args.dry_run,
    )

    if not args.dry_run and not is_tsurugidb_source(repo):
        raise RuntimeError(
            f"cloned/existing repository is not a tsurugidb source tree: {repo}"
        )

    # A fresh clone already has the current parent branch, so avoid an immediate pull.
    update_repository(
        repo,
        pull=(not args.no_pull and not cloned),
        jobs=args.jobs,
        dry_run=args.dry_run,
    )
    return 0


def command_env(args: argparse.Namespace) -> int:
    workspace = default_workspace().expanduser().absolute()
    home = args.home.expanduser().absolute()
    conf = args.conf.expanduser().absolute() if args.conf else default_config(home)
    print(f"export TSURUGI_DEV_WORKSPACE={quote(str(workspace))}")
    print(f"export TSURUGI_HOME={quote(str(home))}")
    print(f"export TSURUGI_CONF={quote(str(conf))}")
    print('export PATH="${TSURUGI_HOME}/bin:${PATH}"')
    print(
        'export LD_LIBRARY_PATH="${TSURUGI_HOME}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"'
    )
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tsurugi-dev",
        description="Development wrapper around tsurugidb's upstream install.sh.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--repo",
        type=repo_path,
        default=default_repo(),
        help=(
            "tsurugidb source tree (default: "
            "$TSURUGI_DEV_WORKSPACE/tsurugidb, otherwise ~/git/tsurugidb)"
        ),
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("full-build", help="clean build and install the full tree")
    add_build_arguments(p)
    p.set_defaults(func=full_build)

    p = sub.add_parser(
        "build", aliases=["diff-build"], help="incremental/differential build"
    )
    add_build_arguments(p)
    p.set_defaults(func=build)

    p = sub.add_parser("clean", help="remove known build outputs")
    add_layout_arguments(p)
    add_component_argument(p)
    p.add_argument("--skip-gradle", action="store_true", help="do not run Gradle clean")
    p.add_argument(
        "--install", action="store_true", help="also remove this wrapper's install tree"
    )
    p.add_argument("--dry-run", action="store_true", help="show removal targets only")
    p.set_defaults(func=clean)

    p = sub.add_parser(
        "update",
        help="clone tsurugidb if missing, then update the parent repository and pinned submodules",
    )
    p.add_argument(
        "--no-pull",
        action="store_true",
        help="do not git pull an existing parent repository",
    )
    p.add_argument(
        "--jobs", type=int, metavar="N", help="git submodule update parallelism"
    )
    p.add_argument("--dry-run", action="store_true", help="print Git commands only")
    p.set_defaults(func=command_update)

    p = sub.add_parser("doctor", help="check tools, source tree and auto parallelism")
    add_home_argument(p)
    add_component_argument(p)
    p.set_defaults(func=doctor)

    p = sub.add_parser("verify", help="verify installed files and shared libraries")
    add_home_argument(p)
    p.set_defaults(func=verify)

    p = sub.add_parser("env", help="print recommended runtime shell exports")
    add_home_argument(p)
    p.add_argument(
        "--conf", type=Path, help="override TSURUGI_CONF in generated exports"
    )
    p.set_defaults(func=command_env)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # CLI boundary: present subprocess/OS errors cleanly.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
