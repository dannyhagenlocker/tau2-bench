"""Bootstrap sys.path for harness-opt scripts (hyphenated directory name)."""

from __future__ import annotations

import sys
from pathlib import Path

HARNESS_OPT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]


def bootstrap() -> None:
    """Add harness-opt and repo root to sys.path for imports."""
    for path in (str(HARNESS_OPT_ROOT), str(REPO_ROOT / "src")):
        if path not in sys.path:
            sys.path.insert(0, path)
