from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ok(message: str, **fields: Any) -> Dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "error": None,
        "timestamp": timestamp(),
        **fields,
    }


def error_body(
    message: str,
    code: str,
    details: Optional[Dict[str, Any]] = None,
    *,
    accepted: Optional[bool] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "success": False,
        "message": message,
        "error": {
            "code": code,
            "details": details or {},
        },
        "timestamp": timestamp(),
    }
    if accepted is not None:
        body["accepted"] = accepted
    return body


def fail(
    status_code: int,
    message: str,
    code: str,
    details: Optional[Dict[str, Any]] = None,
    *,
    accepted: Optional[bool] = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=error_body(message, code, details, accepted=accepted),
    )
