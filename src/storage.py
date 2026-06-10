from __future__ import annotations

import json
import os
from typing import Dict, Optional

# Render native runtime uses /opt/render/project/src as the working directory.
# Docker uses /app. STORAGE_DIR env var overrides both.
_DEFAULT = os.path.join(
    os.getenv("RENDER_PROJECT_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "storage"
)
DEFAULT_STORAGE_DIR = os.getenv("STORAGE_DIR", _DEFAULT)
CONFIG_FILE = os.path.join(DEFAULT_STORAGE_DIR, "connection.json")

# Saved reports moved to src/core/reports.py (Report v2 store) in Phase 4; they
# persist to ``reports.json`` under this same STORAGE_DIR.


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def save_connection_config(config: Dict[str, object]) -> None:
    """Persist the manual connection — **never** the password (F5).

    Profiles are the encrypted persistence path; this legacy single-connection
    file must not hold a plaintext secret at rest. The password (if supplied) is
    stripped before writing, so it lives only in the running session.
    """
    _ensure_dir(CONFIG_FILE)
    safe = {k: v for k, v in config.items() if k != "password"}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(safe, f, indent=2)


def load_connection_config() -> Optional[Dict[str, object]]:
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
