"""core/io.py — JSON 가져오기/내보내기 + ICS 내보내기"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from core.models import (
    Event, PeriodEvent, WindowEvent, DeadlineEvent,
    event_from_dict, rule_from_dict,
    Course,
)
from core.storage import ScheduleData, load, save


# ─── JSON ─────────────────────────────────────────────────────

def export_json(data: Optional[ScheduleData] = None) -> bytes:
    if data is None:
        data = load()
    raw = {
        "version": data.version,
        "semester": data.semester,
        "courses": [c.to_dict() for c in data.courses],
        "rules":   [r.to_dict() for r in data.rules],
        "events":  [e.to_dict() for e in data.events],
    }
    return json.dumps(raw, ensure_ascii=False, indent=2).encode("utf-8")


def validate_schema(raw: dict) -> tuple[bool, str]:
    if raw.get("version") != "1.0":
        return False, f"지원하지 않는 버전입니다: {raw.get('version')} (지원: 1.0)"
    for key in ("courses", "rules", "events"):
        if not isinstance(raw.get(key), list):
            return False, f"'{key}' 필드가 없거나 형식이 잘못됐습니다."
    return True, "OK"


def import_json(
    raw_bytes: bytes,
    mode: str = "replace",
) -> tuple[ScheduleData, str]:
    """
    mode: "replace" | "merge"
    Returns (new_data, summary_message)
    """
    raw = json.loads(raw_bytes.decode("utf-8"))
    ok, msg = validate_schema(raw)
    if not ok:
        raise ValueError(msg)

    imported = ScheduleData(
        version=raw["version"],
        semester=raw.get("semester", {}),
        courses=[Course.from_dict(c) for c in raw["courses"]],
        rules=[rule_from_dict(r) for r in raw["rules"]],
        events=[event_from_dict(e) for e in raw["events"]],
    )

    if mode == "replace":
        save(imported)
        return imported, (
            f"전체 교체 완료: 과목 {len(imported.courses)}개, "
            f"규칙 {len(imported.rules)}개, 일정 {len(imported.events)}개"
        )

    # merge: upsert by id
    existing = load()

    existing_course_codes = {c.code for c in existing.courses}
    for c in imported.courses:
        if c.code not in existing_course_codes:
            existing.courses.append(c)
        else:
            for ec in existing.courses:
                if ec.code == c.code:
                    ec.name  = c.name
                    ec.color = c.color

    existing_rule_ids = {r.id for r in existing.rules}
    for r in imported.rules:
        if r.id not in existing_rule_ids:
            existing.rules.append(r)
        else:
            existing.rules = [r if er.id == r.id else er for er in existing.rules]

    existing_event_ids = {e.id for e in existing.events}
    added = 0
    updated = 0
    for e in imported.events:
        if e.id not in existing_event_ids:
            existing.events.append(e)
            added += 1
        else:
            existing.events = [e if ee.id == e.id else ee for ee in existing.events]
            updated += 1

    save(existing)
    return existing, f"병합 완료: 신규 {added}건 추가, {updated}건 갱신"


# ─── ICS 내보내기 ─────────────────────────────────────────────

def _dt_to_ical(dt_str: Optional[str]) -> Optional[str]:
    if not dt_str:
        return None
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%Y%m%dT%H%M%S")


def export_ics(
    data: Optional[ScheduleData] = None,
    course_codes: Optional[list[str]] = None,
    event_types: Optional[list[str]] = None,
    exclude_completed: bool = True,
) -> bytes:
    if data is None:
        data = load()

    course_map = {c.code: c for c in data.courses}
    events = data.events

    if course_codes:
        events = [e for e in events if e.course_code in course_codes]
    if event_types:
        events = [e for e in events if e.event_type_key() in event_types]
    if exclude_completed:
        events = [e for e in events if not e.completed]

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ExamPlanner//ExamPlanner 1.0//KO",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for e in events:
        course = course_map.get(e.course_code)
        course_name = course.name if course else e.course_code

        if isinstance(e, PeriodEvent):
            dtstart = _dt_to_ical(e.start_at)
            dtend   = _dt_to_ical(e.end_at) or dtstart
        elif isinstance(e, WindowEvent):
            dtstart = _dt_to_ical(e.open_at) or _dt_to_ical(e.due_at)
            dtend   = _dt_to_ical(e.due_at)
        else:
            dtstart = _dt_to_ical(e.due_at)
            dtend   = dtstart

        if not dtstart:
            continue

        desc = e.description or ""
        if e.progress > 0:
            desc += f"\\n진행률: {e.progress}%"
        desc = desc.replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

        lines += [
            "BEGIN:VEVENT",
            f"UID:{e.id}@exam-planner",
            f"SUMMARY:[{course_name}] {e.title}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"DESCRIPTION:{desc}",
            f"CATEGORIES:{course_name}",
            f"X-EXAMPLANNER-TYPE:{e.event_type_key()}",
            f"X-EXAMPLANNER-PROGRESS:{e.progress}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode("utf-8")
