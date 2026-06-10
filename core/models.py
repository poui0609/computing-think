from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


def _icon(filename: str) -> str:
    return str(_ICONS_DIR / filename)


COURSE_PALETTE: list[str] = [
    "#4A90D9", "#E67E22", "#2ECC71", "#9B59B6",
    "#E74C3C", "#1ABC9C", "#F39C12", "#3498DB",
    "#D35400", "#27AE60", "#8E44AD", "#C0392B",
]

WEEKDAY_KO: list[str] = ["월", "화", "수", "목", "금", "토", "일"]

DOMAIN_LABEL: dict[str, str] = {
    "course":   "수업",
    "academic": "학사",
    "personal": "개인",
}


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


@dataclass
class Event:
    id: str
    title: str
    domain: str = "course"          # "course" | "academic" | "personal"
    course_code: str = ""           # 수업 Event만 필수
    description: str = ""
    source: str = "manual"          # "manual" | "rule"
    rule_id: Optional[str] = None
    week_number: Optional[int] = None
    progress: int = 0
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
            "id":          self.id,
            "domain":      self.domain,
            "event_type":  self.event_type_key(),
            "title":       self.title,
            "course_code": self.course_code,
            "description": self.description,
            "source":      self.source,
            "rule_id":     self.rule_id,
            "week_number": self.week_number,
            "progress":    self.progress,
            "completed":   self.completed,
            "created_at":  self.created_at,
        }

    def to_dict(self) -> dict:
        return self._base_dict()


@dataclass
class PeriodEvent(Event):
    """교시 기반 — 교시(period) 번호로 시각을 특정한다."""
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    start_period: Optional[int] = None
    end_period: Optional[int] = None

    def sort_at(self) -> Optional[datetime]:
        return datetime.fromisoformat(self.start_at) if self.start_at else None

    def to_dict(self) -> dict:
        d = self._base_dict()
        d.update({
            "start_at":     self.start_at,
            "end_at":       self.end_at,
            "start_period": self.start_period,
            "end_period":   self.end_period,
        })
        return d


@dataclass
class DeadlineEvent(Event):
    """마감 기반 — open_at(선택) + due_at(필수)."""
    open_at: Optional[str] = None
    due_at: Optional[str] = None

    def sort_at(self) -> Optional[datetime]:
        return datetime.fromisoformat(self.due_at) if self.due_at else None

    def to_dict(self) -> dict:
        d = self._base_dict()
        d.update({"open_at": self.open_at, "due_at": self.due_at})
        return d


@dataclass
class RangeEvent(Event):
    """자유 구간 — start_at + end_at 모두 지정."""
    start_at: Optional[str] = None
    end_at: Optional[str] = None

    def sort_at(self) -> Optional[datetime]:
        return datetime.fromisoformat(self.start_at) if self.start_at else None

    def to_dict(self) -> dict:
        d = self._base_dict()
        d.update({"start_at": self.start_at, "end_at": self.end_at})
        return d


@dataclass
class OpenEvent(Event):
    """오픈형 — start_at만 있고 종료·마감 시각이 없다."""
    start_at: Optional[str] = None

    def sort_at(self) -> Optional[datetime]:
        return datetime.fromisoformat(self.start_at) if self.start_at else None

    def to_dict(self) -> dict:
        d = self._base_dict()
        d.update({"start_at": self.start_at})
        return d


@dataclass
class Quiz(PeriodEvent):
    def __post_init__(self): self.domain = "course"
    def label(self) -> str:          return "퀴즈"
    def icon_path(self) -> str:      return _icon("Quiz_Icon.png")
    def event_type_key(self) -> str: return "quiz"


@dataclass
class Exam(PeriodEvent):
    def __post_init__(self): self.domain = "course"
    def label(self) -> str:          return "시험"
    def icon_path(self) -> str:      return _icon("Label_Icon.png")
    def event_type_key(self) -> str: return "exam"


@dataclass
class ZoomMeeting(PeriodEvent):
    def __post_init__(self): self.domain = "course"
    def label(self) -> str:          return "화상 강의"
    def icon_path(self) -> str:      return _icon("Zoommeeting_Icon.png")
    def event_type_key(self) -> str: return "zoom_meeting"


@dataclass
class VOD(DeadlineEvent):
    def __post_init__(self): self.domain = "course"
    def label(self) -> str:          return "동영상 강의"
    def icon_path(self) -> str:      return _icon("VOD_Icon.png")
    def event_type_key(self) -> str: return "vod"


