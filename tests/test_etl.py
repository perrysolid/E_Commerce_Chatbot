"""Unit tests for the ETL transform + validate stages (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3  # noqa: E402

from etl import load, transform, validate  # noqa: E402


def _raw(**kw):
    base = {"product_link": "http://x", "title": "Samsung Galaxy M14",
            "category": "mobiles", "price": 12999, "discount": 0.3,
            "avg_rating": 4.2, "total_ratings": 100}
    base.update(kw)
    return base


def test_normalize_derives_brand_and_types():
    out = transform.normalize([_raw()])
    row = out[0]
    assert row["brand"] == "Samsung"
    assert row["category"] == "mobiles"
    assert isinstance(row["price"], int)
    assert set(row) == set(transform.UNIFIED_FIELDS)


def test_normalize_extracts_specs_from_title():
    mobile = transform.normalize([_raw(
        title="realme P4R 5G (8 GB RAM, 128 GB) Snapdragon 695")])[0]
    assert mobile["ram_gb"] == 8
    assert mobile["storage_gb"] == 128
    assert mobile["network"] == "5G"
    assert "Snapdragon" in (mobile["processor"] or "")

    tv = transform.normalize([_raw(
        category="televisions", title="Foxsky 109 cm (43 inch) Full HD LED Smart TV")])[0]
    assert tv["screen_inch"] == 43.0
    assert tv["resolution"] == "Full HD"

    laptop = transform.normalize([_raw(
        category="laptops", title="HP Intel Core i5 (16 GB/512 GB SSD) 15.6 inch")])[0]
    assert laptop["ram_gb"] == 16 and laptop["storage_gb"] == 512
    assert laptop["screen_inch"] == 15.6


def test_validate_drops_bad_rows():
    rows = transform.normalize([
        _raw(), _raw(), _raw(), _raw(),  # 4 valid (keep majority valid)
        _raw(price=0),                   # invalid price
        _raw(category="books"),          # not an allowed category
        _raw(title=""),                  # empty title
    ])
    clean, report = validate.validate(rows)
    assert report["valid"] == 4
    assert report["dropped"] == 3


def test_validate_raises_when_mostly_invalid():
    import pytest
    rows = transform.normalize([_raw(), _raw(price=0), _raw(price=0)])
    with pytest.raises(ValueError):
        validate.validate(rows)


def test_load_is_idempotent_upsert(tmp_path):
    db = tmp_path / "t.sqlite"
    rows = transform.normalize([_raw(product_link="http://a"), _raw(product_link="http://b")])

    load.load(rows, db_path=db)
    load.load(rows, db_path=db)  # second run must not duplicate

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM product").fetchone()[0] == 2

        # A changed price upserts in place (no new row).
        updated = transform.normalize([_raw(product_link="http://a", price=999)])
        load.load(updated, db_path=db)
        assert conn.execute("SELECT COUNT(*) FROM product").fetchone()[0] == 2
        assert conn.execute(
            "SELECT price FROM product WHERE product_link='http://a'"
        ).fetchone()[0] == 999
