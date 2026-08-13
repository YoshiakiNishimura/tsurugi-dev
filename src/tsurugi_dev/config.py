from __future__ import annotations

import os
from pathlib import Path

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


def default_home() -> Path:
    """Resolve runtime home: TSURUGI_HOME first, then ~/git/tsurugi."""
    return env_path("TSURUGI_HOME") or (Path.home() / "git" / "tsurugi")


def default_config(home: Path) -> Path:
    """Resolve config: TSURUGI_CONF first, then the installed default."""
    return env_path("TSURUGI_CONF") or (home / "var" / "etc" / "tsurugi.ini")
