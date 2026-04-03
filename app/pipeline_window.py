from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone


PIPELINE_WINDOW_START_ENV = "PIPELINE_WINDOW_START_UTC"
PIPELINE_WINDOW_END_ENV = "PIPELINE_WINDOW_END_UTC"


def _parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(microsecond=0)
        return parsed.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)
    except ValueError:
        return None


def get_pipeline_window(hours: int = 24) -> tuple[datetime, datetime]:
    window_start = _parse_utc_timestamp(os.getenv(PIPELINE_WINDOW_START_ENV))
    window_end = _parse_utc_timestamp(os.getenv(PIPELINE_WINDOW_END_ENV))

    if window_end is None:
        window_end = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    if window_start is None:
        window_start = window_end - timedelta(hours=hours)

    if window_start > window_end:
        window_start = window_end - timedelta(hours=hours)

    return window_start, window_end


def set_pipeline_window(hours: int = 24) -> tuple[datetime, datetime]:
    window_start, window_end = get_pipeline_window(hours=hours)
    os.environ[PIPELINE_WINDOW_START_ENV] = window_start.isoformat()
    os.environ[PIPELINE_WINDOW_END_ENV] = window_end.isoformat()
    return window_start, window_end