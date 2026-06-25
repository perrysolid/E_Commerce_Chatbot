"""Load step: write the catalog into SQLite."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List

import pandas as pd

from etl.transform import UNIFIED_FIELDS

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "app" / "db.sqlite"

SCHEMA = """
CREATE TABLE product (
    product_link  TEXT,
    title         TEXT,
    brand         TEXT,
    category      TEXT,
    price         INTEGER,
    discount      REAL,
    avg_rating    REAL,
    total_ratings INTEGER
);
"""


def load(rows: List[Dict], db_path: Path = DB_PATH) -> int:
    df = pd.DataFrame(rows)[UNIFIED_FIELDS]
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        df.to_sql("product", conn, if_exists="append", index=False)
        conn.execute("CREATE INDEX idx_brand ON product(brand)")
        conn.execute("CREATE INDEX idx_category ON product(category)")
    return len(df)
