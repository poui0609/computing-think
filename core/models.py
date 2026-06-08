"""
core/models.py
OOP class hierarchy: Course, Event (14 subclasses), Rule (3 subclasses)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


def _icon(filename: str) -> str:
    return str(_ICONS_DIR / filename)


COURSE_PALETTE = [
    "#4A90D9", "#E67E22", "#2ECC71", "#9B59B6",
    "#E74C3C", "#1ABC9C", "#F39C12", "#3498DB",
    "#D35400", "#27AE60", "#8E44AD", "#C0392B",
]

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


# ─── Course ───────────────────────────────────────────────────

@dataclass
class Course:
    code: str
    name: str
    color: str = "#4A90D9"

    def to_dict(self) -> dict:
        return {"code": self.code, "name": self.name, "color": self.color}

    @classmethod
    def from_dict(cls, d: dict) -> "Course":
        return cls(**d)


# ─── Base Event ───────────────────────────────────────────────

@dataclass
class Event:
    id: str
    course_code: str
    title: str
    description: str = ""
    source: str = "manual"          # "manual" | "rule"
    rule_id: Optional[str] = None
    week_number: Optional[int] = None
    progress: int = 0               # 0~100
    completed: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def sort_at(self) -> Optional[datetime]:
        raise NotImplementedError

    def label(self) -> str:
        raise NotImplementedError

    def icon_path(self) -> str:
        raise NotImplementedError

    def event_type_key(self) -> str:
        raise NotImplementedError

    def _base_dict(self) -> dict:
        return {
            "id": self.id,
            "course_code": self.course_code,
            "event_type": self.event_type_key(),
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "rule_id": self.rule_id,
            "week_number": self.week_number,
            "progress": self.progress,
            "completed": self.completed,
            "created_at": self.created_at,
        }

    def to_dict(self) -> dict:
        return self._base_dict()


# ─── PeriodEvent ──────────────────────────────────────────────

@dataclass
class PeriodEvent(Event):
    """교시 기반 이벤트 (퀴즈/시험, 화상강의)"""
    start_at: Optional[str] = None      # ISO datetime string
    end_at: Optional[str] = None
    start_period: Optional[int] = None
    end_period: Optional[int] = None

    def sort_at(self) -> Optional[datetime]:
        return datetime.fromisoformat(self.start_at) if self.start_at else None

    def to_dict(self) -> dict:
        d = self._base_dict()
        d.update({
            "start_at": self.start_at,
            "end_at": self.end_at,
            "start_period": self.start_period,
            "end_period": self.end_period,
        })
        return d


@dataclass
class Quiz(PeriodEvent):
    def label(self) -> str:         return "퀴즈"
    def icon_path(self) -> str:     return _icon("Quiz_Icon.png")
    def event_type_key(self) -> str: return "quiz"


@dataclass
class ZoomMeeting(PeriodEvent):
    def label(self) -> str:         return "화상 강의"
    def icon_path(self) -> str:     return _icon("Zoommeeting_Icon.png")
    def event_type_key(self) -> str: return "zoom_meeting"


# ─── WindowEvent ──────────────────────────────────────────────

@dataclass
class WindowEvent(Event):
    """기간 기반 이벤트 — 시작(optional) + 마감 (동영상, 과제)"""
    open_at: Optional[str] = None
    due_at: Optional[str] = None

    def sort_at(self) -> Optional[datetime]:
        return datetime.fromisoformat(self.due_at) if self.due_at else None

    def to_dict(self) -> dict:
        d = self._base_dict()
        d.update({"open_at": self.open_at, "due_at": self.due_at})
        return d


@dataclass
class Assignment(WindowEvent):
    def label(self) -> str:         return "과제"
    def icon_path(self) -> str:     return _icon("Assignment_Icon.png")
    def event_type_key(self) -> str: return "assignment"


@dataclass
class VOD(WindowEvent):
    def label(self) -> str:         return "동영상 강의"
    def icon_path(self) -> str:     return _icon("VOD_Icon.png")
    def event_type_key(self) -> str: return "vod"


# ─── DeadlineEvent ────────────────────────────────────────────

@dataclass
class DeadlineEvent(Event):
    """마감 기반 이벤트 — due_at 만 (10종)"""
    due_at: Optional[str] = None

    def sort_at(self) -> Optional[datetime]:
        return datetime.fromisoformat(self.due_at) if self.due_at else None

    def to_dict(self) -> dict:
        d = self._base_dict()
        d.update({"due_at": self.due_at})
        return d


@dataclass
class Poll(DeadlineEvent):
    def label(self) -> str:         return "투표"
    def icon_path(self) -> str:     return _icon("Poll_Icon.png")
    def event_type_key(self) -> str: return "poll"


@dataclass
class Board(DeadlineEvent):
    def label(self) -> str:         return "게시판"
    def icon_path(self) -> str:     return _icon("Board_Icon.png")
    def event_type_key(self) -> str: return "board"


@dataclass
class Survey(DeadlineEvent):
    def label(self) -> str:         return "설문조사"
    def icon_path(self) -> str:     return _icon("Survey_Icon.png")
    def event_type_key(self) -> str: return "survey"


@dataclass
class GroupEvaluation(WindowEvent):
    """조별과제 — 시작(optional) + 마감"""
    def label(self) -> str:         return "조별과제"
    def icon_path(self) -> str:     return _icon("Forum_Icon.png")
    def event_type_key(self) -> str: return "group_evaluation"


@dataclass
class Forum(DeadlineEvent):
    def label(self) -> str:         return "토론방"
    def icon_path(self) -> str:     return _icon("Forum_Icon.png")
    def event_type_key(self) -> str: return "forum"


@dataclass
class Wiki(DeadlineEvent):
    def label(self) -> str:         return "위키"
    def icon_path(self) -> str:     return _icon("Wiki_Icon.png")
    def event_type_key(self) -> str: return "wiki"


@dataclass
class File(DeadlineEvent):
    def label(self) -> str:         return "파일"
    def icon_path(self) -> str:     return _icon("File_Icon.png")
    def event_type_key(self) -> str: return "file"


@dataclass
class Folder(DeadlineEvent):
    def label(self) -> str:         return "폴더"
    def icon_path(self) -> str:     return _icon("Folder_Icon.png")
    def event_type_key(self) -> str: return "folder"


@dataclass
class Label(DeadlineEvent):
    def label(self) -> str:         return "개요"
    def icon_path(self) -> str:     return _icon("Label_Icon.png")
    def event_type_key(self) -> str: return "label"


@dataclass
class URLLink(DeadlineEvent):
    def label(self) -> str:         return "URL링크"
    def icon_path(self) -> str:     return _icon("URL_Icon.png")
    def event_type_key(self) -> str: return "url"


# ─── Lookup maps ──────────────────────────────────────────────

@dataclass
class Exam(PeriodEvent):
    """시험 — 교시 기반 (Quiz와 동일한 입력 방식)"""
    def label(self) -> str:         return "시험"
    def icon_path(self) -> str:     return _icon("Label_Icon.png")
    def event_type_key(self) -> str: return "exam"


EVENT_TYPE_MAP: dict[str, type[Event]] = {
    # ── UI에 표시되는 6개 ──
    "vod":               VOD,
    "zoom_meeting":      ZoomMeeting,
    "assignment":        Assignment,
    "group_evaluation":  GroupEvaluation,
    "quiz":              Quiz,
    "exam":              Exam,
    # ── (UI 미표시) ──
    "poll":              Poll,
    "board":             Board,
    "survey":            Survey,
    "forum":             Forum,
    "wiki":              Wiki,
    "file":              File,
    "folder":            Folder,
    "label":             Label,
    "url":               URLLink,
}

_DUMMY: dict[str, Event] = {
    k: cls(id="", course_code="", title="") for k, cls in EVENT_TYPE_MAP.items()
}
EVENT_LABEL_MAP: dict[str, str] = {k: v.label() for k, v in _DUMMY.items()}
EVENT_ICON_MAP: dict[str, str]  = {k: v.icon_path() for k, v in _DUMMY.items()}

# UI에 표시할 6개 (순서 고정)
VISIBLE_TYPES: list[str] = [
    "vod", "zoom_meeting", "assignment", "group_evaluation", "quiz", "exam",
]

# 전체 타입 (데이터 호환 포함)
ALL_TYPES_ORDER: list[str] = [
    "vod", "zoom_meeting", "assignment", "group_evaluation", "quiz", "exam",
    "poll", "board", "survey", "forum", "wiki", "file", "folder", "label", "url",
]


def event_from_dict(d: dict) -> Optional[Event]:
    from dataclasses import fields as dc_fields
    data = {k: v for k, v in d.items()}
    event_type = data.pop("event_type", None)
    if event_type is None or event_type not in EVENT_TYPE_MAP:
        return None
    cls = EVENT_TYPE_MAP[event_type]
    valid = {f.name for f in dc_fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in valid})


# ─── Rule hierarchy ───────────────────────────────────────────

@dataclass
class Rule:
    id: str
    course_code: str
    event_type: str
    title_template: str         # e.g. "{week}주차 {label}"
    start_date: str             # ISO date "YYYY-MM-DD"
    end_date: str
    enabled: bool = True

    def expand(self, semester_start: str) -> list[Event]:
        raise NotImplementedError

    def rule_pattern(self) -> str:
        raise NotImplementedError

    def to_dict(self) -> dict:
        raise NotImplementedError

    def _base_rule_dict(self) -> dict:
        return {
            "id": self.id,
            "course_code": self.course_code,
            "event_type": self.event_type,
            "title_template": self.title_template,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "enabled": self.enabled,
            "pattern": self.rule_pattern(),
        }


@dataclass
class WindowCycleRule(Rule):
    """과제·동영상: open 요일+교시 → due 요일+주차offset+시각"""
    open_weekday: int = 0       # 0=월
    open_period: int = 1        # 1~8
    due_weekday: int = 0
    due_week_offset: int = 0    # 0=같은주, 1=다음주
    due_time: str = "23:59"

    def rule_pattern(self) -> str: return "window_cycle"

    def to_dict(self) -> dict:
        d = self._base_rule_dict()
        d.update({
            "open_weekday": self.open_weekday,
            "open_period": self.open_period,
            "due_weekday": self.due_weekday,
            "due_week_offset": self.due_week_offset,
            "due_time": self.due_time,
        })
        return d


@dataclass
class PeriodWeeklyRule(Rule):
    """퀴즈·화상강의: 매주 요일+교시구간"""
    occurrence_weekday: int = 0
    start_period: int = 1
    end_period: int = 1

    def rule_pattern(self) -> str: return "period_weekly"

    def to_dict(self) -> dict:
        d = self._base_rule_dict()
        d.update({
            "occurrence_weekday": self.occurrence_weekday,
            "start_period": self.start_period,
            "end_period": self.end_period,
        })
        return d


@dataclass
class DueWeeklyRule(Rule):
    """마감형: 매주 요일+시각"""
    due_weekday: int = 0
    due_time: str = "23:59"

    def rule_pattern(self) -> str: return "due_weekly"

    def to_dict(self) -> dict:
        d = self._base_rule_dict()
        d.update({
            "due_weekday": self.due_weekday,
            "due_time": self.due_time,
        })
        return d


RULE_PATTERN_MAP: dict[str, type[Rule]] = {
    "window_cycle":  WindowCycleRule,
    "period_weekly": PeriodWeeklyRule,
    "due_weekly":    DueWeeklyRule,
}


def rule_from_dict(d: dict) -> Optional[Rule]:
    from dataclasses import fields as dc_fields
    data = {k: v for k, v in d.items()}
    pattern = data.pop("pattern", None)
    if pattern is None or pattern not in RULE_PATTERN_MAP:
        return None
    cls = RULE_PATTERN_MAP[pattern]
    valid = {f.name for f in dc_fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in valid})
