from datetime import date
from typing import Any, Optional


def _get(data: dict, key: str, default=None):
    return data.get(key) if isinstance(data, dict) else default


def _parse_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str) and len(v) >= 10:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            pass
    return None
