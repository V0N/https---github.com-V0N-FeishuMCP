from __future__ import annotations

import calendar
import re
from datetime import date


def month_range(year: int, month: int) -> tuple[int, int]:
    last_day = calendar.monthrange(year, month)[1]
    start = year * 10000 + month * 100 + 1
    end = year * 10000 + month * 100 + last_day
    return (start, end)


def _last_month_range() -> list[tuple[int, int]]:
    today = date.today()
    year, month = today.year, today.month
    if month == 1:
        year -= 1
        month = 12
    else:
        month -= 1
    return [month_range(year, month)]


def _last_quarter_ranges() -> list[tuple[int, int]]:
    today = date.today()
    year, month = today.year, today.month
    current_q = (month - 1) // 3 + 1
    if current_q == 1:
        year -= 1
        last_q = 4
    else:
        last_q = current_q - 1
    start_month = (last_q - 1) * 3 + 1
    return [month_range(year, start_month + i) for i in range(3)]


def _quarter_ranges(year: int, q: int) -> list[tuple[int, int]]:
    start_month = (q - 1) * 3 + 1
    return [month_range(year, start_month + i) for i in range(3)]


def parse_time_range(text: str) -> list[tuple[int, int]]:
    text = text.strip()

    if text in ("上个月", "上月"):
        return _last_month_range()

    if text in ("上个季度", "上季度"):
        return _last_quarter_ranges()

    m = re.fullmatch(r"(\d{4})年(\d{1,2})月", text)
    if m:
        return [month_range(int(m.group(1)), int(m.group(2)))]

    m = re.fullmatch(r"(\d{1,2})月", text)
    if m:
        return [month_range(date.today().year, int(m.group(1)))]

    m = re.fullmatch(r"(\d{4})-(\d{2})", text)
    if m:
        return [month_range(int(m.group(1)), int(m.group(2)))]

    m = re.fullmatch(r"(\d{4})[Qq]([1-4])", text)
    if m:
        return _quarter_ranges(int(m.group(1)), int(m.group(2)))

    m = re.fullmatch(r"[Qq]([1-4])", text)
    if m:
        return _quarter_ranges(date.today().year, int(m.group(1)))

    return _last_month_range()


def format_time_range_label(ranges: list[tuple[int, int]]) -> str:
    if len(ranges) == 1:
        start = ranges[0][0]
        year = start // 10000
        month = (start % 10000) // 100
        return f"{year}年{month}月"

    if len(ranges) == 3:
        start = ranges[0][0]
        year = start // 10000
        month1 = (ranges[0][0] % 10000) // 100
        month3 = (ranges[2][0] % 10000) // 100
        q = (month1 - 1) // 3 + 1
        return f"{year}年Q{q}（{month1}-{month3}月）"

    start = ranges[0][0]
    end = ranges[-1][1]
    year_s = start // 10000
    month_s = (start % 10000) // 100
    year_e = end // 10000
    month_e = (end % 10000) // 100
    return f"{year_s}年{month_s}月-{year_e}年{month_e}月"
