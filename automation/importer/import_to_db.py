from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from automation.pipeline.schema import validate_and_normalize_row


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_rows(csv_path: Path, run_id: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, raw in enumerate(reader, start=2):
            validated = validate_and_normalize_row(raw, run_id=run_id)
            if not validated.ok:
                reason = ",".join(validated.errors)
                raise ValueError(f"Invalid CSV row at line {idx}: {reason}")
            rows.append(validated.row)
    return rows


def get_npx_command() -> str:
    # On Windows, subprocess often needs the .cmd shim explicitly.
    return "npx.cmd" if os.name == "nt" else "npx"


def run_prisma_import(rows_path: Path, run_id: str, summary_path: Path) -> int:
    taxonomy_review_path = summary_path.parent / "taxonomy_review.json"
    command = [
        get_npx_command(),
        "tsx",
        "automation/importer/prisma_upsert.ts",
        "--rows",
        str(rows_path),
        "--run-id",
        run_id,
        "--stale-threshold",
        "2",
        "--summary",
        str(summary_path),
        "--taxonomy-review",
        str(taxonomy_review_path),
    ]

    print(f"[import_to_db] running: {' '.join(command)}", flush=True)

    completed = subprocess.run(
        command,
        check=False,
        cwd=PROJECT_ROOT,
        shell=False,
    )
    return completed.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import normalized CSV rows into Neon via Prisma.")
    parser.add_argument("--csv", required=True, help="Path to normalized CSV file")
    parser.add_argument("--run-id", required=True, help="Current run id")
    parser.add_argument("--summary", required=True, help="Path to importer summary JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv).resolve()
    summary_path = Path(args.summary).resolve()

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    rows = load_rows(csv_path=csv_path, run_id=args.run_id)
    rows_path = summary_path.parent / "rows.json"
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    rows_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    return_code = run_prisma_import(
        rows_path=rows_path,
        run_id=args.run_id,
        summary_path=summary_path,
    )
    if return_code != 0:
        return return_code

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[import_to_db] fatal: {exc}", file=sys.stderr)
        sys.exit(1)