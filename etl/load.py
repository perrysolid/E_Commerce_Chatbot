"""Load step: idempotent upsert into one SQLite table, plus a clean per-category
view.

``product_link`` is the natural key, so re-running the pipeline updates existing
products and inserts new ones without duplicates. After loading, a VIEW is created
per category exposing only the columns relevant to that category — the chatbot
queries these views so it never sees irrelevant spec columns.
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
    storage_type  TEXT,
    screen_inch   REAL,
    network       TEXT,
    processor     TEXT,
    os            TEXT,
    color         TEXT,
    resolution    TEXT,
    panel_type    TEXT,
    form_factor   TEXT,
    connectivity  TEXT,
    anc           INTEGER,
    battery_hours INTEGER,
    has_calling   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_brand ON product(brand);
CREATE INDEX IF NOT EXISTS idx_category ON product(category);
"""

# Columns every category view exposes.
BASE_VIEW_COLS = [
    "product_link", "title", "brand", "rank",
    "price", "discount", "avg_rating", "total_ratings",
]
# Category-specific spec columns layered on top.
CATEGORY_EXTRA = {
    "mobiles": ["ram_gb", "storage_gb", "network", "processor", "color"],
    "laptops": ["processor", "ram_gb", "storage_gb", "storage_type", "screen_inch", "os"],
    "tablets": ["ram_gb", "storage_gb", "screen_inch", "network", "processor", "os"],
    "televisions": ["screen_inch", "resolution", "panel_type"],
    "headphones": ["battery_hours", "form_factor", "connectivity", "anc"],
    "earbuds": ["battery_hours", "form_factor", "connectivity", "anc"],
    "smartwatches": ["screen_inch", "has_calling"],
}


def _create_views(conn: sqlite3.Connection) -> None:
    for category, extra in CATEGORY_EXTRA.items():
        cols = ", ".join(BASE_VIEW_COLS + extra)
        conn.execute(f"DROP VIEW IF EXISTS {category}")
        conn.execute(
            f"CREATE VIEW {category} AS SELECT {cols} FROM product "
            f"WHERE category = '{category}'"
        )


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
        _create_views(conn)
    return len(rows)
