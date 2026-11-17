"""
Local data snapshot: real data frozen at a timestamp (PROJECT_DESIGN.md §4.1).

`uv run python -m campaign_intel.ingest.build_snapshot` writes data/cache/*.parquet and
data/cache/manifest.json. The app reads only from here, so demos never depend on a live API.
"""

from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from campaign_intel.config import CACHE_DIR

MANIFEST = CACHE_DIR / "manifest.json"


class SnapshotMissing(FileNotFoundError):
    pass


def path_for(name: str):
    return CACHE_DIR / f"{name}.parquet"


@lru_cache(maxsize=64)
def _read(name: str, mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path_for(name))


def read_table(name: str) -> pd.DataFrame:
    p = path_for(name)
    if not p.exists():
        raise SnapshotMissing(f"Snapshot table '{name}' not found. Run: uv run python -m campaign_intel.ingest.build_snapshot")
    return _read(name, p.stat().st_mtime).copy()


def has_table(name: str) -> bool:
    return path_for(name).exists()


def manifest() -> dict:
    if not MANIFEST.exists():
        return {}
    return json.loads(MANIFEST.read_text())
