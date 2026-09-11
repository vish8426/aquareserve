"""Saved configurations / leads

A minimal append-only JSONL store so a prospect's configuration and contact details can be kept for follow-up.
This is a lightweight store: a flat file, single-tenant and unauthenticated.
Real multi-tenant lead storage with access control lands with the phased database and auth.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import REPO_ROOT

LEADS_PATH = Path(os.environ.get("AQUARESERVE_LEADS_PATH", REPO_ROOT / "data" / "leads.jsonl"))


def save_lead(record: dict[str, Any]) -> dict[str, str]:
    """Append a lead and return its id and creation time."""
    lead_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = {"id": lead_id, "created": created, **record}
    LEADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEADS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return {"id": lead_id, "created": created}


def list_leads() -> list[dict[str, Any]]:
    if not LEADS_PATH.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in LEADS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out
