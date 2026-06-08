"""
app.py
이그잼 플래너 - 학생용 통합 일정 관리 앱 (Streamlit 화면 계층 / 모바일 친화 버전)

실행: streamlit run app.py

모바일 친화 설계 요점:
  - layout 을 'centered'(기본)로 두어 좁은 폰 화면에 맞춤 (wide 미사용)
  - 사이드바 대신 화면을 '탭'으로 구성 → 한 번에 한 화면만 보임
  - 입력 폼을 본문(추가 탭)으로 빼서 햄버거 메뉴에 숨지 않게 함
  - 월간 캘린더를 7칸 격자 대신 '날짜 목록형'으로 → 폰에서 찌그러지지 않음
  - 가로 정렬(컬럼) 최소화 → 항목을 위에서 아래로 세로 나열

기획서 대응(기능은 그대로):
  수업/과제/시험 통합 관리 · D-day + 임박순 정렬 · 캘린더 · 입력/수정/삭제 (CSV)
"""

import calendar
from datetime import date

import streamlit as st

import planner  # 데이터/로직 (CSV 저장, D-day 계산, 정렬)

# centered 레이아웃: 폰처럼 좁은 화면에서 내용이 가운데로 모여 읽기 좋습니다.
st.set_page_config(page_title="이그잼 플래너", page_icon="📅", layout="centered")

# 종류별 이모지. 목록에서 한눈에 종류를 구분하기 위함입니다.
CATEGORY_EMOJI = {"수업": "🟦", "과제": "🟧", "시험": "🟥", "기타": "⬜"}


def emoji(category: str) -> str:
    """종류 이름 → 이모지. 없는 값이 와도 기본값(⬜)으로 안전하게 처리."""
    return CATEGORY_EMOJI.get(category, "⬜")


def dday_badge(n: int) -> str:
    """남은 일수를 색이 들어간 배지 문자열로. 모바일에서 급한 정도가 바로 보이게 함.
      - 0~2일: 빨강(매우 급함) / 3~6일: 주황 / 그 외: 회색 / 지난 일정: 빨강"""
    label = planner.dday_label(n)
    if n < 0:
        color = "#9ca3af"          # 지난 일정은 흐리게
    elif n <= 2:
        color = "#ef4444"          # 임박: 빨강
    elif n <= 6:
        color = "#f97316"          # 주의: 주황
    else:
        color = "#3b82f6"          # 여유: 파랑
    # st.markdown(unsafe_allow_html=True) 로 색 배지를 그립니다.
    return (f"<span style='background:{color};color:white;padding:2px 8px;"
            f"border-radius:10px;font-size:0.8rem;font-weight:600'>{label}</span>")


# ---------------------------------------------------------------------------
# 탭 1: 임박한 일정
# ---------------------------------------------------------------------------
def tab_urgent(items):
    """완료 안 된 일정을 임박순으로 세로 나열. (앱 핵심: 급한 게 맨 위)"""
    st.subheader("🔥 임박한 일정")
    upcoming = planner.sort_by_urgency(items, include_done=False)

    if not upcoming:
        st.info("일정이 없습니다. '추가' 탭에서 일정을 등록해 보세요.")
        return

    # 카드 하나를 세로로 쌓습니다. 가로 컬럼을 쓰지 않아 폰에서 안 찌그러집니다.
    for s in upcoming:
        n = planner.days_left(s)
        with st.container(border=True):
            st.markdown(
                f"{emoji(s.category)} **{s.title}**　{dday_badge(n)}",
                unsafe_allow_html=True,
            )
            st.caption(f"{s.category} · {s.due_date}"
                       + (f" · {s.memo}" if s.memo else ""))


