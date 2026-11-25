"""API keys: from the environment, or from a gitignored .env file in the repo."""

import os
from pathlib import Path


def load_env(root: Path) -> dict[str, str]:
    values = {}
    path = root / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("'\"")
    # The environment wins, so GitHub Actions secrets override any file.
    values.update({key: value for key, value in os.environ.items() if value})
    return values


def require(values: dict[str, str], *keys: str) -> list[str]:
    missing = [key for key in keys if not values.get(key)]
    if missing:
        raise SystemExit(f"missing {', '.join(missing)}: add to .env (see README)")
    return [values[key] for key in keys]
