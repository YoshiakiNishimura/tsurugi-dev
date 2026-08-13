from __future__ import annotations

import os
from pathlib import Path

TSURUGI_DEV_WORKSPACE_ENV = "TSURUGI_DEV_WORKSPACE"
TSURUGIDB_REPOSITORY_URL = "git@github.com:project-tsurugi/tsurugidb.git"
TSURUGIDB_REPOSITORY_NAME = "tsurugidb"

COMPONENT_ENV = {
    "tateyama-bootstrap": "TG_TATEYAMA_BOOTSTRAP_DIR",
    "jogasaki": "TG_JOGASAKI_DIR",
    "tateyama": "TG_TATEYAMA_DIR",
    "data-relay-grpc": "TG_DATA_RELAY_GRPC_DIR",
    "sharksfin": "TG_SHARKSFIN_DIR",
    "shirakami": "TG_SHIRAKAMI_DIR",
    "yakushima": "TG_YAKUSHIMA_DIR",
    "limestone": "TG_LIMESTONE_DIR",
    "mizugaki": "TG_MIZUGAKI_DIR",
    "yugawara": "TG_YUGAWARA_DIR",
    "takatori": "TG_TAKATORI_DIR",
    "tsubakuro": "TG_TSUBAKURO_DIR",
    "tanzawa": "TG_TANZAWA_DIR",
    "harinoki": "TG_HARINOKI_DIR",
}

REQUIRED_SOURCE_DIRS = tuple(COMPONENT_ENV)

VERIFY_PATHS = (
    "bin/tsurugidb",
    "bin/tgctl",
    "bin/tgsql",
    "bin/tgdump",
    "var/etc/tsurugi.ini",
    "var/data",
    "var/blob/sessions",
    "var/plugins",
)

# Build directories used by the current tsurugidb/dist/install scripts.
# Keep this narrow: clean must not become a generic git clean.
BUILD_DIRS = {
    "takatori": ("build",),
    "yugawara": ("build", "build-hopscotch-map"),
    "mizugaki": ("build",),
    "limestone": ("build",),
    "yakushima": ("build",),
    "shirakami": ("build",),
    "sharksfin": ("build",),
    "tateyama": ("build", "build-concurrentqueue"),
    "data-relay-grpc": ("server/build",),
    "jogasaki": ("build-shirakami",),
    "tateyama-bootstrap": ("build",),
    "tsubakuro": ("modules/ipc/src/main/native/build",),
}

GRADLE_COMPONENTS = ("tsubakuro", "tanzawa", "harinoki")


def env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser()


def default_workspace() -> Path:
    """Resolve the checkout workspace used by tsurugi-dev.

    Resolution order:
      1. $TSURUGI_DEV_WORKSPACE
      2. ~/git
    """
    return env_path(TSURUGI_DEV_WORKSPACE_ENV) or (Path.home() / "git")


def is_tsurugidb_source(path: Path) -> bool:
    """Return True when *path* looks like the tsurugidb source root."""
    return (path / "install.sh").is_file() and (path / ".gitmodules").is_file()


def default_repo() -> Path:
    """Return the default tsurugidb checkout path."""
    return (default_workspace() / TSURUGIDB_REPOSITORY_NAME).expanduser().absolute()


def default_home() -> Path:
    """Resolve runtime home: TSURUGI_HOME first, then workspace/tsurugi."""
    return env_path("TSURUGI_HOME") or (default_workspace() / "tsurugi")


def default_config(home: Path) -> Path:
    """Resolve config: TSURUGI_CONF first, then the installed default."""
    return env_path("TSURUGI_CONF") or (home / "var" / "etc" / "tsurugi.ini")