@dataclass
class Assignment(DeadlineEvent):
    def __post_init__(self): self.domain = "course"
    def label(self) -> str:          return "과제"
    def icon_path(self) -> str:      return _icon("Assignment_Icon.png")
    def event_type_key(self) -> str: return "assignment"


@dataclass
class TeamProject(DeadlineEvent):
    def __post_init__(self): self.domain = "course"
    def label(self) -> str:          return "조별과제"
    def icon_path(self) -> str:      return _icon("Forum_Icon.png")
    def event_type_key(self) -> str: return "team_project"


@dataclass
class Poll(DeadlineEvent):
    def label(self) -> str:          return "투표"
    def icon_path(self) -> str:      return _icon("Poll_Icon.png")
    def event_type_key(self) -> str: return "poll"


@dataclass
class Board(DeadlineEvent):
    def label(self) -> str:          return "게시판"
    def icon_path(self) -> str:      return _icon("Board_Icon.png")
    def event_type_key(self) -> str: return "board"


@dataclass
class Survey(DeadlineEvent):
    def label(self) -> str:          return "설문조사"
    def icon_path(self) -> str:      return _icon("Survey_Icon.png")
    def event_type_key(self) -> str: return "survey"


@dataclass
class Forum(DeadlineEvent):
    def label(self) -> str:          return "토론방"
    def icon_path(self) -> str:      return _icon("Forum_Icon.png")
    def event_type_key(self) -> str: return "forum"


@dataclass
class Wiki(DeadlineEvent):
    def label(self) -> str:          return "위키"
    def icon_path(self) -> str:      return _icon("Wiki_Icon.png")
    def event_type_key(self) -> str: return "wiki"


@dataclass
class File(DeadlineEvent):
    def label(self) -> str:          return "파일"
    def icon_path(self) -> str:      return _icon("File_Icon.png")
    def event_type_key(self) -> str: return "file"


@dataclass
class Folder(DeadlineEvent):
    def label(self) -> str:          return "폴더"
    def icon_path(self) -> str:      return _icon("Folder_Icon.png")
    def event_type_key(self) -> str: return "folder"


@dataclass
class Label(DeadlineEvent):
    def label(self) -> str:          return "개요"
    def icon_path(self) -> str:      return _icon("Label_Icon.png")
    def event_type_key(self) -> str: return "label"


@dataclass
class URLLink(DeadlineEvent):
    def label(self) -> str:          return "URL링크"
    def icon_path(self) -> str:      return _icon("URL_Icon.png")
    def event_type_key(self) -> str: return "url"


WindowEvent = DeadlineEvent


@dataclass
class Seminar(RangeEvent):
    def __post_init__(self): self.domain = "academic"
    def label(self) -> str:          return "세미나"
    def icon_path(self) -> str:      return _icon("Board_Icon.png")
    def event_type_key(self) -> str: return "seminar"


@dataclass
class Exhibition(RangeEvent):
    def __post_init__(self): self.domain = "academic"
    def label(self) -> str:          return "전시/박람회"
    def icon_path(self) -> str:      return _icon("Poll_Icon.png")
    def event_type_key(self) -> str: return "exhibition"


@dataclass
class OfficialEvent(RangeEvent):
    def __post_init__(self): self.domain = "academic"
    def label(self) -> str:          return "학사 행사"
    def icon_path(self) -> str:      return _icon("Survey_Icon.png")
    def event_type_key(self) -> str: return "official_event"


@dataclass
class DeptCompetition(DeadlineEvent):
    def __post_init__(self): self.domain = "academic"
    def label(self) -> str:          return "교내 대회"
    def icon_path(self) -> str:      return _icon("Quiz_Icon.png")
    def event_type_key(self) -> str: return "dept_competition"


