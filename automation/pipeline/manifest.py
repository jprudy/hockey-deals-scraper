from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)


def init_manifest(run_id: str, started_at: str) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "started_at": started_at,
        "ended_at": None,
        "status": "running",
        "intake_types_used": ["scraped"],
        "intake_jobs": {},
        "importer": {},
        "errors": [],
        "artifacts": {},
    }
