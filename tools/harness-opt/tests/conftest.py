"""Pytest configuration for harness-opt."""

from __future__ import annotations

import sys
from pathlib import Path

HARNESS_OPT = Path(__file__).resolve().parents[1]
if str(HARNESS_OPT) not in sys.path:
    sys.path.insert(0, str(HARNESS_OPT))

from lib.bootstrap import bootstrap

bootstrap()
