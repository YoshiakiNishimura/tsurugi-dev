from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import (
    BUILD_DIRS,
    COMPONENT_ENV,
    GRADLE_COMPONENTS,
    REQUIRED_SOURCE_DIRS,
    VERIFY_PATHS,
    default_config,
    default_workspace,
    is_tsurugidb_source,
)
from .common.java import (
    JavaRuntime,
    apply_java_runtime,
    current_java_runtime,
    select_java_runtime,
)
from .common.process import capture, quote, run
from .common.system import ParallelDecision, auto_parallel


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def source_root(value: str | os.PathLike[str]) -> Path:
    root = Path(value).expanduser().resolve()
    if not is_tsurugidb_source(root):
        raise argparse.ArgumentTypeError(
            f"not a tsurugidb source tree: {root} (install.sh/.gitmodules not found)"
        )
    return root


def parse_component_dir(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected COMPONENT=PATH")
    name, raw_path = value.split("=", 1)
    if name not in COMPONENT_ENV:
        raise argparse.ArgumentTypeError(
            f"unknown component {name!r}; choose one of: {', '.join(sorted(COMPONENT_ENV))}"
        )
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"component directory not found: {path}")
    return name, path


def safe_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise argparse.ArgumentTypeError(
            "name may contain only letters, digits, '.', '_' and '-'"
        )
    return value


def parse_parallel(value: str) -> str | int:
    if value == "auto":
        return value
    try:
        jobs = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected 'auto' or a positive integer"
        ) from exc
    if jobs < 1:
        raise argparse.ArgumentTypeError("parallel jobs must be >= 1")
    return jobs


def resolve_parallel(value: str | int) -> tuple[int, ParallelDecision | None]:
    if value == "auto":
        decision = auto_parallel()
        return decision.jobs, decision
    return int(value), None


def component_paths(repo: Path, overrides: list[tuple[str, Path]]) -> dict[str, Path]:
    override_map = dict(overrides)
    return {name: override_map.get(name, repo / name) for name in COMPONENT_ENV}


def validate_submodules(repo: Path, overrides: dict[str, Path]) -> list[str]:
    missing: list[str] = []
    for name in REQUIRED_SOURCE_DIRS:
        path = overrides.get(name, repo / name)
        if not path.is_dir():
            missing.append(f"{name}: directory not found ({path})")
            continue
        if name in {"tsubakuro", "tanzawa", "harinoki"}:
            continue
        if (path / "CMakeLists.txt").is_file():
            continue
        if name == "data-relay-grpc" and (path / "server" / "CMakeLists.txt").is_file():
            continue
        missing.append(f"{name}: checkout looks incomplete ({path})")
    return missing


@dataclass(frozen=True)
class InstallLayout:
    home: Path
    prefix: Path
    name: str

    @property
    def install_dir(self) -> Path:
        return self.prefix / f"tsurugi-{self.name}"

    @property
    def upstream_symbolic_home(self) -> Path:
        return self.prefix / "tsurugi"


def resolve_layout(args: argparse.Namespace) -> InstallLayout:
    home = args.home.expanduser().absolute()
    prefix = (args.prefix or home.parent).expanduser().absolute()
    name = args.name or f"dev-{args.build_type.lower()}"
    return InstallLayout(home=home, prefix=prefix, name=name)


