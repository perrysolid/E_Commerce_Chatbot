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

COMMON_SCHEMA = """product_link - string (link to the product)
title - string (product name; model/series names like 'iPhone', 'Galaxy F36' live here)
brand - string (manufacturer, e.g. 'Apple', 'Samsung', 'boAt')
rank - integer (Flipkart relevance position; 1 = most relevant/popular)
price - integer (price in Indian Rupees)
discount - float (0.1 means 10 percent off)
avg_rating - float (0-5, higher is better)
total_ratings - integer (number of ratings)"""

# Spec columns exposed per category view (matches etl/load.py).
CATEGORY_SCHEMA = {
    "mobiles": """ram_gb - integer, RAM in GB (nullable)
storage_gb - integer, storage in GB (nullable)
network - string, '5G' or '4G' (nullable)
processor - string, chipset e.g. 'Snapdragon 695' (nullable)
color - string (nullable)""",
    "laptops": """processor - string, CPU e.g. 'Intel Core I5', 'Ryzen 5' (nullable)
ram_gb - integer, RAM in GB (nullable)
storage_gb - integer, storage in GB (nullable)
storage_type - string, 'SSD'/'HDD'/'EMMC' (nullable)
screen_inch - float, screen size in inches (nullable)
os - string, 'Windows'/'Chrome OS'/'macOS' (nullable)""",
    "tablets": """ram_gb - integer, RAM in GB (nullable)
storage_gb - integer, storage in GB (nullable)
screen_inch - float, screen size in inches (nullable)
network - string, '5G'/'4G'/'Wi-Fi' (nullable)
processor - string, chipset (nullable)
os - string (nullable)""",
    "televisions": """screen_inch - float, screen size in inches (nullable)
resolution - string, 'HD'/'Full HD'/'4K'/'8K' (nullable)
panel_type - string, 'LED'/'QLED'/'OLED' (nullable)""",
    "headphones": """battery_hours - integer, battery/playtime in hours (nullable)
form_factor - string, 'Over-Ear'/'On-Ear'/'In-Ear'/'TWS' (nullable)
connectivity - string, 'Bluetooth'/'Wired' (nullable)
anc - integer, 1 if noise cancellation else 0""",
    "earbuds": """battery_hours - integer, battery/playtime in hours (nullable)
form_factor - string, 'TWS'/'Neckband'/'In-Ear' (nullable)
connectivity - string, 'Bluetooth'/'Wired' (nullable)
anc - integer, 1 if noise cancellation else 0""",
    "smartwatches": """screen_inch - float, display size in inches (nullable)
has_calling - integer, 1 if Bluetooth calling else 0""",
}

# Full table used when no category is selected ("Just browsing").
BROWSE_SCHEMA = (
    COMMON_SCHEMA
    + "\ncategory - string, one of: mobiles, laptops, headphones, smartwatches, "
    "televisions, tablets, earbuds\n"
    + "\n".join(sorted({line for block in CATEGORY_SCHEMA.values()
                        for line in block.splitlines()}))
)

SQL_PROMPT_TEMPLATE = """You write SQLite SELECT queries for an electronics store.
<schema>
table: {table}
fields:
{schema}
</schema>
Rules:
- Query ONLY the table named '{table}'.
- Match brand case-insensitively with LIKE (e.g. brand LIKE '%samsung%'). Never use ILIKE.
- Model/series names (e.g. 'iPhone', 'Galaxy F36', 'Rockerz') live in the TITLE, not the
  brand: 'iPhone' -> title LIKE '%iphone%' (brand is 'Apple').
- For processor, match the KEY TOKEN with LIKE, not the whole phrase (values look like
  'Intel Core I5', 'Ryzen 5', 'Snapdragon 695'): 'i5' -> processor LIKE '%i5%';
  'Ryzen 5' -> processor LIKE '%ryzen 5%'; 'Snapdragon' -> processor LIKE '%snapdragon%'.
- Spec fields can be NULL; when filtering on a spec also require it IS NOT NULL.
- Ordering:
  - Default (no sort requested): ORDER BY rank ASC (most relevant first).
  - "best/top rated": total_ratings >= 50, ORDER BY avg_rating DESC, total_ratings DESC.
  - "most reviewed"/"popular": ORDER BY total_ratings DESC.
  - "cheapest": ORDER BY price ASC.  "biggest discount": ORDER BY discount DESC.
- Always SELECT * (all fields).
- If a value is ambiguous — e.g. a price 'under 2' with no unit (Rs 2 thousand? Rs 2 lakh?) —
  do NOT guess; return one short question wrapped in <CLARIFY></CLARIFY> and no SQL.
- Otherwise return ONLY the query, wrapped in <SQL></SQL> tags. Nothing else."""

RESULT_LIMIT = 8


def _prompt_for(category: Optional[str]) -> str:
    if category in CATEGORY_SCHEMA:
        schema = COMMON_SCHEMA + "\n" + CATEGORY_SCHEMA[category]
        return SQL_PROMPT_TEMPLATE.format(table=category, schema=schema)
    return SQL_PROMPT_TEMPLATE.format(table="product", schema=BROWSE_SCHEMA)


def generate_sql_query(question: str, category: Optional[str] = None,
                       error: Optional[str] = None) -> str:
    user = question
    if error:
        user = (
            f"{question}\n\nYour previous query failed with this error:\n{error}\n"
            "Return a corrected query."
        )
    return chat(
        messages=[
            {"role": "system", "content": _prompt_for(category)},
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


def _variant_key(title: str, price: int):
    """Same model in a different colour shares this key (parenthetical stripped)."""
    base = re.sub(r"\s*\([^)]*\)", "", str(title)).strip().lower()
    return base, price


def format_products(df: pd.DataFrame, limit: int = RESULT_LIMIT) -> str:
    """Render results straight from the rows — no LLM touches the numbers, so every
    price/rating/discount shown matches the database. Colour variants of the same
    model (same name + price) are collapsed into one entry, order preserved."""
    groups: dict = {}
    order = []
    for row in df.itertuples(index=False):
        key = _variant_key(row.title, int(row.price))
        if key not in groups:
            groups[key] = 0
            order.append((key, row))
        groups[key] += 1

    distinct = len(order)
    head = "Here's what I found:" if distinct <= limit else f"Found {distinct} products. Top {limit}:"
    lines = [head]
    for i, (key, row) in enumerate(order[:limit], 1):
        price = f"₹{int(row.price):,}"
        discount = f" ({round(row.discount * 100)}% off)" if getattr(row, "discount", 0) else ""
        rating = (f"{row.avg_rating}★ ({int(row.total_ratings):,} ratings)"
                  if getattr(row, "avg_rating", 0) else "no ratings yet")
        colours = f" · {groups[key]} colours" if groups[key] > 1 else ""
        lines.append(f"{i}. {row.title} — {price}{discount}, {rating}{colours}\n   {row.product_link}")
    return "\n".join(lines)


def sql_chain(question: str, history: Optional[str] = None,
              category: Optional[str] = None) -> str:
    q = question if not history else f"{history}\nLatest question: {question}"

    df = None
    error = None
    # Self-correction loop: try once, then retry with the error fed back.
    for attempt in range(SQL_MAX_RETRIES + 1):
        raw = generate_sql_query(q, category=category, error=error)
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
