from pathlib import Path

from kernel.config import RuntimeConfig


RUNTIME_LIMITS = RuntimeConfig(retry_limit=3, minimum_confidence=0.6)

KERNEL_DIRECTORIES_READ_ONLY: tuple[str, ...] = ("kernel", "memory")
ALLOWED_MUTABLE_DIRECTORIES: tuple[str, ...] = ("projects", "agents", "evolution")


def get_read_only_paths(project_root: Path) -> tuple[Path, ...]:
    return tuple(project_root / directory for directory in KERNEL_DIRECTORIES_READ_ONLY)


def get_allowed_mutable_paths(project_root: Path) -> tuple[Path, ...]:
    return tuple(project_root / directory for directory in ALLOWED_MUTABLE_DIRECTORIES)
