"""Pipeline orchestration — framework-agnostic.

Exposes the ETL stages as plain functions plus ``run_etl`` that chains them.
Airflow calls these same functions from its DAG, so the pipeline works
identically with or without Airflow (and stays unit-testable).

Usage:
    python -m etl.pipeline
"""
from __future__ import annotations

from typing import Dict, List

from etl import extractors, transform, validate
from etl.load import load


def extract() -> List[Dict]:
    return transform.normalize(extractors.extract_electronics())


def run_etl() -> Dict:
    rows = extract()
    clean, report = validate.validate(rows)
    n = load(clean)
    by_cat: Dict[str, int] = {}
    for r in clean:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    result = {"loaded": n, "by_category": by_cat, **report}
    print("ETL complete:", result)
    return result


if __name__ == "__main__":
    run_etl()
