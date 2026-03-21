from __future__ import annotations

import csv
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]


def _stock_to_bool(value: str) -> str:
    text = str(value or "").strip().lower()
    if "in stock" in text or text in {"true", "1", "yes", "y"}:
        return "true"
    if text in {"false", "0", "no", "n", "out of stock"}:
        return "false"
    return "false"


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


def run(run_id: str, output_dir: Path, log_dir: Path) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    source_name = "thehockeyshop"
    log_path = log_dir / "scraper_thehockeyshop.log"
    raw_csv_path = output_dir / "csv" / "raw_thehockeyshop.csv"

    env = os.environ.copy()
    env["RUN_ID"] = run_id
    env["OUTPUT_CSV_PATH"] = str(raw_csv_path)

    command_override = env.get("THS_SCRAPER_COMMAND")
    if command_override:
        command = shlex.split(command_override, posix=(os.name != "nt"))
    else:
        command = [sys.executable, "automation/scrapers/thehockeyshop/scrape.py"]

    code = _run_subprocess(command=command, env=env, log_path=log_path)
    if code != 0:
        return [], {
            "status": "failed",
            "return_code": code,
            "rows_scraped": 0,
            "log_file": str(log_path),
            "raw_csv_path": str(raw_csv_path),
            "source": source_name,
        }

    rows: List[Dict[str, str]] = []
    if raw_csv_path.exists():
        with raw_csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                rows.append(
                    {
                        "product_name": str(raw.get("ProductName", "")).strip(),
                        "price": str(raw.get("SalePrice", "")).strip(),
                        "original_price": str(raw.get("OriginalPrice", "")).strip(),
                        "url": str(raw.get("DealURL", "")).strip(),
                        "image_url": str(raw.get("ImageURL", "")).strip(),
                        "brand": str(raw.get("Brand", "")).strip(),
                        "category": str(raw.get("Category", "")).strip(),
                        "subcategory": str(raw.get("Subcategory", "")).strip(),
                        "size": str(raw.get("Size", "")).strip(),
                        "in_stock": _stock_to_bool(str(raw.get("Stock", ""))),
                        "source": "ths",
                        "source_store": "thehockeyshop",
                        "source_product_id": str(raw.get("ID", "")).strip(),
                        "description": str(raw.get("Description", "")).strip(),
                    }
                )

    return rows, {
        "status": "success",
        "return_code": 0,
        "rows_scraped": len(rows),
        "log_file": str(log_path),
        "raw_csv_path": str(raw_csv_path),
        "source": source_name,
    }
