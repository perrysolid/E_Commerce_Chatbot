"""Transform step: clean the raw scrape into the final catalog schema.

Besides typing and brand derivation, this step parses structured specs out of the
product title (which Flipkart packs full of detail), so users can filter by RAM,
storage, screen size, network, processor, resolution and battery — without having
to scrape every product page.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

UNIFIED_FIELDS = [
    "product_link", "title", "brand", "category", "rank",
    "price", "discount", "avg_rating", "total_ratings",
    "ram_gb", "storage_gb", "screen_inch", "network",
    "processor", "resolution", "battery_hours",
]

PROCESSOR_RE = re.compile(
    r"(snapdragon\s*\w*|mediatek\s*\w*|dimensity\s*\d+|helio\s*\w+|exynos\s*\d+|"
    r"unisoc\s*\w*|intel\s+core\s+i\d|intel\s+celeron\s*\w*|pentium|ryzen\s*\d|"
    r"apple\s+a\d+)",
    re.I,
)
RESOLUTIONS = ["8K", "4K", "Ultra HD", "QLED", "OLED", "Full HD", "HD Ready", "HD"]


def _to_int(value) -> int:
    match = re.search(r"\d+", str(value).replace(",", ""))
    return int(match.group()) if match else 0


def _brand_from_title(title: str) -> Optional[str]:
    words = str(title).split()
    return words[0] if words else None


def _storage_gb(title: str) -> Optional[int]:
    tb = re.search(r"(\d+(?:\.\d+)?)\s*TB", title, re.I)
    if tb:
        return int(float(tb.group(1)) * 1024)
    pair = re.search(r"\d+\s*GB\s*/\s*(\d+)\s*GB", title, re.I)  # e.g. 8 GB/256 GB
    if pair:
        return int(pair.group(1))
    rom = re.search(r"(\d+)\s*GB\s*(?:ROM|SSD|EMMC|HDD|UFS|Storage)", title, re.I)
    if rom:
        return int(rom.group(1))
    bare = re.findall(r"(\d+)\s*GB(?!\s*RAM)", title, re.I)  # e.g. "(Black, 128 GB)"
    return int(bare[-1]) if bare else None


def _ram_gb(title: str) -> Optional[int]:
    pair = re.search(r"(\d+)\s*GB\s*/\s*\d+\s*GB", title, re.I)
    if pair:
        return int(pair.group(1))
    ram = re.search(r"(\d+)\s*GB\s*RAM", title, re.I)
    return int(ram.group(1)) if ram else None


def _screen_inch(title: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*inch", title, re.I) or re.search(r"(\d+(?:\.\d+)?)\"", title)
    if not m:
        return None
    value = float(m.group(1))
    return value if 1.0 <= value <= 120.0 else None


def _network(title: str) -> Optional[str]:
    if re.search(r"\b5G\b", title, re.I):
        return "5G"
    if re.search(r"\b4G\b|\bLTE\b", title, re.I):
        return "4G"
    return None


def _processor(title: str) -> Optional[str]:
    m = PROCESSOR_RE.search(title)
    return re.sub(r"\s+", " ", m.group(1)).strip().title() if m else None


def _resolution(title: str) -> Optional[str]:
    for res in RESOLUTIONS:
        if res.lower() in title.lower():
            return res
    return None


def _battery_hours(title: str) -> Optional[int]:
    m = (re.search(r"(\d+)\s*H(?:rs|ours)?\s*(?:Battery|Playback|Playtime)", title, re.I)
         or re.search(r"(?:Upto\s*)?(\d+)\s*Hours?\s*Play", title, re.I))
    return int(m.group(1)) if m else None


def normalize(raw: List[Dict]) -> List[Dict]:
    out = []
    for r in raw:
        title = str(r.get("title", "")).strip()
        out.append({
            "product_link": r.get("product_link"),
            "title": title,
            "brand": _brand_from_title(title),
            "category": r.get("category"),
            "rank": _to_int(r.get("rank", 0)) or None,
            "price": _to_int(r.get("price", 0)),
            "discount": float(r.get("discount") or 0.0),
            "avg_rating": float(r.get("avg_rating") or 0.0),
            "total_ratings": _to_int(r.get("total_ratings", 0)),
            "ram_gb": _ram_gb(title),
            "storage_gb": _storage_gb(title),
            "screen_inch": _screen_inch(title),
            "network": _network(title),
            "processor": _processor(title),
            "resolution": _resolution(title),
            "battery_hours": _battery_hours(title),
        })
    return out
