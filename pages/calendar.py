from __future__ import annotations

import base64
import calendar
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import streamlit as st

from core.models import (
    Event, PeriodEvent, DeadlineEvent, RangeEvent, OpenEvent,
    EVENT_LABEL_MAP, EVENT_ICON_MAP, DOMAIN_LABEL,
    is_timed, timed_auto_done,
)
from core.storage import load, get_course_map, set_event_progress, toggle_event_completed

def _cb_cal_done(event_id: str, d: str) -> None:
    done = st.session_state[f"cal_det_done_{event_id}_{d}"]
    evt  = toggle_event_completed(event_id, done)
    st.session_state[f"cal_det_prog_{event_id}_{d}"] = evt.progress


def _cb_cal_prog(event_id: str, d: str) -> None:
    prog = st.session_state[f"cal_det_prog_{event_id}_{d}"]
    evt  = set_event_progress(event_id, prog)
    st.session_state[f"cal_det_done_{event_id}_{d}"] = evt.completed
from core.dday import calc_dday, dday_label
from core.progress import progress_color, progress_bar_html, course_week_progress
from core.rule_engine import week_number as compute_week_number

_icon_b64_cache: dict[str, str] = {}


def _icon_b64(path: str) -> str:
    if path in _icon_b64_cache:
        return _icon_b64_cache[path]
    p = Path(path)
    if p.exists():
        b64 = base64.b64encode(p.read_bytes()).decode()
        _icon_b64_cache[path] = b64
        return b64
    return ""


def _img_tag(icon_path: str, size: int = 12) -> str:
    b64 = _icon_b64(icon_path)
    if b64:
        return f'<img src="data:image/png;base64,{b64}" width="{size}" height="{size}" style="vertical-align:middle; flex-shrink:0;">'
    return "■"


def _bar_segment(
    event: Event,
    cell_date: date,
    bar_start: date,
    bar_end: date,
    color: str,
    show_title: bool = False,
) -> str:
    is_start  = cell_date == bar_start
    is_end    = cell_date == bar_end
    is_single = is_start and is_end

    if is_single:
        radius = "3px"
    elif is_start:
        radius = "3px 0 0 3px"
    elif is_end:
        radius = "0 3px 3px 0"
    else:
        radius = "0"

    left_dot  = f'<span style="color:{color}; font-size:8px; flex-shrink:0; line-height:1;">●</span>' if is_start else ""
    right_dot = f'<span style="color:{color}; font-size:8px; flex-shrink:0; line-height:1;">●</span>' if is_end else ""

    icon_part = _img_tag(event.icon_path(), 11) if (is_start or is_single) else ""

    title = event.title
    title_short = (title[:9] + "…") if len(title) > 10 else title
    completed_style = "text-decoration:line-through; opacity:0.5;" if event.completed else ""
    title_part = (
        f'<span style="font-size:9px; color:{color}; margin-left:2px; '
        f'white-space:nowrap; overflow:hidden; {completed_style}">{title_short}</span>'
        if (is_start or is_single)
        else ""
    )

    line = (
        f'<div style="flex:1; height:4px; background:{color}; '
        f'border-radius:{radius}; opacity:{"0.4" if event.completed else "1"};"></div>'
    )

    return (
        f'<div style="display:flex; align-items:center; height:18px; '
        f'gap:1px; margin-bottom:1px; overflow:hidden;">'
        f'{icon_part}{left_dot}{line}{right_dot}{title_part}'
        f'</div>'
    )


def _event_date_range(event: Event) -> tuple[Optional[date], Optional[date]]:
    if isinstance(event, PeriodEvent):
        s = datetime.fromisoformat(event.start_at).date() if event.start_at else None
        e = datetime.fromisoformat(event.end_at).date()   if event.end_at   else s
        return s, e
    if isinstance(event, OpenEvent):
        s = datetime.fromisoformat(event.start_at).date() if event.start_at else None
        return s, s
    if isinstance(event, RangeEvent):
        s = datetime.fromisoformat(event.start_at).date() if event.start_at else None
        e = datetime.fromisoformat(event.end_at).date()   if event.end_at   else s
        return s, e
    if isinstance(event, DeadlineEvent):
        s = datetime.fromisoformat(event.open_at).date() if event.open_at else None
        e = datetime.fromisoformat(event.due_at).date()  if event.due_at  else None
        if s is None:
            return e, e
        return s, e
    return None, None


def _events_for_date(events: list[Event], d: date) -> list[Event]:
    result = []
    for e in events:
        s, end = _event_date_range(e)
        if s is None and end is None:
            continue
        if s is None:
            if end == d:
                result.append(e)
        else:
            if s <= d <= end:
                result.append(e)
    return result

_DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]
_CELL_STYLE = (
    "min-height:90px; border:1px solid #e0e0e0; padding:4px; "
    "border-radius:4px; background:#fafafa; overflow:hidden;"
)
_TODAY_STYLE = (
    "min-height:90px; border:2px solid #4A90D9; padding:4px; "
    "border-radius:4px; background:#EBF5FB; overflow:hidden;"
)
_WEEKEND_STYLE = (
    "min-height:90px; border:1px solid #e0e0e0; padding:4px; "
    "border-radius:4px; background:#fdf8f8; overflow:hidden;"
)


def _render_week_row(
    week_dates: list[date],
    events: list[Event],
    course_map: dict,
    today: date,
    data,
    week_num: int,
    show_week_progress: bool,
) -> None:
    sem_start = date.fromisoformat(data.semester["start_date"])
    label_col, *day_cols = st.columns([0.7, *[1]*7])
    with label_col:
        st.markdown(
            f'<div style="text-align:center; font-size:11px; font-weight:bold; '
            f'color:#666; padding-top:4px;">Week<br/>{week_num}</div>',
            unsafe_allow_html=True,
        )
        if show_week_progress:
            for course in data.courses:
                pct = course_week_progress(data.events, course.code, week_num)
                color = progress_color(pct)
                st.markdown(
                    f'<div style="height:5px; background:#eee; border-radius:3px; margin:1px 0;">'
                    f'<div style="width:{pct}%; height:5px; background:{color}; border-radius:3px;"></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    for col, d in zip(day_cols, week_dates):
        with col:
            if d is None:
                st.markdown('<div style="min-height:90px;"></div>', unsafe_allow_html=True)
                continue

            style = _TODAY_STYLE if d == today else (
                _WEEKEND_STYLE if d.weekday() >= 5 else _CELL_STYLE
            )

            day_events = _events_for_date(events, d)

            bars_html = ""
            max_shown = 4
            extra = max(0, len(day_events) - max_shown)

            for evt in day_events[:max_shown]:
                domain = getattr(evt, "domain", "course")
                course = course_map.get(evt.course_code)
                if domain == "course" and course:
                    color = course.color
                elif domain == "academic":
                    color = "#9B59B6"
                elif domain == "personal":
                    color = "#1ABC9C"
                else:
                    color = "#999"
                s, e_d = _event_date_range(evt)
                bars_html += _bar_segment(evt, d, s or d, e_d or d, color)

            if extra:
                bars_html += (
                    f'<div style="font-size:9px; color:#888; margin-top:1px;">+{extra}건 더</div>'
                )

            is_selected = st.session_state.get("cal_selected_date") == d
            selected_border = "border:2px solid #4A90D9;" if is_selected else ""

            st.markdown(
                f'<div style="{style} {selected_border}">'
                f'<div style="font-size:11px; font-weight:bold; color:{"#E74C3C" if d == today else "#333"};">'
                f'{d.day}'
                f'</div>'
                f'{bars_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
            if day_events:
                btn_label = "▲ 닫기" if is_selected else f"📋 {len(day_events)}건"
                if st.button(
                    btn_label,
                    key=f"cal_day_{d}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    if is_selected:
                        st.session_state.pop("cal_selected_date", None)
                    else:
                        st.session_state["cal_selected_date"] = d
                    st.rerun()


def _render_day_detail(d: date, events: list[Event], course_map: dict, today: date) -> None:
    st.subheader(f"{d.strftime('%Y년 %m월 %d일 (%a)')} 일정 상세")
    day_events = _events_for_date(events, d)

    if not day_events:
        st.info("이 날짜에 해당하는 일정이 없습니다.")
        return

    for evt in day_events:
        domain = getattr(evt, "domain", "course")
        course = course_map.get(evt.course_code)
        if domain == "course" and course:
            cname  = course.name
            ccolor = course.color
        else:
            domain_colors = {"academic": "#9B59B6", "personal": "#1ABC9C"}
            cname  = DOMAIN_LABEL.get(domain, domain)
            ccolor = domain_colors.get(domain, "#888")
        dday   = calc_dday(evt, today)

        timed     = is_timed(evt)
        auto_done = timed_auto_done(evt)

        with st.container(border=True):
            c1, c2 = st.columns([0.5, 8])
            with c1:
                st.image(evt.icon_path(), width=28)
            with c2:
                done_style = "text-decoration:line-through; color:#aaa;" if (evt.completed or auto_done) else ""
                st.markdown(
                    f'<span style="color:{ccolor}; font-weight:bold;">[{cname}]</span> '
                    f'<span style="{done_style}">{evt.title}</span>',
                    unsafe_allow_html=True,
                )
                if timed:
                    badge_text   = "자동 완료" if auto_done else "진행 중"
                    badge_color2 = "#00ACC1"  if auto_done else "#F39C12"
                    st.markdown(
                        f'<span style="background:{badge_color2}; color:white; padding:2px 8px; '
                        f'border-radius:12px; font-size:11px; font-weight:bold;">{badge_text}</span>',
                        unsafe_allow_html=True,
                    )
                elif dday is not None:
                    st.caption(dday_label(dday))

            if not timed:
                st.markdown(progress_bar_html(evt.progress, height=5), unsafe_allow_html=True)
                st.slider(
                    "진행률", 0, 100, evt.progress,
                    key=f"cal_det_prog_{evt.id}_{d}",
                    format="%d%%",
                    label_visibility="collapsed",
                    on_change=_cb_cal_prog, args=(evt.id, str(d)),
                )
                st.checkbox(
                    "완료", value=evt.completed,
                    key=f"cal_det_done_{evt.id}_{d}",
                    on_change=_cb_cal_done, args=(evt.id, str(d)),
                )


def run():
    st.title("캘린더")

    data       = load()
    course_map = get_course_map(data)
    today      = date.today()

    if not data.courses:
        st.info("수강 과목을 먼저 등록하세요. → **수강 과목** 페이지")
        return
    if "cal_year" not in st.session_state:
        st.session_state["cal_year"]  = today.year
    if "cal_month" not in st.session_state:
        st.session_state["cal_month"] = today.month

    yr  = st.session_state["cal_year"]
    mo  = st.session_state["cal_month"]

    nav_c1, nav_c2, nav_c3, nav_c4 = st.columns([1, 2, 1, 5])
    with nav_c1:
        if st.button("◀", key="cal_prev"):
            mo -= 1
            if mo < 1:
                mo = 12; yr -= 1
            st.session_state.update({"cal_year": yr, "cal_month": mo})
            st.rerun()
    with nav_c2:
        st.markdown(
            f'<h3 style="text-align:center; margin:0;">{yr}년 {mo}월</h3>',
            unsafe_allow_html=True,
        )
    with nav_c3:
        if st.button("▶", key="cal_next"):
            mo += 1
            if mo > 12:
                mo = 1; yr += 1
            st.session_state.update({"cal_year": yr, "cal_month": mo})
            st.rerun()
    with nav_c4:
        if st.button("오늘", key="cal_today"):
            st.session_state.update({"cal_year": today.year, "cal_month": today.month})
            st.rerun()

    with st.expander("필터"):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            sel_courses = st.multiselect(
                "과목",
                options=[c.code for c in data.courses],
                format_func=lambda c: course_map[c].name,
                key="cal_filter_courses",
            )
        with fc2:
            sel_types = st.multiselect(
                "종류",
                options=list(EVENT_LABEL_MAP.keys()),
                format_func=lambda k: EVENT_LABEL_MAP[k],
                key="cal_filter_types",
            )
        with fc3:
            sel_done = st.radio(
                "완료 여부",
                ["전체", "미완료만", "완료만"],
                horizontal=True,
                key="cal_filter_done",
            )
        show_week_progress = st.checkbox("주차 progress 표시", value=True, key="cal_show_wp")

    events = data.events
    if sel_courses:
        events = [e for e in events if e.course_code in sel_courses]
    if sel_types:
        events = [e for e in events if e.event_type_key() in sel_types]
    if sel_done == "미완료만":
        events = [e for e in events if not e.completed]
    elif sel_done == "완료만":
        events = [e for e in events if e.completed]

    header_cols = st.columns([0.7, *[1]*7])
    with header_cols[0]:
        st.markdown('<div style="text-align:center; font-size:11px; color:#999;"></div>', unsafe_allow_html=True)
    for i, name in enumerate(_DAY_NAMES):
        with header_cols[i + 1]:
            color = "#E74C3C" if i == 6 else ("#3498DB" if i == 5 else "#555")
            st.markdown(
                f'<div style="text-align:center; font-weight:bold; color:{color}; font-size:12px;">{name}</div>',
                unsafe_allow_html=True,
            )

    if "cal_selected_date" in st.session_state:
        sel_d = st.session_state["cal_selected_date"]
        with st.container(border=True):
            col_title, col_close = st.columns([8, 1])
            with col_title:
                st.markdown(
                    f"### 📋 {sel_d.strftime('%Y년 %m월 %d일 (%a)')} 일정 상세"
                )
            with col_close:
                if st.button("✕ 닫기", key="cal_close_detail", use_container_width=True):
                    st.session_state.pop("cal_selected_date")
                    st.rerun()
            _render_day_detail(sel_d, events, course_map, today)
        st.divider()

    month_weeks = calendar.monthcalendar(yr, mo)
    sem_start   = date.fromisoformat(data.semester["start_date"])

    for week in month_weeks:
        week_dates: list[Optional[date]] = []
        for day_num in week:
            if day_num == 0:
                week_dates.append(None)
            else:
                week_dates.append(date(yr, mo, day_num))

        valid_dates = [d for d in week_dates if d is not None]
        mid_date    = valid_dates[len(valid_dates) // 2] if valid_dates else date(yr, mo, 1)
        w_num       = compute_week_number(mid_date, sem_start)

        _render_week_row(
            week_dates, events, course_map, today, data, w_num, show_week_progress
        )


run()
