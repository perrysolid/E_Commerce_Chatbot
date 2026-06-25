"""Smoke test: every module imports and the DB is queryable end-to-end
without an API key."""
import importlib


def test_modules_import():
    for name in ["config", "llm", "router", "sql", "faq", "smalltalk", "memory"]:
        importlib.import_module(name)


def test_db_exists_and_has_products():
    import sql
    df = sql.run_query("SELECT COUNT(*) AS n FROM product")
    assert df.iloc[0]["n"] > 0
