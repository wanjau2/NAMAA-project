"""Load Alfred's `namaa_ai` package without vendoring a copy into `api/`."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_namaa_ai() -> None:
    try:
        import namaa_ai  # noqa: F401
        return
    except ImportError:
        pass
    src = Path(__file__).resolve().parents[2] / "ai" / "src"
    if src.is_dir():
        sys.path.insert(0, str(src))
    import namaa_ai  # noqa: F401
