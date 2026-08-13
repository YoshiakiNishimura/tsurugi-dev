from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import default_config, default_home
from .common.git import update_repository
from .common.process import quote
from .upstream import (
    build,
    clean,
    doctor,
    full_build,
    parse_component_dir,
    parse_parallel,
    resolve_layout,
    safe_name,
    source_root,
    verify,
)


def add_home_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--home",
        type=Path,
        default=default_home(),
        help="Tsurugi home/alias (default: $TSURUGI_HOME, otherwise ~/git/tsurugi)",
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
    update_repository(
        args.repo,
        pull=not args.no_pull,
        jobs=args.jobs,
        dry_run=args.dry_run,
    )
    return 0


def command_env(args: argparse.Namespace) -> int:
    home = args.home.expanduser().absolute()
    conf = args.conf.expanduser().absolute() if args.conf else default_config(home)
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
        type=source_root,
        default=Path.cwd().resolve(),
        help="tsurugidb source tree (default: current directory)",
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
        "update", help="update the parent repository and pinned submodules"
    )
    p.add_argument(
        "--no-pull", action="store_true", help="do not git pull the parent repository"
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
