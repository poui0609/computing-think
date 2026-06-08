"""core/dday.py — D-day 계산 및 정렬"""
from datetime import date, datetime
from typing import Optional

from core.models import Event


def get_sort_at(event: Event) -> Optional[datetime]:
    return event.sort_at()


def calc_dday(event: Event, today: date) -> Optional[int]:
    sa = get_sort_at(event)
    if sa is None:
        return None
    return (sa.date() - today).days


def dday_label(dday: int) -> str:
    if dday < 0:
        return f"D+{abs(dday)}"
    elif dday == 0:
        return "D-day"
    return f"D-{dday}"


def dday_color(dday: Optional[int]) -> str:
    """임박도에 따른 배지 배경색"""
    if dday is None:
        return "#95A5A6"
    if dday < 0:
        return "#95A5A6"
    if dday == 0:
        return "#E74C3C"
    if dday <= 3:
        return "#E67E22"
    return "#3498DB"
