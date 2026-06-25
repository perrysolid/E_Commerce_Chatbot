"""Reproducible database build: CSV -> clean SQLite.

Replaces the ad-hoc notebook step. Rebuilds app/db.sqlite from the product
CSV with a tidy schema (no stray pandas index) and a ``category`` column so
the catalog can grow beyond shoes without a schema change.

Usage:
    python data/build_db.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "app" / "resources" / "ecommerce_data_final.csv"
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


def build(csv_path: Path = CSV_PATH, db_path: Path = DB_PATH, category: str = "shoes") -> int:
    df = pd.read_csv(csv_path)
    if "category" not in df.columns:
        df["category"] = category
    df = df[["product_link", "title", "brand", "category",
             "price", "discount", "avg_rating", "total_ratings"]]

    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        df.to_sql("product", conn, if_exists="append", index=False)
        conn.execute("CREATE INDEX idx_brand ON product(brand)")
        conn.execute("CREATE INDEX idx_category ON product(category)")
    print(f"Built {db_path} with {len(df)} products.")
    return len(df)


if __name__ == "__main__":
    build()
