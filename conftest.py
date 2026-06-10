"""Pytest bootstrap.

Lives at the repo root so the `src` package is importable from tests, and sets
test-only environment defaults BEFORE any module that reads them is imported.
"""

import os

# A deterministic key for tests only — never a real secret.
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-not-for-production")
# Keep test artifacts out of the real storage directory.
os.environ.setdefault(
    "STORAGE_DIR", os.path.join(os.path.dirname(__file__), ".pytest-storage")
)
