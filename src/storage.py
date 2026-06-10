from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

# Render native runtime uses /opt/render/project/src as the working directory.
# Docker uses /app. STORAGE_DIR env var overrides both.
_DEFAULT = os.path.join(
    os.getenv("RENDER_PROJECT_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "storage"
)
DEFAULT_STORAGE_DIR = os.getenv("STORAGE_DIR", _DEFAULT)
CONFIG_FILE = os.path.join(DEFAULT_STORAGE_DIR, "connection.json")
REPORTS_FILE = os.path.join(DEFAULT_STORAGE_DIR, "reports.json")


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def save_connection_config(config: Dict[str, object]) -> None:
    _ensure_dir(CONFIG_FILE)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def load_connection_config() -> Optional[Dict[str, object]]:
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_reports() -> Dict[str, Dict[str, object]]:
    if not os.path.exists(REPORTS_FILE):
        return {}
    with open(REPORTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def list_reports() -> List[str]:
    return sorted(list(_load_reports().keys()))


def get_report(name: str) -> Optional[Dict[str, object]]:
    return _load_reports().get(name)


def save_report(name: str, report: Dict[str, object]) -> None:
    _ensure_dir(REPORTS_FILE)
    data = _load_reports()
    data[name] = report
    with open(REPORTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def delete_report(name: str) -> None:
    data = _load_reports()
    if name in data:
        del data[name]
        with open(REPORTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
