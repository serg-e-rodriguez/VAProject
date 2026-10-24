"""
SQLite Scenario Storage and Comparative Analytics per §7.8.
Persists scenario payloads to data/scenarios.db.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from campaign_intel.config import SCENARIOS_DB


def init_db(db_path: Path | None = None):
    p = db_path or SCENARIOS_DB
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                scope TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                payload_json TEXT NOT NULL
            )
        """)
        conn.commit()


def save_scenario(
    name: str,
    scope: str,
    unit_type: str,
    allocation: pd.DataFrame,
    assumptions_dict: dict[str, Any],
    results_dict: dict[str, Any],
    db_path: Path | None = None,
) -> int:
    init_db(db_path)
    p = db_path or SCENARIOS_DB

    payload = {
        "allocation": allocation.to_dict(orient="records") if allocation is not None else [],
        "assumptions": assumptions_dict,
        "results": results_dict,
    }

    with sqlite3.connect(p) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO scenarios (name, scope, unit_type, created_at, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, scope, unit_type, datetime.now().isoformat(), json.dumps(payload))
        )
        conn.commit()
        return cursor.lastrowid


def list_scenarios(db_path: Path | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    p = db_path or SCENARIOS_DB
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, scope, unit_type, created_at, payload_json FROM scenarios ORDER BY id DESC")
        rows = cursor.fetchall()
        result = []
        for r in rows:
            payload = json.loads(r["payload_json"])
            result.append({
                "id": r["id"],
                "name": r["name"],
                "scope": r["scope"],
                "unit_type": r["unit_type"],
                "created_at": r["created_at"],
                "allocation": pd.DataFrame(payload.get("allocation", [])),
                "assumptions": payload.get("assumptions", {}),
                "results": payload.get("results", {})
            })
        return result


def delete_scenario(scenario_id: int, db_path: Path | None = None):
    init_db(db_path)
    p = db_path or SCENARIOS_DB
    with sqlite3.connect(p) as conn:
        conn.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
        conn.commit()
