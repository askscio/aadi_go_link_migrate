from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parent / ".env"


def _load_dotenv() -> None:
    """Load key=value pairs from .env into os.environ (no-op if missing)."""
    if not _ENV_FILE.is_file():
        return
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if value and len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key:
                os.environ.setdefault(key, value)


_load_dotenv()


class ConflictStrategy(str, Enum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    FAIL = "fail"


@dataclass
class MigrationConfig:
    source_api_token: str = ""
    source_base_url: str = ""
    dest_api_token: str = ""
    dest_base_url: str = ""
    page_size: int = 100
    on_conflict: ConflictStrategy = ConflictStrategy.SKIP
    max_retries: int = 5
    dry_run: bool = False
    backup_dir: Path = field(default_factory=lambda: Path("."))

    @classmethod
    def from_env(cls, **overrides: object) -> MigrationConfig:
        """Build config from env vars, with explicit overrides taking precedence."""
        defaults = {
            "source_api_token": os.getenv("GLEAN_SOURCE_TOKEN", ""),
            "source_base_url": os.getenv("GLEAN_SOURCE_URL", ""),
            "dest_api_token": os.getenv("GLEAN_DEST_TOKEN", ""),
            "dest_base_url": os.getenv("GLEAN_DEST_URL", ""),
        }
        merged = {k: v for k, v in defaults.items()}
        for k, v in overrides.items():
            if v is not None:
                merged[k] = v
        return cls(**merged)  # type: ignore[arg-type]
