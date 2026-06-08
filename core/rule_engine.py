"""core/rule_engine.py — 반복 규칙 확장 엔진"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Optional

from core.models import (
    Event, Rule, WindowCycleRule, PeriodWeeklyRule, DueWeeklyRule,
    EVENT_TYPE_MAP, EVENT_LABEL_MAP,
)
from core.period import periods_to_range, combine_datetime, PERIOD_TABLE


def week_number(d: date, semester_start: date) -> int:
    delta = (d - semester_start).days
    return max(1, delta // 7 + 1)


def _week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _date_with_weekday(week_mon: date, weekday: int) -> date:
    return week_mon + timedelta(days=weekday)


def _make_title(template: str, week_num: int, event_type: str) -> str:
    label = EVENT_LABEL_MAP.get(event_type, event_type)
    return template.replace("{week}", str(week_num)).replace("{label}", label)


def expand_rule(rule: Rule) -> list[Event]:
    """규칙 하나에서 학기 내 모든 이벤트를 생성합니다."""
    from core.storage import load
    data = load()

    semester_start = date.fromisoformat(data.semester["start_date"])
    rule_start = date.fromisoformat(rule.start_date)
    rule_end   = date.fromisoformat(rule.end_date)

    existing_keys = {
        (e.rule_id, e.week_number)
        for e in data.events
        if e.rule_id == rule.id and e.week_number is not None
    }

    cls = EVENT_TYPE_MAP.get(rule.event_type)
    if cls is None:
        raise ValueError(f"Unknown event_type: {rule.event_type}")

    events: list[Event] = []
    cursor = _week_monday(rule_start)
    week_num = week_number(cursor, semester_start)

    while cursor <= rule_end + timedelta(days=6):
        if (rule.id, week_num) in existing_keys:
            cursor += timedelta(weeks=1)
            week_num += 1
            continue

        title = _make_title(rule.title_template, week_num, rule.event_type)

        if isinstance(rule, WindowCycleRule):
            open_date = _date_with_weekday(cursor, rule.open_weekday)
            open_dt = None
            if rule.open_period in PERIOD_TABLE:
                open_dt, _ = periods_to_range(open_date, rule.open_period, rule.open_period)

            due_week_mon = cursor + timedelta(weeks=rule.due_week_offset)
            due_date = _date_with_weekday(due_week_mon, rule.due_weekday)
            due_dt   = combine_datetime(due_date, rule.due_time)

            if not (rule_start <= open_date <= rule_end or rule_start <= due_date <= rule_end):
                cursor += timedelta(weeks=1)
                week_num += 1
                continue

            evt = cls(
                id=str(uuid.uuid4()),
                course_code=rule.course_code,
                title=title,
                source="rule",
                rule_id=rule.id,
                week_number=week_num,
                open_at=open_dt.isoformat() if open_dt else None,
                due_at=due_dt.isoformat(),
            )

        elif isinstance(rule, PeriodWeeklyRule):
            occ_date = _date_with_weekday(cursor, rule.occurrence_weekday)
            if not (rule_start <= occ_date <= rule_end):
                cursor += timedelta(weeks=1)
                week_num += 1
                continue

            start_dt, end_dt = periods_to_range(
                occ_date, rule.start_period, rule.end_period
            )
            evt = cls(
                id=str(uuid.uuid4()),
                course_code=rule.course_code,
                title=title,
                source="rule",
                rule_id=rule.id,
                week_number=week_num,
                start_at=start_dt.isoformat(),
                end_at=end_dt.isoformat(),
                start_period=rule.start_period,
                end_period=rule.end_period,
            )

        elif isinstance(rule, DueWeeklyRule):
            due_date = _date_with_weekday(cursor, rule.due_weekday)
            if not (rule_start <= due_date <= rule_end):
                cursor += timedelta(weeks=1)
                week_num += 1
                continue

            due_dt = combine_datetime(due_date, rule.due_time)
            evt = cls(
                id=str(uuid.uuid4()),
                course_code=rule.course_code,
                title=title,
                source="rule",
                rule_id=rule.id,
                week_number=week_num,
                due_at=due_dt.isoformat(),
            )

        else:
            cursor += timedelta(weeks=1)
            week_num += 1
            continue

        events.append(evt)
        cursor += timedelta(weeks=1)
        week_num += 1

    return events


def regenerate_rule(rule_id: str) -> list[Event]:
    """미완료 연결 이벤트를 삭제하고 규칙을 재확장합니다."""
    from core.storage import load, save, add_event
    data = load()

    rule = next((r for r in data.rules if r.id == rule_id), None)
    if not rule:
        raise KeyError(f"Rule not found: {rule_id}")

    data.events = [
        e for e in data.events
        if not (e.rule_id == rule_id and not e.completed)
    ]
    save(data)

    new_events = expand_rule(rule)
    for evt in new_events:
        add_event(evt)
    return new_events


def rule_preview(rule: Rule, semester_start: str) -> Optional[str]:
    """규칙의 첫 주차 샘플 문자열을 반환합니다 (UI 미리보기용)"""
    try:
        start = date.fromisoformat(rule.start_date)
        sem_start = date.fromisoformat(semester_start)
        cursor = _week_monday(start)
        week_num = week_number(cursor, sem_start)
        title = _make_title(rule.title_template, week_num, rule.event_type)

        if isinstance(rule, WindowCycleRule):
            open_date = _date_with_weekday(cursor, rule.open_weekday)
            open_dt, _ = periods_to_range(open_date, rule.open_period, rule.open_period)
            due_week_mon = cursor + timedelta(weeks=rule.due_week_offset)
            due_date = _date_with_weekday(due_week_mon, rule.due_weekday)
            due_dt = combine_datetime(due_date, rule.due_time)
            return (
                f"{title}: {open_dt.strftime('%m/%d(%a) %H:%M')} ~ "
                f"{due_dt.strftime('%m/%d(%a) %H:%M')}"
            )
        elif isinstance(rule, PeriodWeeklyRule):
            occ_date = _date_with_weekday(cursor, rule.occurrence_weekday)
            start_dt, end_dt = periods_to_range(occ_date, rule.start_period, rule.end_period)
            return (
                f"{title}: {start_dt.strftime('%m/%d(%a) %H:%M')} ~ "
                f"{end_dt.strftime('%H:%M')}"
            )
        elif isinstance(rule, DueWeeklyRule):
            due_date = _date_with_weekday(cursor, rule.due_weekday)
            due_dt = combine_datetime(due_date, rule.due_time)
            return f"{title}: ~ {due_dt.strftime('%m/%d(%a) %H:%M')}"
    except Exception:
        return None
    return None
