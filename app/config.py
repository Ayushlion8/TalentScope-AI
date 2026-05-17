"""Runtime configuration for the SHL recommender service."""
from __future__ import annotations

import logging
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - exercised only in minimal envs
    def load_dotenv() -> bool:
        return False

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


CATALOG_PATH = _resolve_path(os.getenv("CATALOG_PATH"), PROJECT_ROOT / "data" / "catalog.json")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def configure_logging() -> None:
    """Configure application logging once from environment settings."""
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
