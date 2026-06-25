"""Load step: idempotent upsert of the catalog into SQLite.

``product_link`` is the natural key, so re-running the pipeline updates existing
products (price/rating refresh) and inserts new ones without creating duplicates
— running it twice on the same data is a no-op.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List

from etl.transform import UNIFIED_FIELDS

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "app" / "db.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS product (
    product_link  TEXT PRIMARY KEY,
    title         TEXT,
    brand         TEXT,
    category      TEXT,
    rank          INTEGER,
    price         INTEGER,
    discount      REAL,
    avg_rating    REAL,
    total_ratings INTEGER,
    ram_gb        INTEGER,
    storage_gb    INTEGER,
    screen_inch   REAL,
    network       TEXT,
    processor     TEXT,
    resolution    TEXT,
    battery_hours INTEGER
);
CREATE INDEX IF NOT EXISTS idx_brand ON product(brand);
CREATE INDEX IF NOT EXISTS idx_category ON product(category);
"""


def load(rows: List[Dict], db_path: Path = DB_PATH) -> int:
    cols = UNIFIED_FIELDS
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "product_link")
    upsert = (
        f"INSERT INTO product ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(product_link) DO UPDATE SET {updates}"
    )
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.executemany(upsert, [tuple(r[c] for c in cols) for r in rows])
    return len(rows)
