"""Application configuration."""

import os
from pathlib import Path


DEFAULT_QUERIES = (
    "psychologists",
    "plumbers",
    "electricians",
    "hairdressers",
    "accountants",
    "cleaning services",
    "restaurants",
    "dentists",
)


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE entries without an external dependency."""
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))
