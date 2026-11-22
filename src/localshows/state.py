"""JSON state that lives in the repo."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def load(path: Path, default: Any) -> Any:
    """Return the saved value, or default if there is none.

    A corrupt file raises: treating it as empty would look like every show was canceled.
    """
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: Any) -> None:
    """Write atomically, with stable ordering so that git diffs show only real changes."""
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
