"""core/progress.py — Progress 색상 gradient 및 집계"""
from core.models import Event

_GRADIENT = [
    (0,   10,  "#E53935"),
    (10,  30,  "#FB8C00"),
    (30,  50,  "#FDD835"),
    (50,  70,  "#C0CA33"),
    (70,  90,  "#7CB342"),
    (90,  100, "#43A047"),
    (100, 101, "#00ACC1"),
]


def progress_color(pct: int) -> str:
    for lo, hi, color in _GRADIENT:
        if lo <= pct < hi:
            return color
    return "#00ACC1"


def progress_bar_html(pct: int, height: int = 6) -> str:
    color = progress_color(pct)
    label = "전부 클리어! 🎉" if pct == 100 else f"{pct}%"
    return (
        f'<div style="display:flex; align-items:center; gap:6px;">'
        f'<div style="flex:1; height:{height}px; background:#eee; border-radius:{height}px;">'
        f'<div style="width:{pct}%; height:{height}px; background:{color}; border-radius:{height}px; transition:width .3s;"></div>'
        f'</div>'
        f'<span style="font-size:11px; color:{color}; font-weight:bold; min-width:70px;">{label}</span>'
        f'</div>'
    )


def course_week_progress(events: list[Event], course_code: str, week_number: int) -> int:
    targets = [
        e for e in events
        if e.course_code == course_code and e.week_number == week_number
    ]
    if not targets:
        return 0
    return round(sum(e.progress for e in targets) / len(targets))


def overall_week_progress(events: list[Event], week_number: int) -> int:
    targets = [e for e in events if e.week_number == week_number]
    if not targets:
        return 0
    return round(sum(e.progress for e in targets) / len(targets))
