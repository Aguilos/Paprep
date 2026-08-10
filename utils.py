"""Shared utilities for PaPrep."""
from datetime import datetime, timezone, timedelta

_PHT = timezone(timedelta(hours=8))  # Philippine Standard Time (UTC+8)


def today_pht():
    """Return the current date in Philippine Standard Time (UTC+8)."""
    return datetime.now(_PHT).date()
