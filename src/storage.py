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


def load_connection_config() -> Optional[Dict[str, object]]:
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def migrate_legacy_connection() -> Optional[Dict[str, object]]:
    """Retire the legacy ``connection.json`` (ITM-006).

    The encrypted ``ProfileStore`` is the **single** persistence path. The
    manual connection no longer writes to disk; if a legacy file is present we
    read its fields into the caller (for this session only) and **delete the
    file** — removing the second on-disk path and, incidentally, any
    pre-Phase-4 file that still held a plaintext password. Idempotent: returns
    ``None`` when there is nothing to migrate.
    """
    cfg = load_connection_config()
    if cfg is None:
        return None
    try:
        os.remove(CONFIG_FILE)
    except OSError:
        pass
    return cfg
