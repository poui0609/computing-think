"""core/progress.py — Progress 색상 gradient 및 집계

진행률 집계 필터 규칙:
  1. TIMED_EVENT_TYPES (교시형·행사형) 제외 — 시간이 지나면 자동 완료
  2. 아직 오픈되지 않은 일정 제외 — open_at/start_at 이 현재보다 미래
  3. 마감기한이 지난 일정 제외 — due_at/end_at 이 현재보다 과거
  → 결과: 현재 시점에 실제로 진행 중인 일정만 진행률에 반영
"""
from __future__ import annotations

from datetime import datetime

from core.models import (
    Event, TIMED_EVENT_TYPES,
    DeadlineEvent, RangeEvent, OpenEvent,
    is_timed, timed_auto_done,
)


# ─── 색상 그라디언트 ──────────────────────────────────────────

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
    label = "Clear!" if pct == 100 else f"{pct}%"
    return (
        f'<div style="display:flex; align-items:center; gap:6px;">'
        f'<div style="flex:1; height:{height}px; background:#eee; border-radius:{height}px;">'
        f'<div style="width:{pct}%; height:{height}px; background:{color}; '
        f'border-radius:{height}px; transition:width .3s;"></div>'
        f'</div>'
        f'<span style="font-size:11px; color:{color}; font-weight:bold; min-width:70px;">{label}</span>'
        f'</div>'
    )


# ─── 진행률 집계 필터 ─────────────────────────────────────────

def is_progress_eligible(event: Event, now: datetime) -> bool:
    """현재 시점(now) 기준으로 진행률 집계에 포함할 이벤트인지 판단.

    제외 조건:
      - 교시형/행사형 (TIMED_EVENT_TYPES)
      - DeadlineEvent: open_at > now (아직 오픈 전)
      - DeadlineEvent: due_at  < now (마감 경과)
      - RangeEvent:    start_at > now (아직 시작 전)
      - RangeEvent:    end_at   < now (이미 종료)
      - OpenEvent:     start_at > now (아직 시작 전)
    """
    if event.event_type_key() in TIMED_EVENT_TYPES:
        return False

    if isinstance(event, DeadlineEvent):
        if event.open_at and datetime.fromisoformat(event.open_at) > now:
            return False   # 아직 오픈 전
        if event.due_at and datetime.fromisoformat(event.due_at) < now:
            return False   # 마감 경과

    elif isinstance(event, OpenEvent):
        # OpenEvent 는 end_at 없음 — 시작 전이면 제외, 이후는 계속 포함
        if event.start_at and datetime.fromisoformat(event.start_at) > now:
            return False   # 아직 시작 전

    elif isinstance(event, RangeEvent):
        if event.start_at and datetime.fromisoformat(event.start_at) > now:
            return False   # 아직 시작 전
        if event.end_at and datetime.fromisoformat(event.end_at) < now:
            return False   # 이미 종료

    return True


def is_todo(event: Event, now: datetime) -> bool:
    """TODO 모드에서 표시할 이벤트인지 판단.

    표시 조건 (모두 충족해야 함):
      - 수동 완료되지 않음
      - 교시형/행사형: 아직 시작·종료 전 (자동 완료 전)
      - DeadlineEvent: 오픈됐고(open_at 경과) 마감 전(due_at 미경과)
      - RangeEvent:    시작됐고(start_at 경과) 종료 전(end_at 미경과)
      - OpenEvent:     시작됐고(start_at 경과) — 만료 없음
    """
    # 수동 완료된 이벤트는 TODO에서 제외
    if event.completed:
        return False

    if is_timed(event):
        # 교시형/행사형: 자동 완료(시간 경과)되면 TODO에서 제외
        return not timed_auto_done(event)

    if isinstance(event, DeadlineEvent):
        if event.open_at and datetime.fromisoformat(event.open_at) > now:
            return False   # 아직 오픈 전
        if event.due_at and datetime.fromisoformat(event.due_at) < now:
            return False   # 마감 경과 → 더 이상 할 수 없음

    elif isinstance(event, OpenEvent):
        if event.start_at and datetime.fromisoformat(event.start_at) > now:
            return False   # 아직 시작 전

    elif isinstance(event, RangeEvent):
        if event.start_at and datetime.fromisoformat(event.start_at) > now:
            return False   # 아직 시작 전
        if event.end_at and datetime.fromisoformat(event.end_at) < now:
            return False   # 이미 종료

    return True


# ─── 집계 함수 ────────────────────────────────────────────────

def course_week_progress(events: list[Event], course_code: str, week_number: int) -> int:
    """특정 수업의 주차 진행률 (0~100 정수)."""
    now     = datetime.now()
    targets = [
        e for e in events
        if e.course_code == course_code
        and e.week_number == week_number
        and is_progress_eligible(e, now)
    ]
    if not targets:
        return 0
    return round(sum(e.progress for e in targets) / len(targets))


def overall_week_progress(events: list[Event], week_number: int) -> int:
    """전체 수업의 주차 진행률 (0~100 정수)."""
    now     = datetime.now()
    targets = [
        e for e in events
        if e.week_number == week_number
        and is_progress_eligible(e, now)
    ]
    if not targets:
        return 0
    return round(sum(e.progress for e in targets) / len(targets))