@dataclass
class ExamPrep(RangeEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "시험 공부"
    def icon_path(self) -> str:      return _icon("Label_Icon.png")
    def event_type_key(self) -> str: return "exam_prep"


@dataclass
class QuizPrep(RangeEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "퀴즈 대비"
    def icon_path(self) -> str:      return _icon("Quiz_Icon.png")
    def event_type_key(self) -> str: return "quiz_prep"


@dataclass
class SelfStudy(RangeEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "자습"
    def icon_path(self) -> str:      return _icon("VOD_Icon.png")
    def event_type_key(self) -> str: return "self_study"


@dataclass
class Club(RangeEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "동아리"
    def icon_path(self) -> str:      return _icon("Forum_Icon.png")
    def event_type_key(self) -> str: return "club"


@dataclass
class Volunteer(RangeEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "봉사"
    def icon_path(self) -> str:      return _icon("Survey_Icon.png")
    def event_type_key(self) -> str: return "volunteer"


@dataclass
class ExtCompetition(RangeEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "외부 대회"
    def icon_path(self) -> str:      return _icon("Assignment_Icon.png")
    def event_type_key(self) -> str: return "ext_competition"


@dataclass
class PersonalCustom(RangeEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "기타"
    def icon_path(self) -> str:      return _icon("Folder_Icon.png")
    def event_type_key(self) -> str: return "personal_custom"


@dataclass
class PersonalGoal(OpenEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "개인 목표"
    def icon_path(self) -> str:      return _icon("Label_Icon.png")
    def event_type_key(self) -> str: return "personal_goal"


@dataclass
class StudyPlan(OpenEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "학습 계획"
    def icon_path(self) -> str:      return _icon("VOD_Icon.png")
    def event_type_key(self) -> str: return "study_plan"


@dataclass
class Habit(OpenEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "습관"
    def icon_path(self) -> str:      return _icon("Survey_Icon.png")
    def event_type_key(self) -> str: return "habit"


@dataclass
class PersonalOpenCustom(OpenEvent):
    def __post_init__(self): self.domain = "personal"
    def label(self) -> str:          return "기타(오픈)"
    def icon_path(self) -> str:      return _icon("Folder_Icon.png")
    def event_type_key(self) -> str: return "personal_open_custom"


EVENT_TYPE_MAP: dict[str, type[Event]] = {
    # ── 수업 UI 6종 ──
    "vod":              VOD,
    "zoom_meeting":     ZoomMeeting,
    "assignment":       Assignment,
    "team_project":     TeamProject,
    "quiz":             Quiz,
    "exam":             Exam,
    # ── 수업 레거시 (데이터 호환) ──
    "group_evaluation": TeamProject,
    "poll":             Poll,
    "board":            Board,
    "survey":           Survey,
    "forum":            Forum,
    "wiki":             Wiki,
    "file":             File,
    "folder":           Folder,
    "label":            Label,
    "url":              URLLink,
    # ── 학사 ──
    "seminar":          Seminar,
    "exhibition":       Exhibition,
    "official_event":   OfficialEvent,
    "dept_competition": DeptCompetition,
    # ── 개인 구간형 ──
    "exam_prep":            ExamPrep,
    "quiz_prep":            QuizPrep,
    "self_study":           SelfStudy,
    "club":                 Club,
    "volunteer":            Volunteer,
    "ext_competition":      ExtCompetition,
    "personal_custom":      PersonalCustom,
    # ── 개인 오픈형 ──
    "personal_goal":        PersonalGoal,
    "study_plan":           StudyPlan,
    "habit":                Habit,
    "personal_open_custom": PersonalOpenCustom,
}

# 레이블·아이콘 조회용 (내부 구현 세부사항)
_DUMMY: dict[str, Event] = {
    k: cls(id="", title="") for k, cls in EVENT_TYPE_MAP.items()
}
EVENT_LABEL_MAP: dict[str, str] = {k: v.label()     for k, v in _DUMMY.items()}
EVENT_ICON_MAP:  dict[str, str] = {k: v.icon_path() for k, v in _DUMMY.items()}

# ── 도메인별 UI 표시 타입 목록 (순서 = 화면 배치 순서) ─────────

COURSE_TYPES: list[str] = [
    "vod", "zoom_meeting", "assignment", "team_project", "quiz", "exam",
]
ACADEMIC_TYPES: list[str] = [
    "seminar", "exhibition", "official_event", "dept_competition",
]
PERSONAL_TYPES: list[str] = [
    "exam_prep", "quiz_prep", "self_study",
    "club", "volunteer", "ext_competition", "personal_custom",
    "personal_goal", "study_plan", "habit", "personal_open_custom",
]
PERSONAL_OPEN_TYPES: list[str] = [
    "personal_goal", "study_plan", "habit", "personal_open_custom",
]

ALL_TYPES_ORDER: list[str] = (
    COURSE_TYPES + ACADEMIC_TYPES + PERSONAL_TYPES
    + ["poll", "board", "survey", "forum", "wiki", "file", "folder", "label", "url"]
)

VISIBLE_TYPES: list[str] = COURSE_TYPES

# ── 자동 완료 대상 타입 ─────────────────────────────────────
# 시간이 지나면 자동으로 완료 처리되며, 수동 진행률/완료 컨트롤을 표시하지 않는다.
# 주차 Progress 집계에도 포함되지 않는다.
TIMED_EVENT_TYPES: frozenset[str] = frozenset({
    "quiz", "exam", "zoom_meeting",            # 수업 — 교시형
    "seminar", "exhibition", "official_event", # 학사 — 행사형
})


def event_from_dict(d: dict) -> Optional[Event]:
    from dataclasses import fields as dc_fields
    data       = dict(d)
    event_type = data.pop("event_type", None)
    if event_type is None or event_type not in EVENT_TYPE_MAP:
        return None
    cls    = EVENT_TYPE_MAP[event_type]
    valid  = {f.name for f in dc_fields(cls)}
    obj    = cls(**{k: v for k, v in data.items() if k in valid})
    # JSON에 domain이 명시돼 있으면 __post_init__ 기본값을 덮어쓴다
    if "domain" in data and "domain" in valid:
        obj.domain = data["domain"]
    return obj


def is_timed(event: Event) -> bool:
    """교시형·행사형처럼 종료 시각이 지나면 자동 완료되는 이벤트인지 확인."""
    return event.event_type_key() in TIMED_EVENT_TYPES


def timed_auto_done(event: Event) -> bool:
    """is_timed(event)가 True이고 종료 시각(end_at)이 현재보다 이전이면 True.
    end_at이 없으면 start_at 기준으로 판단한다."""
    if not is_timed(event):
        return False
    end = getattr(event, "end_at", None) or getattr(event, "start_at", None)
    if not end:
        return False
    return datetime.fromisoformat(end) < datetime.now()


@dataclass
class Rule:
    id: str
    course_code: str
    event_type: str
    title_template: str
    start_date: str
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
            "id":             self.id,
            "course_code":    self.course_code,
            "event_type":     self.event_type,
            "title_template": self.title_template,
            "start_date":     self.start_date,
            "end_date":       self.end_date,
            "enabled":        self.enabled,
            "pattern":        self.rule_pattern(),
        }


@dataclass
class WindowCycleRule(Rule):
    """주기적으로 open → due 구간이 반복되는 규칙 (VOD·과제 등)."""
    open_weekday:    int = 0
    open_period:     int = 1
    due_weekday:     int = 0
    due_week_offset: int = 0
    due_time:        str = "23:59"

    def rule_pattern(self) -> str: return "window_cycle"

    def to_dict(self) -> dict:
        d = self._base_rule_dict()
        d.update({
            "open_weekday":    self.open_weekday,
            "open_period":     self.open_period,
            "due_weekday":     self.due_weekday,
            "due_week_offset": self.due_week_offset,
            "due_time":        self.due_time,
        })
        return d


@dataclass
class PeriodWeeklyRule(Rule):
    """매주 특정 요일·교시에 반복되는 규칙 (퀴즈·시험·화상강의)."""
    occurrence_weekday: int = 0
    start_period:       int = 1
    end_period:         int = 1

    def rule_pattern(self) -> str: return "period_weekly"

    def to_dict(self) -> dict:
        d = self._base_rule_dict()
        d.update({
            "occurrence_weekday": self.occurrence_weekday,
            "start_period":       self.start_period,
            "end_period":         self.end_period,
        })
        return d


@dataclass
class DueWeeklyRule(Rule):
    """매주 특정 요일 마감이 반복되는 규칙."""
    due_weekday: int = 0
    due_time:    str = "23:59"

    def rule_pattern(self) -> str: return "due_weekly"

    def to_dict(self) -> dict:
        d = self._base_rule_dict()
        d.update({
            "due_weekday": self.due_weekday,
            "due_time":    self.due_time,
        })
        return d


RULE_PATTERN_MAP: dict[str, type[Rule]] = {
    "window_cycle":  WindowCycleRule,
    "period_weekly": PeriodWeeklyRule,
    "due_weekly":    DueWeeklyRule,
}


def rule_from_dict(d: dict) -> Optional[Rule]:
    """JSON dict → Rule 인스턴스. 알 수 없는 pattern이면 None 반환."""
    from dataclasses import fields as dc_fields
    data    = dict(d)
    pattern = data.pop("pattern", None)
    if pattern is None or pattern not in RULE_PATTERN_MAP:
        return None
    cls   = RULE_PATTERN_MAP[pattern]
    valid = {f.name for f in dc_fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in valid})
