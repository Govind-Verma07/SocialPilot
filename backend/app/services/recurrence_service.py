"""
app/services/recurrence_service.py
----------------------------------
Calculation and occurrence generation engine for Phase 4: Recurring Posts.
Supports DAILY, WEEKLY, and MONTHLY recurrence with safe month-end handling
and boundary enforcement (future timestamps, end_date limit, occurrence caps).
"""

import calendar
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, List

WEEKDAY_NAME_TO_INT = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

INT_TO_WEEKDAY_NAME = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


def parse_weekday(val: Optional[Union[int, str]]) -> Optional[int]:
    """Parse weekday representation into integer 0 (Monday) .. 6 (Sunday)."""
    if val is None:
        return None
    if isinstance(val, int):
        if 0 <= val <= 6:
            return val
        raise ValueError("Weekday must be between 0 (Monday) and 6 (Sunday).")
    if isinstance(val, str):
        clean = val.strip().lower()
        if clean in WEEKDAY_NAME_TO_INT:
            return WEEKDAY_NAME_TO_INT[clean]
        # Maybe numeric string
        try:
            int_val = int(clean)
            if 0 <= int_val <= 6:
                return int_val
        except ValueError:
            pass
        raise ValueError(f"Invalid weekday: '{val}'. Expected Monday through Sunday.")
    raise ValueError(f"Invalid weekday type: {type(val)}")


def compute_occurrences(
    start_at: datetime,
    end_at: datetime,
    frequency: str,
    interval: int = 1,
    by_weekday: Optional[Union[int, str]] = None,
    by_month_day: Optional[int] = None,
    occurrence_limit: Optional[int] = None,
    max_safety_limit: int = 100,
) -> List[datetime]:
    """
    Calculate scheduled occurrence datetimes for a recurring rule.
    - Preserves start_at time components (hour, minute, second).
    - Enforces end_at boundary.
    - Guarantees occurrences are in the future relative to current UTC time.
    - Clamps monthly dates safely for shorter months (e.g. Feb 28/29).
    """
    now = datetime.now(timezone.utc)

    # Normalize timezones to UTC
    start_utc = start_at if start_at.tzinfo is not None else start_at.replace(tzinfo=timezone.utc)
    end_utc = end_at if end_at.tzinfo is not None else end_at.replace(tzinfo=timezone.utc)

    if start_utc <= now:
        raise ValueError("Start date/time must be in the future.")

    if end_utc <= start_utc:
        raise ValueError("End date must be after start date.")

    freq_normalized = frequency.strip().lower()
    if freq_normalized not in ("daily", "weekly", "monthly"):
        raise ValueError(f"Unsupported frequency: '{frequency}'. Allowed: daily, weekly, monthly.")

    if interval < 1:
        raise ValueError("Recurrence interval must be at least 1.")

    limit = max_safety_limit
    if occurrence_limit is not None and occurrence_limit > 0:
        limit = min(limit, occurrence_limit)

    occurrences: List[datetime] = []

    if freq_normalized == "daily":
        curr = start_utc
        while curr <= end_utc and len(occurrences) < limit:
            if curr > now:
                occurrences.append(curr)
            curr = curr + timedelta(days=interval)

    elif freq_normalized == "weekly":
        target_weekday = parse_weekday(by_weekday) if by_weekday is not None else start_utc.weekday()
        # Find first matching weekday on or after start_utc
        diff_days = (target_weekday - start_utc.weekday()) % 7
        curr = start_utc + timedelta(days=diff_days)

        while curr <= end_utc and len(occurrences) < limit:
            if curr >= start_utc and curr > now:
                occurrences.append(curr)
            curr = curr + timedelta(weeks=interval)

    elif freq_normalized == "monthly":
        if by_month_day is not None:
            if not (1 <= by_month_day <= 31):
                raise ValueError("Monthly recurrence must have a valid day of month (1-31).")
            target_day = by_month_day
        else:
            target_day = start_utc.day

        curr_year = start_utc.year
        curr_month = start_utc.month

        # Check first candidate month
        max_d = calendar.monthrange(curr_year, curr_month)[1]
        actual_d = min(target_day, max_d)
        curr = start_utc.replace(year=curr_year, month=curr_month, day=actual_d)

        if curr < start_utc:
            # Advance to next interval month
            total_months = curr_year * 12 + (curr_month - 1) + interval
            curr_year = total_months // 12
            curr_month = (total_months % 12) + 1
            max_d = calendar.monthrange(curr_year, curr_month)[1]
            actual_d = min(target_day, max_d)
            curr = start_utc.replace(year=curr_year, month=curr_month, day=actual_d)

        while curr <= end_utc and len(occurrences) < limit:
            if curr >= start_utc and curr > now:
                occurrences.append(curr)
            # Advance by interval months
            total_months = curr_year * 12 + (curr_month - 1) + interval
            curr_year = total_months // 12
            curr_month = (total_months % 12) + 1
            max_d = calendar.monthrange(curr_year, curr_month)[1]
            actual_d = min(target_day, max_d)
            curr = start_utc.replace(year=curr_year, month=curr_month, day=actual_d)

    return occurrences
