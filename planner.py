"""
planner.py
이그잼 플래너의 데이터/로직 계층.

이 파일은 화면(UI)과 분리되어 있습니다. 그 이유는:
  - 일정 저장/계산 같은 핵심 로직을 UI 없이도 단독으로 테스트할 수 있고,
  - 나중에 다른 화면(예: Tkinter, CLI)으로 바꿔도 이 로직을 그대로 재사용할 수 있기 때문입니다.

저장 방식: CSV 파일 (기획서의 "파이썬 기반 + CSV 설계" 요구사항을 따름)
"""

import csv
import os
from dataclasses import dataclass, asdict
from datetime import date, datetime

# CSV 파일 경로. 이 모듈 파일이 있는 폴더 기준으로 schedules.csv 를 사용합니다.
# __file__ 을 기준으로 잡는 이유: 앱을 어느 위치에서 실행하더라도
# 항상 같은 데이터 파일을 가리키게 하기 위함입니다.
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedules.csv")

# CSV 의 열(헤더) 구성. 일정 한 건이 가지는 필드들입니다.
FIELDNAMES = ["id", "title", "category", "due_date", "memo", "done"]

# 일정의 종류. 기획서의 "수업/과제/시험" 통합 관리에 대응합니다.
CATEGORIES = ["수업", "과제", "시험", "기타"]


@dataclass
class Schedule:
    """일정 한 건을 표현하는 데이터 구조.

    dataclass 를 쓴 이유: 필드가 명확하게 보이고, 딕셔너리 변환(asdict)이
    자동으로 되어 CSV 저장이 간단해지기 때문입니다.
    """
    id: int
    title: str          # 일정 제목 (예: "자료구조 과제 1")
    category: str       # 종류 (수업/과제/시험/기타)
    due_date: str       # 마감/일정 날짜, "YYYY-MM-DD" 문자열로 저장
    memo: str = ""      # 메모 (선택)
    done: bool = False  # 완료 여부

    def due(self) -> date:
        """문자열 날짜를 date 객체로 변환해서 돌려줍니다.
        날짜 계산(D-day)은 date 객체로 해야 정확하기 때문입니다."""
        return datetime.strptime(self.due_date, "%Y-%m-%d").date()


def _ensure_file():
    """CSV 파일이 없으면 헤더만 있는 빈 파일을 새로 만듭니다.
    첫 실행 시 파일이 없어서 나는 오류를 막기 위한 안전장치입니다."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def load_schedules() -> list[Schedule]:
    """CSV 파일을 읽어 Schedule 객체 리스트로 돌려줍니다."""
    _ensure_file()
    items: list[Schedule] = []
    with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # CSV 는 모든 값을 문자열로 읽기 때문에, id 는 정수로,
            # done 은 불리언으로 직접 변환해 줘야 합니다.
            items.append(
                Schedule(
                    id=int(row["id"]),
                    title=row["title"],
                    category=row["category"],
                    due_date=row["due_date"],
                    memo=row.get("memo", ""),
                    done=row.get("done", "False") == "True",
                )
            )
    return items


def save_schedules(items: list[Schedule]):
    """Schedule 리스트 전체를 CSV 파일에 덮어씁니다.
    (간단함을 위해 일부만 고치지 않고 매번 전체를 다시 씁니다.
     일정 개수가 많지 않은 학생 일정 관리 용도라 이 방식으로 충분합니다.)"""
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))


def _next_id(items: list[Schedule]) -> int:
    """새 일정에 부여할 id 를 정합니다.
    기존 id 중 가장 큰 값 + 1 을 써서 중복을 피합니다.
    목록이 비어 있으면 1 부터 시작합니다."""
    return (max((s.id for s in items), default=0)) + 1


def add_schedule(title: str, category: str, due_date: str, memo: str = "") -> Schedule:
    """일정을 새로 추가하고 저장합니다. 추가된 일정을 돌려줍니다."""
    items = load_schedules()
    new_item = Schedule(
        id=_next_id(items),
        title=title.strip(),
        category=category,
        due_date=due_date,
        memo=memo.strip(),
        done=False,
    )
    items.append(new_item)
    save_schedules(items)
    return new_item


def update_schedule(sid: int, **fields) -> bool:
    """id 가 sid 인 일정의 일부 필드를 수정합니다.
    찾아서 고쳤으면 True, 못 찾았으면 False 를 돌려줍니다.

    **fields 를 쓴 이유: 제목만, 또는 날짜만 등 원하는 항목만 골라
    수정할 수 있게 하기 위함입니다."""
    items = load_schedules()
    found = False
    for s in items:
        if s.id == sid:
            for key, value in fields.items():
                if hasattr(s, key):
                    setattr(s, key, value)
            found = True
            break
    if found:
        save_schedules(items)
    return found


def delete_schedule(sid: int) -> bool:
    """id 가 sid 인 일정을 삭제합니다. 삭제 성공 시 True."""
    items = load_schedules()
    new_items = [s for s in items if s.id != sid]
    if len(new_items) == len(items):
        return False  # 삭제된 게 없음 = 해당 id 없음
    save_schedules(new_items)
    return True


def days_left(schedule: Schedule, today: date | None = None) -> int:
    """D-day 를 계산합니다. 오늘부터 마감일까지 남은 '일수'입니다.
      - 양수: 아직 남음 (예: 3 → D-3)
      - 0   : 오늘이 마감 (D-day)
      - 음수: 이미 지남 (예: -2 → D+2)

    today 를 인자로 받는 이유: 테스트할 때 '오늘'을 고정해서
    결과를 검증할 수 있게 하기 위함입니다. 평소에는 비워두면 실제 오늘을 씁니다."""
    if today is None:
        today = date.today()
    return (schedule.due() - today).days


def dday_label(n: int) -> str:
    """남은 일수(정수)를 'D-3', 'D-DAY', 'D+2' 같은 표시 문자열로 바꿉니다."""
    if n > 0:
        return f"D-{n}"
    elif n == 0:
        return "D-DAY"
    else:
        return f"D+{abs(n)}"


def sort_by_urgency(items: list[Schedule], today: date | None = None,
                    include_done: bool = False) -> list[Schedule]:
    """임박한 순서대로 정렬합니다. (기획서의 핵심 알고리즘)

    정렬 기준:
      1) 완료된 일정은 기본적으로 제외 (include_done=True 면 포함)
      2) 남은 일수가 적은 순(=마감이 가까운 순)으로 오름차순 정렬

    즉, 앱을 켜면 가장 급한 일정이 맨 위로 올라옵니다."""
    target = items if include_done else [s for s in items if not s.done]
    # key 로 days_left 를 주면 '남은 일수'가 작은 것부터 정렬됩니다.
    return sorted(target, key=lambda s: days_left(s, today))


def schedules_on(items: list[Schedule], target_day: date) -> list[Schedule]:
    """특정 날짜에 해당하는 일정만 골라 돌려줍니다.
    월간 캘린더에서 각 날짜 칸을 채울 때 사용합니다."""
    return [s for s in items if s.due() == target_day]
