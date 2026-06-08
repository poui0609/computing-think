"""core/storage.py — schedules.json CRUD"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from core.models import (
    Course, Event, Rule, COURSE_PALETTE,
    event_from_dict, rule_from_dict,
)
from core.dday import get_sort_at, calc_dday
from core.progress import course_week_progress

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "schedules.json"
COURSE_MAPPING_PATH = PROJECT_ROOT / "assets" / "CourseMapping.json"

DEFAULT_SEMESTER = {
    "year": 2026,
    "term": 1,
    "start_date": "2026-03-02",
    "end_date": "2026-06-15",
}

EMPTY_DATA: dict = {
    "version": "1.0",
    "semester": DEFAULT_SEMESTER,
    "courses": [],
    "rules": [],
    "events": [],
}


@dataclass
class ScheduleData:
    version: str = "1.0"
    semester: dict = field(default_factory=lambda: dict(DEFAULT_SEMESTER))
    courses: list[Course] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)


def load() -> ScheduleData:
    if not DATA_PATH.exists():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(
            json.dumps(EMPTY_DATA, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return ScheduleData(
        version=raw.get("version", "1.0"),
        semester=raw.get("semester", DEFAULT_SEMESTER),
        courses=[Course.from_dict(c) for c in raw.get("courses", [])],
        rules=[rule_from_dict(r) for r in raw.get("rules", [])],
        events=[event_from_dict(e) for e in raw.get("events", [])],
    )


def save(data: ScheduleData) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "version": data.version,
        "semester": data.semester,
        "courses": [c.to_dict() for c in data.courses],
        "rules":   [r.to_dict() for r in data.rules],
        "events":  [e.to_dict() for e in data.events],
    }
    DATA_PATH.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_course_mapping() -> dict[str, str]:
    if COURSE_MAPPING_PATH.exists():
        return json.loads(COURSE_MAPPING_PATH.read_text(encoding="utf-8"))
    return {}


def _next_color(courses: list[Course]) -> str:
    used = {c.color for c in courses}
    for color in COURSE_PALETTE:
        if color not in used:
            return color
    return COURSE_PALETTE[len(courses) % len(COURSE_PALETTE)]


# ─── Course ───────────────────────────────────────────────────

def add_course(code: str, name: str) -> Course:
    data = load()
    if any(c.code == code for c in data.courses):
        raise ValueError(f"이미 등록된 학정번호입니다: {code}")
    course = Course(code=code, name=name, color=_next_color(data.courses))
    data.courses.append(course)
    save(data)
    return course


def update_course(code: str, name: Optional[str] = None, color: Optional[str] = None) -> Course:
    data = load()
    for c in data.courses:
        if c.code == code:
            if name is not None:
                c.name = name
            if color is not None:
                c.color = color
            save(data)
            return c
    raise KeyError(f"Course not found: {code}")


def remove_course(code: str) -> None:
    data = load()
    data.courses = [c for c in data.courses if c.code != code]
    data.rules   = [r for r in data.rules   if r.course_code != code]
    data.events  = [e for e in data.events  if e.course_code != code]
    save(data)


def get_course_map(data: Optional[ScheduleData] = None) -> dict[str, Course]:
    if data is None:
        data = load()
    return {c.code: c for c in data.courses}


# ─── Event ────────────────────────────────────────────────────

def add_event(event: Event) -> Event:
    data = load()
    data.events.append(event)
    save(data)
    return event


def update_event(event_id: str, **fields) -> Event:
    data = load()
    for e in data.events:
        if e.id == event_id:
            for k, v in fields.items():
                if hasattr(e, k):
                    setattr(e, k, v)
            save(data)
            return e
    raise KeyError(f"Event not found: {event_id}")


def remove_event(event_id: str) -> None:
    data = load()
    data.events = [e for e in data.events if e.id != event_id]
    save(data)


def set_event_progress(event_id: str, progress: int) -> Event:
    progress = max(0, min(100, progress))
    return update_event(event_id, progress=progress, completed=(progress == 100))


def toggle_event_completed(event_id: str, completed: bool) -> Event:
    fields: dict = {"completed": completed}
    if completed:
        fields["progress"] = 100
    return update_event(event_id, **fields)


def list_events(
    course_codes: Optional[list[str]] = None,
    event_types: Optional[list[str]] = None,
    completed: Optional[bool] = None,
    data: Optional[ScheduleData] = None,
) -> list[Event]:
    if data is None:
        data = load()
    events = data.events
    if course_codes:
        events = [e for e in events if e.course_code in course_codes]
    if event_types:
        events = [e for e in events if e.event_type_key() in event_types]
    if completed is not None:
        events = [e for e in events if e.completed == completed]
    return events


def get_upcoming(today: date, max_dday: int = 3) -> list[Event]:
    data = load()
    result = []
    for e in data.events:
        if e.completed:
            continue
        dday = calc_dday(e, today)
        if dday is not None and 0 <= dday <= max_dday:
            result.append(e)
    result.sort(key=lambda e: (
        get_sort_at(e) or datetime.max,
        e.course_code,
        e.title,
    ))
    return result


def get_all_upcoming(today: date) -> list[Event]:
    data = load()
    result = [
        e for e in data.events
        if not e.completed and get_sort_at(e) is not None
        and (get_sort_at(e)).date() >= today
    ]
    result.sort(key=lambda e: (get_sort_at(e) or datetime.max))
    return result


def get_overdue(today: date) -> list[Event]:
    data = load()
    result = [
        e for e in data.events
        if not e.completed and get_sort_at(e) is not None
        and (get_sort_at(e)).date() < today
    ]
    result.sort(key=lambda e: (get_sort_at(e) or datetime.max))
    return result


# ─── Rule ─────────────────────────────────────────────────────

def add_rule(rule: Rule) -> Rule:
    data = load()
    data.rules.append(rule)
    save(data)
    return rule


def update_rule(rule_id: str, **fields) -> Rule:
    data = load()
    for r in data.rules:
        if r.id == rule_id:
            for k, v in fields.items():
                if hasattr(r, k):
                    setattr(r, k, v)
            save(data)
            return r
    raise KeyError(f"Rule not found: {rule_id}")


def remove_rule(rule_id: str) -> None:
    data = load()
    data.rules  = [r for r in data.rules  if r.id != rule_id]
    data.events = [e for e in data.events if e.rule_id != rule_id]
    save(data)


def get_course_week_progress_val(course_code: str, week_number: int) -> int:
    data = load()
    return course_week_progress(data.events, course_code, week_number)


def current_week_number(today: Optional[date] = None) -> int:
    data = load()
    if today is None:
        today = date.today()
    start = date.fromisoformat(data.semester["start_date"])
    delta = (today - start).days
    return max(1, delta // 7 + 1)
