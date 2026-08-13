"""Reusable helpers shared by Tsurugi development tooling.

This package intentionally contains no GRDMA-specific build policy.  Separate
setup projects can reuse process/Git/system/Java helpers without importing the
CLI layer.
"""

from .git import clone_repository_if_missing, update_repository, update_submodules
from .java import (
    JavaRuntime,
    apply_java_runtime,
    current_java_runtime,
    select_java_runtime,
)
from .process import capture, command_text, quote, run
from .system import (
    ParallelDecision,
    auto_parallel,
    available_cpu_count,
    choose_parallel,
)

__all__ = [
    "JavaRuntime",
    "ParallelDecision",
    "apply_java_runtime",
    "auto_parallel",
    "available_cpu_count",
    "capture",
    "choose_parallel",
    "clone_repository_if_missing",
    "command_text",
    "current_java_runtime",
    "quote",
    "run",
    "select_java_runtime",
    "update_repository",
    "update_submodules",
]