def build_install_env(
    args: argparse.Namespace, layout: InstallLayout, *, clean: bool
) -> dict[str, str]:
    env = os.environ.copy()
    env["TG_RELEASE_TSURUGI_VERSION"] = layout.name
    env["TG_CLEAN_BUILD"] = "clean" if clean else "keep"
    env["TG_ENABLE_JEMALLOC"] = "OFF" if args.no_jemalloc else "ON"

    common_options = list(args.cmake_option)
    if args.ccache:
        if shutil.which("ccache") is None:
            raise RuntimeError("--ccache requested, but ccache is not in PATH")
        common_options.extend(
            [
                "-DCMAKE_C_COMPILER_LAUNCHER=ccache",
                "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache",
            ]
        )
    if args.tracy:
        common_options.append("-DTRACY_ENABLE=ON")
    if args.altimeter:
        common_options.append("-DENABLE_ALTIMETER=ON")

    # Temporary compatibility mode for environments that were previously built
    # with the legacy build_all.sh scripts.  Keep the workaround entirely in
    # the wrapper: do not modify the Jogasaki source tree.
    if getattr(args, "legacy_build_all_compat", False):
        # Jogasaki explicitly provides this option for the Arrow/Parquet object
        # target.  It is harmless for other projects that do not consume it.
        common_options.append("-DFORCE_CXX20_ARROW_OBJS=ON")

        # The old build_all.sh family searched ~/git/.opt before the install
        # prefix.  Reproduce that lookup only when .opt exists.  This option is
        # appended after the upstream installer's own CMAKE_PREFIX_PATH, so the
        # compatibility value wins for CMake projects in this build.
        opt_prefix = default_workspace().expanduser().absolute() / ".opt"
        if opt_prefix.is_dir():
            common_options.append(
                f"-DCMAKE_PREFIX_PATH={opt_prefix};{layout.install_dir}"
            )

    if common_options:
        env["TG_COMMON_CMAKE_BUILD_OPTIONS"] = " ".join(common_options)

    if args.shirakami_option:
        env["TG_SHIRAKAMI_OPTIONS"] = " ".join(args.shirakami_option)
    if args.force_mpdecimal:
        env["TG_FORCE_INSTALL_MPDECIMAL"] = "ON"

    for component, path in args.component_dir:
        env[COMPONENT_ENV[component]] = str(path)

    return env


def preflight_home_link(layout: InstallLayout, replace_home: bool) -> None:
    home = layout.home
    if home in {layout.install_dir, layout.upstream_symbolic_home}:
        return
    if home.is_symlink() or not home.exists() or replace_home:
        return
    raise RuntimeError(
        f"TSURUGI_HOME exists and is not a symlink: {home}\n"
        "The upstream installer installs into a versioned sibling directory. "
        "Move the old directory away first, or use --replace-home after making a backup."
    )


def update_home_link(layout: InstallLayout, replace_home: bool) -> None:
    home = Path(os.path.abspath(layout.home))
    target = layout.install_dir.resolve()

    if home == layout.install_dir or home == layout.upstream_symbolic_home:
        return

    home.parent.mkdir(parents=True, exist_ok=True)
    if home.is_symlink():
        home.unlink()
    elif home.exists():
        if not replace_home:
            raise RuntimeError(
                f"TSURUGI_HOME exists and is not a symlink: {home}; use --replace-home"
            )
        if home.is_dir():
            shutil.rmtree(home)
        else:
            home.unlink()

    home.symlink_to(target, target_is_directory=True)
    print(f"TSURUGI_HOME link: {home} -> {target}")


def configure_build_java(
    args: argparse.Namespace,
    env: dict[str, str],
    skip: list[str],
) -> tuple[dict[str, str], JavaRuntime | None, JavaRuntime | None]:
    """Select Java 17+ for the build when Harinoki is enabled.

    The caller's shell environment is never mutated. If Java 17+ is not
    available, Harinoki is skipped automatically so the core/server build can
    still complete.
    """
    current = current_java_runtime(env)
    if "harinoki" in skip:
        return env, current, None

    runtime = select_java_runtime(
        min_major=17,
        preferred_major=17,
        explicit_home=getattr(args, "java_home", None),
        env=env,
    )
    if runtime is None:
        skip.append("harinoki")
        eprint(
            "warning: Java 17+ was not found; automatically skipping harinoki "
            "(Tsurugi Authentication Server)"
        )
        return env, current, None

    return apply_java_runtime(env, runtime), current, runtime


