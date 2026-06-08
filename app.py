"""
app.py
이그잼 플래너 - 학생용 통합 일정 관리 앱 (Streamlit 화면 계층)

실행 방법:
    streamlit run app.py

기획서 대응:
  - 수업/과제/시험 일정을 한 곳에서 통합 관리
  - 앱 실행 시 임박한 일정을 자동으로 상단에 표시 (D-day + 임박순 정렬)
  - 월간 캘린더 뷰
  - 일정 입력/저장/조회/수정/삭제 (CSV 저장)
"""

import calendar
from datetime import date, datetime

import streamlit as st

# 데이터/로직은 planner 모듈에 모아 두었습니다. (화면과 로직 분리)
import planner

# ---------------------------------------------------------------------------
# 페이지 기본 설정
# ---------------------------------------------------------------------------
st.set_page_config(page_title="이그잼 플래너", page_icon="📅", layout="wide")

# 종류별 색상/이모지. 캘린더와 목록에서 한눈에 구분되도록 쓰입니다.
CATEGORY_STYLE = {
    "수업": ("🟦", "#3b82f6"),
    "과제": ("🟧", "#f97316"),
    "시험": ("🟥", "#ef4444"),
    "기타": ("⬜", "#9ca3af"),
}


def category_emoji(category: str) -> str:
    """종류 이름을 받아 앞에 붙일 이모지를 돌려줍니다.
    딕셔너리에 없는 값이 들어와도 오류 없이 기본값(⬜)을 쓰도록 했습니다."""
    return CATEGORY_STYLE.get(category, ("⬜", "#9ca3af"))[0]


# ---------------------------------------------------------------------------
# 사이드바: 새 일정 입력 폼
# ---------------------------------------------------------------------------
def render_input_form():
    """왼쪽 사이드바에 일정 입력 폼을 그립니다.
    st.form 으로 묶은 이유: '추가' 버튼을 누르는 순간에만 한 번에 처리되어,
    입력 도중 화면이 계속 새로고침되는 것을 막기 위함입니다."""
    st.sidebar.header("➕ 새 일정 추가")
    with st.sidebar.form("add_form", clear_on_submit=True):
        title = st.text_input("제목", placeholder="예: 컴퓨팅사고 과제 2")
        category = st.selectbox("종류", planner.CATEGORIES)
        due = st.date_input("날짜", value=date.today())
        memo = st.text_area("메모 (선택)", placeholder="제출 형식, 장소 등")
        submitted = st.form_submit_button("추가하기", use_container_width=True)

    if submitted:
        # 제목이 비어 있으면 저장하지 않고 경고만 보여줍니다.
        if not title.strip():
            st.sidebar.warning("제목을 입력해 주세요.")
        else:
            planner.add_schedule(title, category, due.strftime("%Y-%m-%d"), memo)
            st.sidebar.success("일정이 추가되었습니다.")
            st.rerun()  # 화면을 다시 그려 새 일정을 즉시 반영합니다.


# ---------------------------------------------------------------------------
# 상단: 임박한 일정 (D-day + 임박순 정렬)
# ---------------------------------------------------------------------------
def render_urgent(items):
    """완료되지 않은 일정을 임박순으로 정렬해 상단에 보여줍니다.
    기획서의 '앱 실행 즉시 가장 급한 일정을 상단에 표시' 요구사항입니다."""
    st.subheader("🔥 임박한 일정")
    upcoming = planner.sort_by_urgency(items, include_done=False)

    if not upcoming:
        st.info("등록된 일정이 없습니다. 왼쪽에서 일정을 추가해 보세요.")
        return

    # 가장 급한 3개는 큰 카드(metric)로 강조해서 보여줍니다.
    top = upcoming[:3]
    cols = st.columns(len(top))
    for col, s in zip(cols, top):
        n = planner.days_left(s)
        label = planner.dday_label(n)
        # delta 에 D-day 를 넣고, 지난 일정은 빨간색(inverse)으로 표시됩니다.
        col.metric(
            label=f"{category_emoji(s.category)} {s.title}",
            value=label,
            delta=s.due_date,
            delta_color="off",
        )

    # 나머지는 간단한 줄 목록으로 이어서 보여줍니다.
    if len(upcoming) > 3:
        st.markdown("​")  # 약간의 간격
        for s in upcoming[3:]:
            n = planner.days_left(s)
            st.write(f"{category_emoji(s.category)} ~{planner.dday_label(n)}~ "
                     f"· {s.title} ({s.due_date})")


