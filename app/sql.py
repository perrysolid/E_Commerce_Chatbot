"""SQL intent: NL question -> SQL -> rows -> grounded natural-language answer.

Hallucination guardrails added on top of the original chain:
  * SELECT-only validation (no writes ever reach the DB).
  * Self-correction: a failing query is retried once with the error fed back.
  * Empty results return a definite "no products found" message instead of
    letting the LLM invent products.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Optional

import pandas as pd
from config import DB_PATH, SQL_MAX_RETRIES
from llm import chat

SQL_PROMPT = """You are an expert at writing SQLite queries for an electronics store product table.
The schema is provided in the schema tags.
<schema>
table: product
fields:
product_link - string (hyperlink to product)
title - string (name of the product)
brand - string (brand of the product)
category - string, one of:
  mobiles, laptops, headphones, smartwatches, televisions, tablets, earbuds
price - integer (price in Indian Rupees)
discount - float (0.1 means 10 percent off, 0.2 means 20 percent off)
avg_rating - float (0-5, higher is better)
total_ratings - integer (number of ratings)
</schema>
Rules:
- Match brand case-insensitively using LIKE (e.g. brand LIKE '%samsung%'). Never use ILIKE.
- Use the category column for product types (e.g. category = 'laptops').
- Always SELECT * (all fields).
- Return ONLY the query, wrapped in <SQL></SQL> tags. Nothing else."""

RESULT_LIMIT = 8


def generate_sql_query(question: str, error: Optional[str] = None) -> str:
    user = question
    if error:
        user = (
            f"{question}\n\nYour previous query failed with this error:\n{error}\n"
            "Return a corrected query."
        )
    return chat(
        messages=[
            {"role": "system", "content": SQL_PROMPT},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )


def _extract_sql(text: str) -> Optional[str]:
    matches = re.findall(r"<SQL>(.*?)</SQL>", text, re.DOTALL)
    return matches[0].strip() if matches else None


def run_query(query: str) -> pd.DataFrame:
    """Execute a read-only query. Raises on non-SELECT or SQL errors."""
    if not query.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn)


def format_products(df: pd.DataFrame, limit: int = RESULT_LIMIT) -> str:
    """Render results straight from the rows — no LLM touches the numbers, so
    every price/rating/discount shown is guaranteed to match the database."""
    total = len(df)
    head = "Here's what I found:" if total <= limit else f"Found {total} products. Top {limit}:"
    lines = [head]
    for i, row in enumerate(df.head(limit).itertuples(index=False), 1):
        price = f"₹{int(row.price):,}"
        discount = f" ({round(row.discount * 100)}% off)" if getattr(row, "discount", 0) else ""
        rating = (f"{row.avg_rating}★ ({int(row.total_ratings):,} ratings)"
                  if getattr(row, "avg_rating", 0) else "no ratings yet")
        lines.append(f"{i}. {row.title} — {price}{discount}, {rating}\n   {row.product_link}")
    return "\n".join(lines)


def sql_chain(question: str, history: Optional[str] = None) -> str:
    q = question if not history else f"{history}\nLatest question: {question}"

    df = None
    error = None
    # Self-correction loop: try once, then retry with the error fed back.
    for attempt in range(SQL_MAX_RETRIES + 1):
        raw = generate_sql_query(q, error=error)
        sql = _extract_sql(raw)
        if not sql:
            return "Sorry, I couldn't turn that into a product query. Try rephrasing?"
        try:
            df = run_query(sql)
            break
        except Exception as e:  # noqa: BLE001 - feed any DB error back to the model
            error = str(e)
            df = None

    if df is None:
        return "Sorry, I had trouble querying the catalog. Please try rephrasing."

    if df.empty:
        return "I couldn't find any products matching that. Try widening your search."

    return format_products(df)


if __name__ == "__main__":
    print(sql_chain("Show top 3 laptops in descending order of rating"))
    print(sql_chain("Show me phones under 1 rupee"))  # should report none found
