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
rank - integer (Flipkart relevance position within a category; 1 = most relevant/popular)
price - integer (price in Indian Rupees)
discount - float (0.1 means 10 percent off, 0.2 means 20 percent off)
avg_rating - float (0-5, higher is better)
total_ratings - integer (number of ratings)
ram_gb - integer, RAM in GB (nullable)
storage_gb - integer, storage in GB (nullable)
screen_inch - float, screen size in inches (nullable)
network - string, '5G' or '4G' (nullable)
processor - string, chipset/CPU e.g. 'Snapdragon 695', 'Intel Core I5' (nullable)
resolution - string, display quality e.g. 'Full HD', '4K', 'QLED' (nullable, mostly TVs)
battery_hours - integer, battery or playtime in hours (nullable, mostly audio)
</schema>
Rules:
- Match brand case-insensitively using LIKE (e.g. brand LIKE '%samsung%'). Never use ILIKE.
- The brand is the manufacturer (e.g. 'Apple', 'Samsung', 'boAt'). Product lines and
  model names (e.g. 'iPhone', 'Galaxy F36', 'Redmi Note', 'Rockerz') live in the TITLE,
  not the brand. Match those with title LIKE — e.g. 'iPhone' -> title LIKE '%iphone%'
  (its brand is 'Apple'), 'Galaxy F36' -> title LIKE '%galaxy%' AND title LIKE '%f36%'.
- Use the category column for product types (e.g. category = 'laptops').
- Spec fields (ram_gb, storage_gb, screen_inch, network, processor, ...) can be NULL.
  When filtering on a spec, also require it IS NOT NULL.
- Ordering matters for quality:
  - Default (no sort asked for): ORDER BY rank ASC — Flipkart's most relevant first.
  - "best rated" / "top rated": only credible items, total_ratings >= 50,
    ORDER BY avg_rating DESC, total_ratings DESC.
  - "most popular" / "most reviewed": ORDER BY total_ratings DESC.
  - "cheapest": ORDER BY price ASC. "biggest discount": ORDER BY discount DESC.
- Always SELECT * (all fields).
- If a needed value is ambiguous — e.g. a price like 'under 2' with no unit
  (does it mean Rs 2 thousand or Rs 2 lakh?) — do NOT guess. Instead return one short
  clarifying question wrapped in <CLARIFY></CLARIFY> tags and no SQL.
- Otherwise return ONLY the query, wrapped in <SQL></SQL> tags. Nothing else."""

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


def _extract_clarify(text: str) -> Optional[str]:
    matches = re.findall(r"<CLARIFY>(.*?)</CLARIFY>", text, re.DOTALL)
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
        clarify = _extract_clarify(raw)
        if clarify:  # ambiguous request -> ask instead of guessing
            return clarify
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
