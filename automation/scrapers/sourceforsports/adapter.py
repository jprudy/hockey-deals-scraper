from __future__ import annotations

import csv
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]
SOURCE_KEY = "sourceforsports"


def _run_subprocess(command: List[str], env: Dict[str, str], log_path: Path) -> int:
    with log_path.open("w", encoding="utf-8") as log_handle:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            shell=False,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return completed.returncode


def _clean_bool(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "y", "in stock"}:
        return "true"
    if text in {"false", "0", "no", "n", "out of stock", "sold out", "unavailable"}:
        return "false"
    return "false"


def _clean_row(raw: Dict[str, str]) -> Dict[str, str]:
    # Supports both standardized rows and legacy SFS headers.
    product_name = str(raw.get("product_name", "")).strip() or str(raw.get("ProductName", "")).strip()
    price = (
        str(raw.get("price", "")).replace("$", "").replace(",", "").strip()
        or str(raw.get("SalePrice", "")).replace("$", "").replace(",", "").strip()
    )
    original_price = (
        str(raw.get("original_price", "")).replace("$", "").replace(",", "").strip()
        or str(raw.get("OriginalPrice", "")).replace("$", "").replace(",", "").strip()
        or price
    )
    image_url = str(raw.get("image_url", "")).strip() or str(raw.get("ImageURL", "")).strip()
    if image_url.startswith("//"):
        image_url = f"https:{image_url}"
    return {
        "product_name": product_name,
        "price": price,
        "original_price": original_price,
        "url": str(raw.get("url", "")).strip() or str(raw.get("DealURL", "")).strip(),
        "image_url": image_url,
        "brand": str(raw.get("brand", "")).strip() or str(raw.get("Brand", "")).strip() or "Other",
        "category": str(raw.get("category", "")).strip() or str(raw.get("Category", "")).strip() or "Accessories",
        "subcategory": str(raw.get("subcategory", "")).strip() or str(raw.get("Subcategory", "")).strip() or "Other",
        "size": str(raw.get("size", "")).strip() or str(raw.get("Size", "")).strip(),
        "in_stock": _clean_bool(str(raw.get("in_stock", "")).strip() or str(raw.get("Stock", "")).strip()),
        "source": SOURCE_KEY,
        "source_store": SOURCE_KEY,
        "source_product_id": str(raw.get("source_product_id", "")).strip() or str(raw.get("ID", "")).strip(),
        "description": str(raw.get("description", "")).strip() or str(raw.get("Description", "")).strip(),
    }


def run(run_id: str, output_dir: Path, log_dir: Path) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    log_path = log_dir / "scraper_sourceforsports.log"
    raw_csv_path = output_dir / "csv" / "raw_sourceforsports.csv"

    env = os.environ.copy()
    env["RUN_ID"] = run_id
    env["OUTPUT_CSV_PATH"] = str(raw_csv_path)

    command_override = env.get("SOURCEFORSPORTS_SCRAPER_COMMAND")
    if command_override:
        command = shlex.split(command_override, posix=(os.name != "nt"))
    else:
        command = [sys.executable, "automation/scrapers/sourceforsports/scrape.py"]

    code = _run_subprocess(command=command, env=env, log_path=log_path)
    if code != 0:
        return [], {
            "status": "failed",
            "return_code": code,
            "rows_scraped": 0,
            "rows_filtered": 0,
            "log_file": str(log_path),
            "raw_csv_path": str(raw_csv_path),
            "source": SOURCE_KEY,
        }

    rows: List[Dict[str, str]] = []
    filtered = 0
    if raw_csv_path.exists():
        with raw_csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                cleaned = _clean_row(raw)
                if not cleaned["product_name"] or not cleaned["price"] or not cleaned["url"]:
                    filtered += 1
                    continue
                rows.append(cleaned)

    return rows, {
        "status": "success",
        "return_code": 0,
        "rows_scraped": len(rows),
        "rows_filtered": filtered,
        "log_file": str(log_path),
        "raw_csv_path": str(raw_csv_path),
        "source": SOURCE_KEY,
    }