def execute_build(args: argparse.Namespace, *, clean: bool) -> int:
    repo: Path = args.repo
    if not is_tsurugidb_source(repo):
        eprint(f"tsurugidb source repository not found: {repo}")
        eprint("run 'tsurugi-dev update' first to clone/update the source tree")
        return 2

    layout = resolve_layout(args)
    layout.prefix.mkdir(parents=True, exist_ok=True)

    overrides: dict[str, Path] = dict(args.component_dir)
    missing = validate_submodules(repo, overrides)
    if missing:
        eprint("source tree is incomplete:")
        for item in missing:
            eprint(f"  - {item}")
        eprint("run 'tsurugi-dev update' first, or use --component-dir COMPONENT=PATH")
        return 2

    try:
        preflight_home_link(layout, args.replace_home)
        env = build_install_env(args, layout, clean=clean)
        jobs, auto_decision = resolve_parallel(args.parallel)
        effective_skip = list(args.skip)
        env, current_java, build_java = configure_build_java(args, env, effective_skip)
    except RuntimeError as exc:
        eprint(f"error: {exc}")
        return 2

    command = [
        str(repo / "install.sh"),
        f"--prefix={layout.prefix}",
        f"--buildtype={args.build_type}",
        f"--parallel={jobs}",
        "--symbolic",
    ]
    if args.verbose:
        command.append("--verbose")
    if effective_skip:
        command.append(f"--skip={','.join(effective_skip)}")
    if args.replace_config:
        command.append(f"--replaceconfig={','.join(args.replace_config)}")

    mode = "full" if clean else "incremental"
    print(f"[{mode} build]")
    print(f"source:        {repo}")
    print(f"TSURUGI_HOME:  {layout.home}")
    print(f"install dir:   {layout.install_dir}")
    print(f"build type:    {args.build_type}")
    if auto_decision is not None:
        print(f"parallel:      {jobs} (auto: {auto_decision.reason})")
    else:
        print(f"parallel:      {jobs} (explicit)")
    print(f"TG_CLEAN_BUILD={env['TG_CLEAN_BUILD']}")
    if getattr(args, "legacy_build_all_compat", False):
        print("build_all compatibility: ON (default)")
    if current_java is not None:
        print(f"shell java:    {current_java.major} ({current_java.executable})")
    if build_java is not None:
        switched = (
            current_java is None or current_java.executable != build_java.executable
        )
        suffix = " [auto-selected]" if switched else ""
        print(f"build java:    {build_java.major} ({build_java.executable}){suffix}")
    elif "harinoki" in effective_skip:
        print("build java:    Java 17+ unavailable/not required; harinoki skipped")
    if effective_skip:
        print(f"skip:          {','.join(effective_skip)}")
    if env.get("TG_COMMON_CMAKE_BUILD_OPTIONS"):
        print(f"TG_COMMON_CMAKE_BUILD_OPTIONS={env['TG_COMMON_CMAKE_BUILD_OPTIONS']}")
    for component, _ in args.component_dir:
        key = COMPONENT_ENV[component]
        print(f"{key}={env[key]}")

    run(command, cwd=repo, env=env, dry_run=args.dry_run)
    if args.dry_run:
        return 0

    if not layout.install_dir.is_dir():
        eprint(
            f"error: expected install directory was not created: {layout.install_dir}"
        )
        return 2

    try:
        update_home_link(layout, args.replace_home)
    except RuntimeError as exc:
        eprint(f"error: {exc}")
        return 2

    print("\nEnvironment:")
    print(f"export TSURUGI_HOME={quote(str(layout.home))}")
    if os.environ.get("TSURUGI_CONF"):
        print(f"export TSURUGI_CONF={quote(os.environ['TSURUGI_CONF'])}")
    return 0


def build(args: argparse.Namespace) -> int:
    return execute_build(args, clean=False)


def full_build(args: argparse.Namespace) -> int:
    return execute_build(args, clean=True)


def remove_path(path: Path, *, dry_run: bool) -> None:
    if not path.exists() and not path.is_symlink():
        return
    print(f"remove: {path}")
    if dry_run:
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def clean(args: argparse.Namespace) -> int:
    repo: Path = args.repo
    if not is_tsurugidb_source(repo):
        eprint(f"tsurugidb source repository not found: {repo}")
        eprint("run 'tsurugi-dev update' first to clone/update the source tree")
        return 2

    paths = component_paths(repo, args.component_dir)

    print("[CMake/Ninja build directories]")
    for component, rel_dirs in BUILD_DIRS.items():
        base = paths[component]
        for rel in rel_dirs:
            remove_path(base / rel, dry_run=args.dry_run)

    if not args.skip_gradle:
        print("\n[Gradle build outputs]")
        for component in GRADLE_COMPONENTS:
            base = paths[component]
            gradlew = base / "gradlew"
            if gradlew.is_file():
                run([str(gradlew), "clean"], cwd=base, dry_run=args.dry_run)

    if args.install:
        layout = resolve_layout(args)
        print("\n[install tree]")
        if layout.home.is_symlink():
            try:
                if layout.home.resolve() == layout.install_dir.resolve():
                    remove_path(layout.home, dry_run=args.dry_run)
            except FileNotFoundError:
                remove_path(layout.home, dry_run=args.dry_run)
        remove_path(layout.install_dir, dry_run=args.dry_run)

        stable = layout.upstream_symbolic_home
        if stable.is_symlink():
            try:
                if stable.resolve() == layout.install_dir.resolve():
                    remove_path(stable, dry_run=args.dry_run)
            except FileNotFoundError:
                remove_path(stable, dry_run=args.dry_run)

    print("\nclean: OK")
    return 0


