"""Extract step: load the raw Flipkart electronics snapshot.

The live web scrape lives in ``etl/scrape.py`` and writes the CSV snapshot this
module reads. Keeping the read here (pandas only) means the pipeline, the app and
CI never import the scraping libraries — only ``etl/scrape.py`` does.
Re-run ``python -m etl.scrape`` to refresh the snapshot.

Amazon was intentionally avoided: it blocks automated access and cannot anchor a
reproducible pipeline. Flipkart serves full HTML and reflects the Indian market.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "flipkart_electronics_raw.csv"


def extract_electronics(path: Path = RAW_CSV) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python -m etl.scrape` to create the snapshot."
        )
    return pd.read_csv(path).to_dict(orient="records")


if __name__ == "__main__":
    print("electronics rows:", len(extract_electronics()))
