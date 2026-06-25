"""Unit tests for the SQL guardrails (no LLM calls)."""
import re

import pandas as pd
import pytest
import sql


def test_format_products_prices_match_data_exactly():
    df = pd.DataFrame([
        {"title": "Phone A", "price": 19999, "discount": 0.25, "avg_rating": 4.3,
         "total_ratings": 1200, "product_link": "http://x/a"},
        {"title": "Phone B", "price": 8499, "discount": 0.0, "avg_rating": 0.0,
         "total_ratings": 0, "product_link": "http://x/b"},
    ])
    out = sql.format_products(df)
    # Exact prices from the data appear; the LLM never touches these numbers.
    assert "₹19,999" in out and "₹8,499" in out
    assert "http://x/a" in out and "http://x/b" in out
    # Every rupee figure in the output must come from the dataframe (no invented prices).
    shown = {int(n.replace(",", "")) for n in re.findall(r"₹([\d,]+)", out)}
    assert shown == {19999, 8499}


def test_extract_sql_found():
    raw = "Here you go <SQL>SELECT * FROM product LIMIT 1;</SQL> done"
    assert sql._extract_sql(raw) == "SELECT * FROM product LIMIT 1;"


def test_extract_sql_missing():
    assert sql._extract_sql("no tags here") is None


def test_run_query_rejects_non_select():
    with pytest.raises(ValueError):
        sql.run_query("DELETE FROM product")


def test_run_query_returns_rows():
    df = sql.run_query("SELECT * FROM product LIMIT 5")
    assert len(df) == 5
    assert "brand" in df.columns


def test_run_query_empty_result():
    df = sql.run_query("SELECT * FROM product WHERE price < 0")
    assert df.empty
