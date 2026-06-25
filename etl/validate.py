"""Validate step: drop rows that fail basic data-quality checks.

Returns the clean rows plus a small report. Raising early on garbage keeps bad
data out of the catalog (and out of the chatbot's answers).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

ALLOWED_CATEGORIES = {
    "mobiles", "laptops", "headphones", "smartwatches",
    "televisions", "tablets", "earbuds",
}


def is_valid(row: Dict) -> bool:
    if not row.get("product_link"):  # the upsert key must be present
        return False
    if not row.get("title"):
        return False
    if row.get("category") not in ALLOWED_CATEGORIES:
        return False
    if not isinstance(row.get("price"), int) or row["price"] <= 0:
        return False
    if not (0.0 <= float(row.get("avg_rating", 0)) <= 5.0):
        return False
    return True


def validate(rows: List[Dict]) -> Tuple[List[Dict], Dict]:
    valid = [r for r in rows if is_valid(r)]
    report = {"total": len(rows), "valid": len(valid), "dropped": len(rows) - len(valid)}
    if rows and report["valid"] / report["total"] < 0.5:
        raise ValueError(f"Too many invalid rows: {report}")
    return valid, report
