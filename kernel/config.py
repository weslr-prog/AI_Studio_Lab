from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KernelConfig:
    project_root: Path
    memory_dir: Path
    db_path: Path
    log_path: Path


@dataclass(frozen=True)
class RuntimeConfig:
    retry_limit: int
    minimum_confidence: float


def load_kernel_config() -> KernelConfig:
    project_root = Path(__file__).resolve().parent.parent
    memory_dir = project_root / "memory"
    db_path = memory_dir / "studio.db"
    log_path = memory_dir / "kernel.log"
    return KernelConfig(
        project_root=project_root,
        memory_dir=memory_dir,
        db_path=db_path,
        log_path=log_path,
    )