# ---------------------------------------------------------------------------
# 월간 캘린더 뷰
# ---------------------------------------------------------------------------
def render_calendar(items):
    """선택한 연/월의 달력을 표 형태로 그리고, 각 날짜 칸에 그날의 일정을 채웁니다."""
    st.subheader("🗓️ 월간 캘린더")

    # 보고 싶은 연/월을 고르는 컨트롤. 기본값은 이번 달입니다.
    today = date.today()
    c1, c2 = st.columns(2)
    year = c1.number_input("연도", min_value=2000, max_value=2100,
                           value=today.year, step=1)
    month = c2.number_input("월", min_value=1, max_value=12,
                            value=today.month, step=1)
    year, month = int(year), int(month)

    # calendar.monthcalendar 는 해당 월을 '주 단위 리스트'로 돌려줍니다.
    # 각 주는 7칸(월~일)이고, 그 달에 속하지 않는 칸은 0 으로 채워집니다.
    cal = calendar.monthcalendar(year, month)
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]

    # 요일 헤더
    header_cols = st.columns(7)
    for col, wd in zip(header_cols, weekdays):
        col.markdown(f"**{wd}**")

    # 주 단위로 한 줄씩, 그 안에서 7개 칸을 그립니다.
    for week in cal:
        day_cols = st.columns(7)
        for col, day in zip(day_cols, week):
            if day == 0:
                col.write("")  # 이 달에 없는 칸은 비워 둡니다.
                continue

            cell_date = date(year, month, day)
            # 오늘 날짜는 강조 표시
            if cell_date == today:
                col.markdown(f"**🔵 {day}**")
            else:
                col.markdown(f"{day}")

            # 그날에 해당하는 일정들을 이모지+제목으로 표시합니다.
            for s in planner.schedules_on(items, cell_date):
                done_mark = "✅" if s.done else category_emoji(s.category)
                col.caption(f"{done_mark} {s.title}")


# ---------------------------------------------------------------------------
# 전체 목록 + 수정/삭제
# ---------------------------------------------------------------------------
def render_manage(items):
    """모든 일정을 목록으로 보여주고, 각 일정마다 완료/수정/삭제를 할 수 있게 합니다."""
    st.subheader("📋 전체 일정 관리")

    if not items:
        st.info("아직 일정이 없습니다.")
        return

    # 보기 좋게 날짜순으로 정렬해서 보여줍니다(완료 포함).
    for s in planner.sort_by_urgency(items, include_done=True):
        n = planner.days_left(s)
        # 각 일정을 펼침 영역(expander)으로 만들어, 평소엔 한 줄로 깔끔하게 보입니다.
        title_line = (f"{category_emoji(s.category)} {s.title} "
                      f"· {s.due_date} · {planner.dday_label(n)}"
                      + ("  (완료)" if s.done else ""))
        with st.expander(title_line):
            # 수정 입력칸들. 기존 값을 기본값으로 채워 둡니다.
            new_title = st.text_input("제목", value=s.title, key=f"t{s.id}")
            new_cat = st.selectbox(
                "종류", planner.CATEGORIES,
                index=planner.CATEGORIES.index(s.category)
                if s.category in planner.CATEGORIES else 0,
                key=f"c{s.id}",
            )
            new_due = st.date_input("날짜", value=s.due(), key=f"d{s.id}")
            new_memo = st.text_area("메모", value=s.memo, key=f"m{s.id}")
            new_done = st.checkbox("완료함", value=s.done, key=f"k{s.id}")

            b1, b2 = st.columns(2)
            # 저장 버튼: 바뀐 값들을 한 번에 업데이트합니다.
            if b1.button("💾 저장", key=f"save{s.id}", use_container_width=True):
                planner.update_schedule(
                    s.id,
                    title=new_title.strip(),
                    category=new_cat,
                    due_date=new_due.strftime("%Y-%m-%d"),
                    memo=new_memo.strip(),
                    done=new_done,
                )
                st.success("수정되었습니다.")
                st.rerun()
            # 삭제 버튼
            if b2.button("🗑️ 삭제", key=f"del{s.id}", use_container_width=True):
                planner.delete_schedule(s.id)
                st.warning("삭제되었습니다.")
                st.rerun()


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def main():
    st.title("📅 이그잼 플래너")
    st.caption("수업 · 과제 · 시험 일정을 한 곳에서. 가장 급한 일정이 맨 위에.")

    # 매 실행마다 CSV 에서 최신 일정을 읽어옵니다.
    items = planner.load_schedules()

    render_input_form()      # 사이드바 입력 폼
    render_urgent(items)     # 상단 임박 일정
    st.divider()
    render_calendar(items)   # 월간 캘린더
    st.divider()
    render_manage(items)     # 전체 목록 + 수정/삭제


if __name__ == "__main__":
    main()
