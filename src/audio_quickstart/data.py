"""Synthetic asset-readings database (SQLite) — the generic stand-in for a warehouse.

Production deployments of this pattern point the data tools at a real store
(a warehouse, an ERP, an API). The quickstart stubs that dependency with a
local SQLite file seeded with deterministic synthetic data, so the flow runs
anywhere with zero external services and zero credentials.

Schema mirrors a typical daily-rollup readings table:

    DAILY_ASSET_READINGS(asset_name TEXT, record_date TEXT,
                         output_units REAL, energy_kwh REAL, runtime_hours REAL)
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path

ASSETS: tuple[str, ...] = (
    "PUMP A1",
    "PUMP A2",
    "COMPRESSOR B1",
    "COMPRESSOR B2",
    "GENERATOR C1",
)

METRIC_COLS = {
    "output_units": "OUTPUT_UNITS",
    "energy_kwh": "ENERGY_KWH",
    "runtime_hours": "RUNTIME_HOURS",
}

METRIC_UNITS = {
    "output_units": "units",
    "energy_kwh": "kWh",
    "runtime_hours": "h",
}

METRIC_LABELS = {
    "output_units": "output",
    "energy_kwh": "energy use",
    "runtime_hours": "runtime",
}

_DAYS = 45  # history depth


def _db_path() -> Path:
    """A writable location: the platform state dir when present, else tmp."""
    for env in ("CREWAI_STORAGE_DIR", "XDG_DATA_HOME"):
        root = os.environ.get(env)
        if root and os.path.isdir(root):
            return Path(root) / "audio_quickstart" / "readings.db"
    return Path(tempfile.gettempdir()) / "audio_quickstart_readings.db"


def connect() -> sqlite3.Connection:
    """Open (and seed on first use) the synthetic readings database."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='DAILY_ASSET_READINGS'"
    )
    if cur.fetchone() is None:
        _seed(conn)
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE DAILY_ASSET_READINGS ("
        " ASSET_NAME TEXT NOT NULL,"
        " RECORD_DATE TEXT NOT NULL,"
        " OUTPUT_UNITS REAL, ENERGY_KWH REAL, RUNTIME_HOURS REAL,"
        " PRIMARY KEY (ASSET_NAME, RECORD_DATE))"
    )
    today = date.today()
    rows = []
    for a_idx, asset in enumerate(ASSETS):
        for d in range(_DAYS):
            day = today - timedelta(days=d)
            # Deterministic pseudo-variation — no randomness, reproducible.
            wave = ((a_idx + 1) * 37 + d * 13) % 20
            rows.append((
                asset,
                day.isoformat(),
                round(400 + a_idx * 120 + wave * 3.5, 2),
                round(90 + a_idx * 25 + wave * 1.25, 2),
                round(18 + (wave % 7) * 0.5, 2),
            ))
    conn.executemany(
        "INSERT INTO DAILY_ASSET_READINGS VALUES (?,?,?,?,?)", rows
    )
    conn.commit()
