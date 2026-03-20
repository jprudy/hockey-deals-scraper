from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    here = Path(__file__).resolve().parent
    extractor_path = Path(os.environ.get("THS_EXTRACTOR_PATH", str(here / "ths_extractor.py")))
    out_path = os.environ.get("OUTPUT_CSV_PATH")

    if not out_path:
        raise RuntimeError("Missing OUTPUT_CSV_PATH env var from run_all.py")
    if not extractor_path.exists():
        raise FileNotFoundError(f"THS extractor not found at: {extractor_path}")

    command = [sys.executable, str(extractor_path), "--out", out_path]
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
