"""Unit tests for the SQL guardrails (no LLM calls)."""
import pytest
import sql


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
