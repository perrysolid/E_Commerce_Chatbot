"""Scrape Indian electronics listings from Flipkart into a raw CSV snapshot.

This is the live "extract from the web" step. Because live scraping is slow and
can be rate-limited, the result is snapshotted to a CSV that the rest of the
pipeline (and CI) reads — so the ETL stays reproducible while this script can be
re-run to refresh the data.

Usage:
    python -m etl.scrape --pages 20
"""
from __future__ import annotations

import argparse
import re
import time
from typing import Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from etl.extractors import RAW_CSV

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120 Safari/537.36"),
    "Accept-Language": "en-IN,en;q=0.9",
}

# 7 electronics categories relevant to the Indian market -> Flipkart search query.
CATEGORIES = {
    "mobiles": "mobiles",
    "laptops": "laptops",
    "headphones": "headphones",
    "smartwatches": "smart watches",
    "televisions": "smart tv",
    "tablets": "tablets",
    "earbuds": "wireless earbuds",
}

# The generic category search is dominated by cheap listings, so premium/flagship
# brands (Apple, Sony, Samsung, ...) never appear. These targeted searches pull a
# few pages each so genuine branded products land in the catalog too.
BRAND_QUERIES = {
    "mobiles": ["apple iphone", "samsung galaxy mobile", "oneplus",
                "google pixel", "nothing phone"],
    "laptops": ["apple macbook", "dell laptop", "hp laptop", "lenovo laptop", "asus laptop"],
    "tablets": ["apple ipad", "samsung galaxy tab", "oneplus pad"],
    "televisions": ["sony tv", "samsung tv", "lg tv"],
    "headphones": ["sony headphones", "bose headphones", "jbl headphones"],
    "earbuds": ["apple airpods", "samsung galaxy buds", "sony earbuds", "nothing ear"],
    "smartwatches": ["apple watch", "samsung galaxy watch", "noise smartwatch"],
}
BRAND_PAGES = 3

TITLE_SELECTORS = ["div.KzDlHZ", "div.RG5Slk", "a.wjcEIp", "a.s1Q9rs", "div._4rR01T"]


def _title_from_slug(href: str) -> str:
    slug = href.split("/p/")[0].strip("/").split("/")[-1]
    return slug.replace("-", " ").title()


def _parse_card(card) -> Optional[Dict]:
    anchor = card.find("a", href=re.compile("/p/"))
    if not anchor:
        return None
    link = "https://www.flipkart.com" + anchor["href"].split("?")[0]

    title = None
    for sel in TITLE_SELECTORS:
        el = card.select_one(sel)
        if el and el.get_text(strip=True):
            title = el.get_text(strip=True)
            break
    if not title:
        img = card.find("img")
        title = (img.get("alt") if img else "") or _title_from_slug(anchor["href"])
    title = title.strip()
    if not title:
        return None

    # Price: read the dedicated selling-price element (avoids promo/EMI amounts).
    price_el = card.select_one("div.hZ3P6w")
    price_text = price_el.get_text() if price_el else card.get_text(" ", strip=True)
    price_m = re.search(r"₹([\d,]+)", price_text)
    if not price_m:
        return None
    price = int(price_m.group(1).replace(",", ""))

    # Discount comes straight from the "NN% off" label.
    disc_m = re.search(r"(\d+)%\s*off", card.get_text(" ", strip=True))
    discount = round(int(disc_m.group(1)) / 100, 2) if disc_m else 0.0

    # Rating + count: parse the ratings widget, not the title (which contains
    # spec numbers like "Bluetooth 5.3" that look like ratings).
    avg_rating, total_ratings = 0.0, 0
    rating_el = card.select_one("div.a7saXW, span.a7saXW")
    if rating_el:
        rtext = rating_el.get_text(" ", strip=True)
        rm = re.match(r"\s*([0-5](?:\.\d)?)", rtext)
        if rm:
            avg_rating = float(rm.group(1))
            rest = rtext[rm.end():]
            cm = re.search(r"([\d,]+)\s*Ratings", rest) or re.search(r"\(([\d,]+)\)", rest)
            if cm:
                total_ratings = int(cm.group(1).replace(",", ""))

    return {
        "product_link": link,
        "title": title,
        "category": None,  # filled by caller
        "price": price,
        "discount": discount,
        "avg_rating": avg_rating,
        "total_ratings": total_ratings,
    }


def _collect(query: str, pages: int, category: str, position: int,
             seen: set, rows: List[Dict], delay: float) -> int:
    """Scrape ``pages`` of a Flipkart search into ``rows``; return the new position."""
    for page in range(1, pages + 1):
        url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}&page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  {category} [{query}] p{page}: request failed ({e}); skipping")
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        new = 0
        for card in soup.select("div[data-id]"):
            rec = _parse_card(card)
            if not rec or rec["product_link"] in seen:
                continue
            seen.add(rec["product_link"])
            position += 1
            rec["category"] = category
            rec["rank"] = position
            rows.append(rec)
            new += 1
        print(f"  {category} [{query}] p{page}: +{new} (total {len(rows)})")
        time.sleep(delay)
        if new == 0 and page > 1:
            break  # exhausted (Flipkart returns no new results)
    return position


def scrape(pages: int = 20, delay: float = 1.0, min_rows: int = 0) -> pd.DataFrame:
    seen = set()
    rows: List[Dict] = []
    for category, query in CATEGORIES.items():
        position = 0  # Flipkart relevance order within a category (page 1 first)
        position = _collect(query, pages, category, position, seen, rows, delay)
        # Brand-boost: pull a few pages of flagship-brand searches into this category.
        for brand_query in BRAND_QUERIES.get(category, []):
            position = _collect(brand_query, BRAND_PAGES, category, position, seen, rows, delay)
    df = pd.DataFrame(rows)
    # Safety guard: if the scrape was blocked/throttled and returned too little,
    # keep the last good snapshot instead of merging in garbage.
    if min_rows and len(df) < min_rows:
        print(f"Only {len(df)} rows (< {min_rows}); keeping existing snapshot.")
        return df
    df = _upsert_snapshot(df)
    print(f"Snapshot now has {len(df)} products at {RAW_CSV}")
    return df


def _upsert_snapshot(new_df: pd.DataFrame) -> pd.DataFrame:
    """Idempotent upsert into the CSV snapshot, keyed on product_link.

    Re-scraped items update in place (fresh price/rating), genuinely new items
    are added, and unchanged data produces an identical file (no spurious diff),
    so a daily commit only happens when something actually changed.
    """
    if RAW_CSV.exists():
        old = pd.read_csv(RAW_CSV)
        new_df = pd.concat([new_df, old]).drop_duplicates(subset="product_link", keep="first")
    new_df = new_df.sort_values(["category", "product_link"]).reset_index(drop=True)
    RAW_CSV.parent.mkdir(exist_ok=True)
    new_df.to_csv(RAW_CSV, index=False)
    return new_df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=20)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--min-rows", type=int, default=0, dest="min_rows")
    scrape(**vars(ap.parse_args()))
