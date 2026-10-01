"""Audit logging — structured records for security-sensitive actions.

Writes to the audit_logs table and appends to a rotating text log file.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog

logger = logging.getLogger("rehabx.audit")

_file_handler: logging.FileHandler | None = None


def _ensure_file_handler() -> None:
    global _file_handler
    if _file_handler is not None:
        return
    try:
        path = Path(get_settings().audit_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _file_handler = logging.FileHandler(path, encoding="utf-8")
        _file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(_file_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    except OSError:
        pass


def log(
    db: Session,
    *,
    action: str,
    user_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    record = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=(ip_address or "")[:64] or None,
        user_agent=(user_agent or "")[:512] or None,
        details=details,
    )
    db.add(record)
    db.commit()

    _ensure_file_handler()
    line = json.dumps(
        {
            "ts": datetime.now().astimezone().isoformat(),
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "ip": ip_address,
            "details": details,
        },
        default=str,
    )
    logger.info("AUDIT %s", line)


def _log_enabled() -> bool:
    # Ensures file handler exists without creating a session.
    return os.getenv("DISABLE_AUDIT_FILE", "0") != "1"