def doctor(args: argparse.Namespace) -> int:
    repo: Path = args.repo
    failures = 0
    home = args.home.expanduser().absolute()

    print(f"source: {repo}")
    print(f"TSURUGI_HOME: {home}")
    print(f"TSURUGI_CONF: {default_config(home)}")
    decision = auto_parallel()
    print(f"parallel(auto): {decision.jobs} ({decision.reason})")
    current_java = current_java_runtime()
    selected_java = select_java_runtime(min_major=17, preferred_major=17)
    if current_java is None:
        print("java(current): unavailable")
    else:
        print(f"java(current): {current_java.major} ({current_java.executable})")
    if selected_java is None:
        print("java(build): Java 17+ not found; harinoki will be skipped")
    else:
        print(f"java(build): {selected_java.major} ({selected_java.executable})")
    if (repo / "VERSION").is_file():
        print(f"VERSION: {(repo / 'VERSION').read_text(encoding='utf-8').strip()}")

    print("\n[tools]")
    for tool in ("git", "cmake", "ninja", "make", "tar", "curl", "java"):
        path = shutil.which(tool)
        if path:
            print(f"OK   {tool}: {path}")
        else:
            print(f"MISS {tool}")
            failures += 1

    print("\n[source tree]")
    if not is_tsurugidb_source(repo):
        print(f"MISS tsurugidb repository: {repo}")
        print("     run 'tsurugi-dev update' to clone it and initialize submodules")
        return failures + 1

    overrides: dict[str, Path] = dict(args.component_dir)
    missing = validate_submodules(repo, overrides)
    if missing:
        for item in missing:
            print(f"MISS {item}")
        failures += len(missing)
    else:
        print("OK   required component checkouts are present")

    if shutil.which("git"):
        try:
            head = capture(["git", "rev-parse", "--short", "HEAD"], cwd=repo)
            branch = (
                capture(["git", "branch", "--show-current"], cwd=repo) or "(detached)"
            )
            print(f"git: branch={branch} head={head}")
        except subprocess.CalledProcessError:
            print("WARN source tree is not a normal Git checkout")

    if failures:
        print(f"\ndoctor: {failures} problem(s) found")
        return 1
    print("\ndoctor: OK")
    return 0


def verify(args: argparse.Namespace) -> int:
    home = args.home.expanduser().absolute()
    failures = 0
    print(f"TSURUGI_HOME: {home}")

    for rel in VERIFY_PATHS:
        path = home / rel
        if path.exists():
            print(f"OK   {rel}")
        else:
            print(f"MISS {rel}")
            failures += 1

    config = default_config(home)
    if config.is_file():
        print(f"OK   TSURUGI_CONF: {config}")
    else:
        print(f"MISS TSURUGI_CONF: {config}")
        failures += 1

    native_candidates = (
        list((home / "lib").glob("libtsubakuro.so*")) if (home / "lib").is_dir() else []
    )
    if native_candidates:
        print(f"OK   native library: {native_candidates[0].name}")
    else:
        print("MISS lib/libtsubakuro.so*")
        failures += 1

    server = home / "bin" / "tsurugidb"
    if server.is_file() and shutil.which("ldd"):
        result = subprocess.run(
            ["ldd", str(server)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        missing = [
            line.strip() for line in result.stdout.splitlines() if "not found" in line
        ]
        if missing:
            print("MISS unresolved shared libraries:")
            for line in missing:
                print(f"     {line}")
            failures += len(missing)
        else:
            print("OK   ldd: no unresolved shared libraries")

    if failures:
        print(f"\nverify: {failures} problem(s) found")
        return 1
    print("\nverify: OK")
    return 0
