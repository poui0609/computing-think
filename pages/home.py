"""pages/home.py — 홈 · D-day + 주차 Progress"""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from core.storage import (
    load, set_event_progress, toggle_event_completed,
    get_course_map, current_week_number,
)


# ─── 진행률/완료 on_change 콜백 ────────────────────────────────

def _cb_home_done(event_id: str) -> None:
    done = st.session_state[f"home_done_{event_id}"]
    evt  = toggle_event_completed(event_id, done)
    st.session_state[f"home_prog_{event_id}"] = evt.progress


def _cb_home_prog(event_id: str) -> None:
    prog = st.session_state[f"home_prog_{event_id}"]
    evt  = set_event_progress(event_id, prog)
    st.session_state[f"home_done_{event_id}"] = evt.completed
from core.dday import calc_dday, dday_label, dday_color
from core.progress import progress_color, progress_bar_html, course_week_progress
from core.models import PeriodEvent, WindowEvent


def _time_info(event) -> str:
    if isinstance(event, PeriodEvent) and event.start_at:
        start = datetime.fromisoformat(event.start_at)
        end   = datetime.fromisoformat(event.end_at) if event.end_at else start
        period_str = (
            f" ({event.start_period}~{event.end_period}교시)"
            if event.start_period else ""
        )
        return f"{start.strftime('%m/%d(%a)')} {start.strftime('%H:%M')}~{end.strftime('%H:%M')}{period_str}"
    elif isinstance(event, WindowEvent):
        due = datetime.fromisoformat(event.due_at).strftime("%m/%d(%a) %H:%M") if event.due_at else "?"
        if event.open_at:
            op = datetime.fromisoformat(event.open_at).strftime("%m/%d %H:%M")
            return f"{op} ~ {due}"
        return f"~ {due}"
    elif hasattr(event, "due_at") and event.due_at:
        return f"~ {datetime.fromisoformat(event.due_at).strftime('%m/%d(%a) %H:%M')}"
    return ""


def _event_card(event, course_map: dict, today: date) -> None:
    course = course_map.get(event.course_code)
    cname  = course.name  if course else event.course_code
    ccolor = course.color if course else "#999"

    dday  = calc_dday(event, today)
    color = progress_color(event.progress)

    with st.container(border=True):
        col_icon, col_info, col_badge = st.columns([0.5, 6, 1.8])
        with col_icon:
            st.image(event.icon_path(), width=32)
        with col_info:
            done_style = "text-decoration:line-through; color:#aaa;" if event.completed else ""
            st.markdown(
                f'<span style="font-size:12px; color:{ccolor}; font-weight:bold;">[{cname}]</span> '
                f'<span style="font-size:14px; {done_style}">{event.title}</span>',
                unsafe_allow_html=True,
            )
            st.caption(_time_info(event))
            st.markdown(progress_bar_html(event.progress, height=5), unsafe_allow_html=True)
        with col_badge:
            if dday is not None:
                bc = dday_color(dday)
                st.markdown(
                    f'<div style="text-align:center;">'
                    f'<span style="background:{bc}; color:white; padding:3px 10px; '
                    f'border-radius:12px; font-weight:bold; font-size:13px;">{dday_label(dday)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.checkbox(
                "완료", value=event.completed,
                key=f"home_done_{event.id}",
                on_change=_cb_home_done, args=(event.id,),
            )

        st.slider(
            "진행률", 0, 100, event.progress,
            key=f"home_prog_{event.id}",
            format="%d%%",
            label_visibility="collapsed",
            on_change=_cb_home_prog, args=(event.id,),
        )


def run():
    st.title("이그잼 플래너")

    data     = load()
    today    = date.today()
    course_map = get_course_map(data)

    if not data.courses:
        st.info("수강 과목을 먼저 등록하세요. → **수강 과목** 페이지")
        return

    # ── 주차 Progress ─────────────────────────────────────────
    cur_week = current_week_number(today)
    max_week = (
        (date.fromisoformat(data.semester["end_date"]) -
         date.fromisoformat(data.semester["start_date"])).days // 7 + 1
    )

    st.subheader("이번 주 진행률")
    col_week, _ = st.columns([2, 5])
    with col_week:
        sel_week = st.number_input(
            "주차 선택",
            min_value=1,
            max_value=max_week,
            value=cur_week,
            key="home_week_sel",
            label_visibility="collapsed",
        )
    st.caption(f"**{sel_week}주차** 과목별 진행률")

    for course in data.courses:
        pct = course_week_progress(data.events, course.code, sel_week)
        col_name, col_bar = st.columns([2, 5])
        with col_name:
            st.markdown(
                f'<span style="color:{course.color}; font-weight:bold;">{course.name}</span>',
                unsafe_allow_html=True,
            )
        with col_bar:
            st.markdown(progress_bar_html(pct, height=8), unsafe_allow_html=True)

    st.divider()

    # Filter
    with st.expander("필터"):
        fc1, fc2 = st.columns(2)
        with fc1:
            sel_courses = st.multiselect(
                "과목 필터",
                options=[c.code for c in data.courses],
                format_func=lambda c: course_map[c].name,
                key="home_filter_courses",
            )
        with fc2:
            from core.models import EVENT_LABEL_MAP, ALL_TYPES_ORDER
            sel_types = st.multiselect(
                "유형 필터",
                options=ALL_TYPES_ORDER,
                format_func=lambda k: EVENT_LABEL_MAP[k],
                key="home_filter_types",
            )

    def _filter(evts):
        if sel_courses:
            evts = [e for e in evts if e.course_code in sel_courses]
        if sel_types:
            evts = [e for e in evts if e.event_type_key() in sel_types]
        return evts

    all_incomplete = [e for e in data.events if not e.completed]
    _dated = [(e, e.sort_at()) for e in all_incomplete]
    all_future = sorted(
        [e for e, sa in _dated if sa and sa.date() >= today],
        key=lambda e: e.sort_at() or datetime.max,
    )
    overdue = sorted(
        [e for e, sa in _dated if sa and sa.date() < today],
        key=lambda e: e.sort_at() or datetime.max,
    )

    # ── D-0 ~ D-3 ────────────────────────────────────────────
    urgent = _filter([e for e in all_future if (d := calc_dday(e, today)) is not None and d <= 3])

    if urgent:
        st.subheader(f"오늘·임박 일정 ({len(urgent)}건)")
        for evt in urgent:
            _event_card(evt, course_map, today)

    # ── D-4 이상 ─────────────────────────────────────────────
    upcoming = _filter([e for e in all_future if (d := calc_dday(e, today)) is not None and d > 3])

    if upcoming:
        st.subheader(f"다가오는 일정")
        show_n = st.session_state.get("home_show_n", 10)
        for evt in upcoming[:show_n]:
            _event_card(evt, course_map, today)
        if len(upcoming) > show_n:
            if st.button(f"더 보기 ({len(upcoming) - show_n}건 더)"):
                st.session_state["home_show_n"] = show_n + 10
                st.rerun()

    if not urgent and not upcoming:
        st.success("임박한 미완료 일정이 없습니다!")

    # ── 지난 미완료 ───────────────────────────────────────────
    past = _filter(overdue)
    if past:
        with st.expander(f"지난 미완료 일정 ({len(past)}건)", expanded=False):
            for evt in past:
                _event_card(evt, course_map, today)


run()