# ---------------------------------------------------------------------------
# 탭 2: 캘린더 (목록형)
# ---------------------------------------------------------------------------
def tab_calendar(items):
    """선택한 연/월의 일정을 '날짜순 목록'으로 보여줍니다.
    7칸 달력 격자 대신 목록형이라 좁은 폰 화면에서도 잘 읽힙니다."""
    st.subheader("🗓️ 캘린더")

    today = date.today()
    # 연/월 선택. 가로 2칸 정도는 폰에서도 무리 없습니다.
    c1, c2 = st.columns(2)
    year = int(c1.number_input("연도", 2000, 2100, today.year, 1))
    month = int(c2.number_input("월", 1, 12, today.month, 1))

    # 이 달의 모든 일정을 모아 날짜순으로 정렬합니다.
    month_items = [s for s in items
                   if s.due().year == year and s.due().month == month]
    month_items.sort(key=lambda s: s.due())

    # 이 달에 일정이 며칠에 있는지 헤더로 요약해 줍니다.
    month_name = f"{year}년 {month}월"
    if not month_items:
        st.info(f"{month_name}에는 등록된 일정이 없습니다.")
        return

    st.caption(f"{month_name} · 총 {len(month_items)}건")

    # 같은 날짜끼리 묶어, 날짜 제목 아래에 그날 일정들을 나열합니다.
    last_day = None
    for s in month_items:
        d = s.due()
        if d != last_day:
            # 새 날짜가 시작될 때만 날짜 제목을 출력합니다.
            weekday = ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]
            today_mark = " 🔵 (오늘)" if d == today else ""
            st.markdown(f"**{d.day}일 ({weekday}){today_mark}**")
            last_day = d
        n = planner.days_left(s)
        done = "✅ " if s.done else ""
        st.markdown(
            f"　{done}{emoji(s.category)} {s.title}　{dday_badge(n)}",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# 탭 3: 전체 관리 (수정/삭제)
# ---------------------------------------------------------------------------
def tab_manage(items):
    """모든 일정을 펼침 영역으로 보여주고 수정/삭제/완료 처리."""
    st.subheader("📋 전체 관리")

    if not items:
        st.info("아직 일정이 없습니다.")
        return

    for s in planner.sort_by_urgency(items, include_done=True):
        n = planner.days_left(s)
        head = (f"{emoji(s.category)} {s.title} · {planner.dday_label(n)}"
                + ("  ✅" if s.done else ""))
        with st.expander(head):
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

            # 버튼은 가로 2칸. 폰에서도 두 버튼 정도는 무난합니다.
            b1, b2 = st.columns(2)
            if b1.button("💾 저장", key=f"save{s.id}", use_container_width=True):
                planner.update_schedule(
                    s.id, title=new_title.strip(), category=new_cat,
                    due_date=new_due.strftime("%Y-%m-%d"),
                    memo=new_memo.strip(), done=new_done,
                )
                st.success("수정되었습니다.")
                st.rerun()
            if b2.button("🗑️ 삭제", key=f"del{s.id}", use_container_width=True):
                planner.delete_schedule(s.id)
                st.warning("삭제되었습니다.")
                st.rerun()


# ---------------------------------------------------------------------------
# 탭 4: 새 일정 추가
# ---------------------------------------------------------------------------
def tab_add():
    """입력 폼을 본문에 배치(사이드바 X)해, 폰에서 바로 보이고 입력하기 쉽게 함."""
    st.subheader("➕ 새 일정 추가")
    with st.form("add_form", clear_on_submit=True):
        title = st.text_input("제목", placeholder="예: 컴퓨팅사고 과제 2")
        category = st.selectbox("종류", planner.CATEGORIES)
        due = st.date_input("날짜", value=date.today())
        memo = st.text_area("메모 (선택)", placeholder="제출 형식, 장소 등")
        submitted = st.form_submit_button("추가하기", use_container_width=True)

    if submitted:
        if not title.strip():
            st.warning("제목을 입력해 주세요.")
        else:
            planner.add_schedule(title, category, due.strftime("%Y-%m-%d"), memo)
            st.success("추가되었습니다. 다른 탭에서 확인하세요.")


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def main():
    st.title("📅 이그잼 플래너")
    st.caption("수업·과제·시험을 한 곳에서. 급한 일정이 맨 위에.")

    items = planner.load_schedules()  # 매 실행 시 최신 데이터 로드

    # 탭으로 화면 분리 → 폰에서 한 번에 한 화면만 보임
    t1, t2, t3, t4 = st.tabs(["🔥 임박", "🗓️ 캘린더", "📋 관리", "➕ 추가"])
    with t1:
        tab_urgent(items)
    with t2:
        tab_calendar(items)
    with t3:
        tab_manage(items)
    with t4:
        tab_add()


if __name__ == "__main__":
    main()
