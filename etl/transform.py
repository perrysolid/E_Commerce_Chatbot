"""Transform step: clean the raw scrape into the final catalog schema.

Besides typing and brand derivation, this step parses structured specs out of the
product title (which Flipkart packs with detail), so users can filter by RAM,
storage, processor, screen, network, OS, resolution, battery and more — without
scraping every product page.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

UNIFIED_FIELDS = [
    "product_link", "title", "brand", "category", "rank",
    "price", "discount", "avg_rating", "total_ratings",
    # specs (nullable, parsed from the title)
    "ram_gb", "storage_gb", "storage_type", "screen_inch", "network",
    "processor", "os", "color", "resolution", "panel_type",
    "form_factor", "connectivity", "anc", "battery_hours", "has_calling",
]

PROCESSOR_RE = re.compile(
    r"(snapdragon\s*\w*|mediatek\s*\w*|dimensity\s*\d+|helio\s*\w+|exynos\s*\d+|"
    r"unisoc\s*\w*|intel\s+core\s+i\d|intel\s+celeron\s*\w*|pentium|ryzen\s*\d|"
    r"apple\s+a\d+)",
    re.I,
)
RESOLUTIONS = ["8K", "4K", "Ultra HD", "Full HD", "HD Ready", "HD"]
PANELS = ["QLED", "OLED", "Nano", "LED"]


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
    pair = re.search(r"\d+\s*GB\s*/\s*(\d+)\s*GB", title, re.I)
    if pair:
        return int(pair.group(1))
    rom = re.search(r"(\d+)\s*GB\s*(?:ROM|SSD|EMMC|HDD|UFS|Storage)", title, re.I)
    if rom:
        return int(rom.group(1))
    bare = re.findall(r"(\d+)\s*GB(?!\s*RAM)", title, re.I)
    return int(bare[-1]) if bare else None


def _ram_gb(title: str) -> Optional[int]:
    pair = re.search(r"(\d+)\s*GB\s*/\s*\d+\s*GB", title, re.I)
    if pair:
        return int(pair.group(1))
    ram = re.search(r"(\d+)\s*GB\s*RAM", title, re.I)
    return int(ram.group(1)) if ram else None


def _storage_type(title: str) -> Optional[str]:
    for kind in ("SSD", "HDD", "EMMC", "UFS"):
        if re.search(rf"\b{kind}\b", title, re.I):
            return kind
    return None


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
    if re.search(r"Wi-?Fi", title, re.I):
        return "Wi-Fi"
    return None


def _processor(title: str) -> Optional[str]:
    m = PROCESSOR_RE.search(title)
    return re.sub(r"\s+", " ", m.group(1)).strip().title() if m else None


def _os(title: str) -> Optional[str]:
    for pat, name in (
        (r"windows", "Windows"), (r"chrome\s*os", "Chrome OS"), (r"mac\s*os|macos", "macOS"),
        (r"\bios\b", "iOS"), (r"android", "Android"),
    ):
        if re.search(pat, title, re.I):
            return name
    return None


def _color(title: str) -> Optional[str]:
    # Mobiles use "(Color, 128 GB)"; take the first parenthetical, letters only.
    m = re.search(r"\(([A-Za-z][A-Za-z\s]+?)\s*[,)]", title)
    if not m:
        return None
    color = m.group(1).strip()
    return color if "inch" not in color.lower() and len(color) <= 25 else None


def _resolution(title: str) -> Optional[str]:
    for res in RESOLUTIONS:
        if res.lower() in title.lower():
            return res
    return None


def _panel_type(title: str) -> Optional[str]:
    for panel in PANELS:
        if re.search(rf"\b{panel}\b", title, re.I):
            return panel.upper() if panel != "Nano" else "Nano"
    return None


def _form_factor(title: str) -> Optional[str]:
    t = title.lower()
    if "neckband" in t:
        return "Neckband"
    if "tws" in t or "true wireless" in t or "airdopes" in t or "buds" in t:
        return "TWS"
    if "over ear" in t or "over-ear" in t:
        return "Over-Ear"
    if "on ear" in t or "on-ear" in t:
        return "On-Ear"
    if "in ear" in t or "in-ear" in t:
        return "In-Ear"
    return None


def _connectivity(title: str) -> Optional[str]:
    t = title.lower()
    if "bluetooth" in t or "wireless" in t or "tws" in t:
        return "Bluetooth"
    if "wired" in t:
        return "Wired"
    return None


def _anc(title: str) -> Optional[int]:
    return 1 if re.search(r"\bANC\b|\bENC\b|noise cancel", title, re.I) else 0


def _battery_hours(title: str) -> Optional[int]:
    m = (re.search(r"(\d+)\s*H(?:rs|ours)?\s*(?:Battery|Playback|Playtime)", title, re.I)
         or re.search(r"(?:Upto\s*)?(\d+)\s*Hours?\s*Play", title, re.I))
    return int(m.group(1)) if m else None


def _has_calling(title: str) -> Optional[int]:
    return 1 if re.search(r"calling", title, re.I) else 0


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
            "storage_type": _storage_type(title),
            "screen_inch": _screen_inch(title),
            "network": _network(title),
            "processor": _processor(title),
            "os": _os(title),
            "color": _color(title),
            "resolution": _resolution(title),
            "panel_type": _panel_type(title),
            "form_factor": _form_factor(title),
            "connectivity": _connectivity(title),
            "anc": _anc(title),
            "battery_hours": _battery_hours(title),
            "has_calling": _has_calling(title),
        })
    return out
