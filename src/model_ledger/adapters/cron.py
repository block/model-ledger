"""Cron expression utilities.

Translate 5-field cron expressions to human-readable English.
Used by connectors that discover scheduled ETL jobs.
"""

from __future__ import annotations


def translate_cron_to_english(cron_expression: str | None) -> str:
    """Translate a 5-field cron expression to plain English with UTC timezone.

    Example:
        >>> translate_cron_to_english("0 7 * * *")
        'Daily at 7:00 AM UTC'
        >>> translate_cron_to_english("0 13 2 * *")
        '2nd of each month at 1:00 PM UTC'
        >>> translate_cron_to_english(None)
        'Not scheduled'
    """
    if not cron_expression:
        return "Not scheduled"

    parts = cron_expression.strip().split()
    if len(parts) != 5:
        return f"Custom schedule: {cron_expression} (UTC)"

    minute, hour, day, month, weekday = parts

    def format_time(h: str, m: str) -> str:
        try:
            hour_int = int(h)
            minute_int = int(m)
            period = "AM" if hour_int < 12 else "PM"
            display_hour = hour_int if hour_int <= 12 else hour_int - 12
            display_hour = 12 if display_hour == 0 else display_hour
            return f"{display_hour}:{minute_int:02d} {period} UTC"
        except (ValueError, TypeError):
            return f"{h}:{m} UTC"

    if day == "*" and month == "*" and weekday == "*":
        if hour.startswith("*/"):
            return f"Every {hour[2:]} hours"
        return f"Daily at {format_time(hour, minute)}"

    def get_suffix(day_num: str) -> str:
        try:
            num = int(day_num)
            if 10 <= num % 100 <= 20:
                return "th"
            return {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
        except (ValueError, TypeError):
            return "th"

    if "," in day and month == "*" and weekday == "*":
        days = day.split(",")
        day_list = ", ".join([f"{d}{get_suffix(d)}" for d in days])
        return f"{day_list} of each month at {format_time(hour, minute)}"

    if day.isdigit() and day != "*" and month == "*" and weekday == "*":
        return f"{day}{get_suffix(day)} of each month at {format_time(hour, minute)}"

    if day == "*" and month == "*" and weekday.isdigit():
        days_of_week = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]
        weekday_int = int(weekday)
        if 0 <= weekday_int < len(days_of_week):
            return f"Every {days_of_week[weekday_int]} at {format_time(hour, minute)}"

    return f"Custom schedule: {cron_expression} (UTC)"
