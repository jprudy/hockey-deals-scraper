from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List

ScrapedRow = Dict[str, str]
ScraperRunner = Callable[[str, Path, Path], tuple[List[ScrapedRow], Dict[str, str]]]

# Standardized scraper contract used by run_all.py.
REQUIRED_SCRAPER_FIELDS = [
    "product_name",
    "price",
    "original_price",
    "url",
    "image_url",
    "brand",
    "category",
    "subcategory",
    "size",
    "in_stock",
    "source",
]


@dataclass(frozen=True)
class ScraperDefinition:
    name: str
    run: ScraperRunner
