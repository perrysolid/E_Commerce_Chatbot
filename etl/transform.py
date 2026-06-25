"""Transform step: clean the raw scrape into the final catalog schema.

Schema (one row per product):
    product_link, title, brand, category, price (INR),
    discount (0-1 float), avg_rating (0-5), total_ratings (int)

The scraper already pulls structured fields, so transform focuses on deriving
the brand, coercing types and dropping obviously broken rows.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

UNIFIED_FIELDS = [
    "product_link", "title", "brand", "category",
    "price", "discount", "avg_rating", "total_ratings",
]


def _to_int(value) -> int:
    match = re.search(r"\d+", str(value).replace(",", ""))
    return int(match.group()) if match else 0


def _brand_from_title(title: str) -> Optional[str]:
    words = str(title).split()
    return words[0] if words else None


def normalize(raw: List[Dict]) -> List[Dict]:
    out = []
    for r in raw:
        title = str(r.get("title", "")).strip()
        out.append({
            "product_link": r.get("product_link"),
            "title": title,
            "brand": _brand_from_title(title),
            "category": r.get("category"),
            "price": _to_int(r.get("price", 0)),
            "discount": float(r.get("discount") or 0.0),
            "avg_rating": float(r.get("avg_rating") or 0.0),
            "total_ratings": _to_int(r.get("total_ratings", 0)),
        })
    return out
