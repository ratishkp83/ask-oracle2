"""Atomic JSON persistence shared by the file-backed stores (ADR-014, ITM-013).

Write to a temp file in the destination directory, fsync, then ``os.replace``:
a crash mid-write leaves either the old or the new complete file on disk,
never a torn one. The temp lives in the *same* directory so the replace stays
on one volume — that is what makes it atomic on both POSIX and Windows.

Cross-*process* concurrency is out of scope: each store keeps its
single-process lock, and "one worker per store directory" remains the
documented deployment constraint (D7).
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Callable, Optional


def atomic_write_json(
    path: str,
    payload: Any,
    *,
    indent: int = 2,
    default: Optional[Callable[[Any], Any]] = None,
) -> None:
    """Serialize ``payload`` as JSON to ``path`` atomically.

    Mirrors ``json.dump(payload, fh, indent=indent, default=default)`` so the
    stores' on-disk shape is unchanged. On any failure the target file is left
    exactly as it was and the temp file is removed.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=directory, prefix=f".{os.path.basename(path)}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=indent, default=default)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # If os.fdopen itself raised, the raw descriptor was never adopted by a
        # file object — close it so it can't leak (review r1/R2). On the normal
        # path the `with` already closed it, so this is a no-op (bad-fd OSError).
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
