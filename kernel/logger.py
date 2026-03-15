import json
import logging
from datetime import datetime, UTC
from typing import Any

from kernel.config import KernelConfig, load_kernel_config


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=True)


def get_logger(name: str, config: KernelConfig | None = None) -> logging.Logger:
    runtime_config = config or load_kernel_config()
    runtime_config.memory_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    log_path = runtime_config.log_path
    has_target_handler = False
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == str(log_path):
            has_target_handler = True
            break

    if not has_target_handler:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger
