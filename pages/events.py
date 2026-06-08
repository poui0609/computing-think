"""pages/events.py — 일정 CRUD + progress UI"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time

import streamlit as st

from core.models import (
    EVENT_TYPE_MAP, EVENT_LABEL_MAP, EVENT_ICON_MAP,
    ALL_TYPES_ORDER,
    PeriodEvent, WindowEvent, DeadlineEvent,
)
from core.period import PERIOD_LABELS, periods_to_range, combine_datetime
from core.storage import (
    load, add_event, update_event, remove_event,
    set_event_progress, toggle_event_completed,
    get_course_map,
)
from core.dday import calc_dday, dday_label, dday_color
from core.progress import progress_color, progress_bar_html
from core.rule_engine import week_number


# Timing mode per event type
_PERIOD_TYPES   = {"quiz", "zoom_meeting"}
_WINDOW_TYPES   = {"assignment", "vod"}
_DEADLINE_TYPES = {
    "poll", "board", "survey", "group_evaluation",
    "forum", "wiki", "file", "folder", "label", "url",
}



def _timing_mode(type_key: str) -> str:
    if type_key in _PERIOD_TYPES:
        return "period"
    if type_key in _WINDOW_TYPES:
        return "window"
    return "deadline"


def _week_num(event) -> int | None:
    from core.storage import load as sload
    data = sload()
    sem_start = date.fromisoformat(data.semester["start_date"])
    sa = event.sort_at()
    if sa is None:
        return None
    return week_number(sa.date(), sem_start)


# ─── Add / Edit form ──────────────────────────────────────────

def _type_selector(default_key: str = "quiz") -> str:
    st.markdown("**일정 종류**")
    cols_row1 = st.columns(7)
    cols_row2 = st.columns(7)
    rows = [ALL_TYPES_ORDER[:7], ALL_TYPES_ORDER[7:]]
    col_groups = [cols_row1, cols_row2]

    if "selected_event_type" not in st.session_state:
        st.session_state["selected_event_type"] = default_key

    for row, cols in zip(rows, col_groups):
        for key, col in zip(row, cols):
            with col:
                label = EVENT_LABEL_MAP[key]
                icon  = EVENT_ICON_MAP[key]
                st.image(icon, width=36)
                selected = st.session_state["selected_event_type"] == key
                btn_type = "primary" if selected else "secondary"
                if st.button(label, key=f"type_btn_{key}", use_container_width=True, type=btn_type):
                    st.session_state["selected_event_type"] = key
                    st.rerun()

    return st.session_state["selected_event_type"]


def _event_form(
    courses: list,
    default_type: str = "quiz",
    default_values: dict | None = None,
    form_key: str = "add_event_form",
) -> dict | None:
    """이벤트 입력 폼. 완성 시 dict 반환, 취소/미완성 시 None."""
    dv = default_values or {}

    # 과목 선택
    if not courses:
        st.warning("수강 과목을 먼저 등록해 주세요. → **수강 과목** 페이지")
        return None

    course_opts = [c.code for c in courses]
    default_idx = course_opts.index(dv.get("course_code", course_opts[0])) if dv.get("course_code") in course_opts else 0
    course_code = st.selectbox(
        "과목",
        options=course_opts,
        index=default_idx,
        format_func=lambda c: next((x.name for x in courses if x.code == c), c),
        key=f"{form_key}_course",
    )

    # 일정 종류
    type_key = _type_selector(dv.get("event_type", default_type))
    mode = _timing_mode(type_key)

    st.divider()

    # 공통 필드
    title = st.text_input("제목 *", value=dv.get("title", ""), key=f"{form_key}_title")
    desc  = st.text_area("메모", value=dv.get("description", ""), height=80, key=f"{form_key}_desc")

    # timing_mode별 필드
    result: dict = {
        "course_code": course_code,
        "event_type":  type_key,
        "title":       title,
        "description": desc,
    }

    st.divider()

    if mode == "period":
        st.markdown("**날짜 및 교시**")
        default_date = date.today()
        if dv.get("start_at"):
            default_date = datetime.fromisoformat(dv["start_at"]).date()

        d = st.date_input("날짜", value=default_date, key=f"{form_key}_date")
        c1, c2 = st.columns(2)
        with c1:
            sp = st.selectbox(
                "시작 교시",
                options=list(PERIOD_LABELS.keys()),
                format_func=lambda x: PERIOD_LABELS[x],
                index=(dv.get("start_period", 1) - 1),
                key=f"{form_key}_sp",
            )
        with c2:
            ep_opts = [x for x in PERIOD_LABELS if x >= sp]
            ep_default = dv.get("end_period", sp)
            ep_idx = ep_opts.index(ep_default) if ep_default in ep_opts else 0
            ep = st.selectbox(
                "종료 교시",
                options=ep_opts,
                format_func=lambda x: PERIOD_LABELS[x],
                index=ep_idx,
                key=f"{form_key}_ep",
            )

        try:
            start_dt, end_dt = periods_to_range(d, sp, ep)
            st.info(f"{start_dt.strftime('%H:%M')} ~ {end_dt.strftime('%H:%M')}")
            result.update({
                "start_at": start_dt.isoformat(),
                "end_at":   end_dt.isoformat(),
                "start_period": sp,
                "end_period":   ep,
            })
        except ValueError as e:
            st.error(str(e))

    elif mode == "window":
        use_open = st.checkbox(
            "시작 시각 설정 (optional)",
            value=bool(dv.get("open_at")),
            key=f"{form_key}_use_open",
        )
        if use_open:
            c1, c2 = st.columns(2)
            with c1:
                open_date = st.date_input(
                    "시작일",
                    value=datetime.fromisoformat(dv["open_at"]).date() if dv.get("open_at") else date.today(),
                    key=f"{form_key}_open_date",
                )
            with c2:
                open_time = st.time_input(
                    "시작 시각",
                    value=datetime.fromisoformat(dv["open_at"]).time() if dv.get("open_at") else time(0, 0),
                    key=f"{form_key}_open_time",
                )
            open_dt = datetime.combine(open_date, open_time)
            result["open_at"] = open_dt.isoformat()
        else:
            result["open_at"] = None

        c1, c2 = st.columns(2)
        with c1:
            due_date = st.date_input(
                "마감일 *",
                value=datetime.fromisoformat(dv["due_at"]).date() if dv.get("due_at") else date.today(),
                key=f"{form_key}_due_date",
            )
        with c2:
            due_time = st.time_input(
                "마감 시각",
                value=datetime.fromisoformat(dv["due_at"]).time() if dv.get("due_at") else time(23, 59),
                key=f"{form_key}_due_time",
            )
        due_dt = datetime.combine(due_date, due_time)
        if use_open and result.get("open_at") and datetime.fromisoformat(result["open_at"]) >= due_dt:
            st.error("시작 시각은 마감 시각보다 이전이어야 합니다.")
        else:
            result["due_at"] = due_dt.isoformat()

    else:  # deadline
        c1, c2 = st.columns(2)
        with c1:
            due_date = st.date_input(
                "마감일 *",
                value=datetime.fromisoformat(dv["due_at"]).date() if dv.get("due_at") else date.today(),
                key=f"{form_key}_due_date",
            )
        with c2:
            due_time = st.time_input(
                "마감 시각",
                value=datetime.fromisoformat(dv["due_at"]).time() if dv.get("due_at") else time(23, 59),
                key=f"{form_key}_due_time",
            )
        result["due_at"] = datetime.combine(due_date, due_time).isoformat()

    return result


def _save_new_event(form_data: dict) -> None:
    from dataclasses import fields as dc_fields
    type_key = form_data.pop("event_type")
    cls = EVENT_TYPE_MAP[type_key]

    valid = {f.name for f in dc_fields(cls)}
    evt = cls(
        id=str(uuid.uuid4()),
        **{k: v for k, v in form_data.items() if k in valid},
    )
    evt.week_number = _week_num(evt)
    add_event(evt)


# ─── Event list item ──────────────────────────────────────────

def _render_event_row(event, course_map: dict, today: date, editable: bool = True) -> None:
    course = course_map.get(event.course_code)
    course_name = course.name if course else event.course_code
    course_color = course.color if course else "#999"

    dday = calc_dday(event, today)
    color = progress_color(event.progress)

    with st.container():
        col_icon, col_info, col_meta = st.columns([0.5, 6, 2.5])
        with col_icon:
            st.image(event.icon_path(), width=28)

        with col_info:
            completed_style = "text-decoration:line-through; color:#aaa;" if event.completed else ""
            st.markdown(
                f'<span style="font-size:12px; color:{course_color}; font-weight:bold;">[{course_name}]</span> '
                f'<span style="{completed_style}">{event.title}</span>',
                unsafe_allow_html=True,
            )
            # Time info
            if isinstance(event, PeriodEvent) and event.start_at:
                dt = datetime.fromisoformat(event.start_at)
                p_info = f"{event.start_period}~{event.end_period}교시" if event.start_period and event.end_period else ""
                st.caption(f"{dt.strftime('%m/%d(%a) %H:%M')} ~ {datetime.fromisoformat(event.end_at).strftime('%H:%M')} {p_info}")
            elif isinstance(event, WindowEvent):
                if event.open_at:
                    st.caption(
                        f"{datetime.fromisoformat(event.open_at).strftime('%m/%d %H:%M')} ~ "
                        f"{datetime.fromisoformat(event.due_at).strftime('%m/%d %H:%M')}"
                    )
                else:
                    st.caption(f"~ {datetime.fromisoformat(event.due_at).strftime('%m/%d(%a) %H:%M')}")
            elif hasattr(event, "due_at") and event.due_at:
                st.caption(f"~ {datetime.fromisoformat(event.due_at).strftime('%m/%d(%a) %H:%M')}")

            if event.source == "rule":
                st.caption("🔄 규칙에서 생성된 일정")

            st.markdown(progress_bar_html(event.progress, height=4), unsafe_allow_html=True)

        with col_meta:
            if dday is not None:
                badge_color = dday_color(dday)
                st.markdown(
                    f'<span style="background:{badge_color}; color:white; padding:2px 8px; '
                    f'border-radius:12px; font-size:12px; font-weight:bold;">'
                    f'{dday_label(dday)}</span>',
                    unsafe_allow_html=True,
                )
            done = st.checkbox(
                "완료", value=event.completed, key=f"done_{event.id}"
            )
            if done != event.completed:
                toggle_event_completed(event.id, done)
                st.rerun()

        # Progress slider
        new_prog = st.slider(
            "진행률",
            0, 100, event.progress,
            key=f"prog_{event.id}",
            format="%d%%",
            label_visibility="collapsed",
        )
        if new_prog != event.progress:
            set_event_progress(event.id, new_prog)
            st.rerun()

        if editable:
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("수정", key=f"edit_{event.id}", use_container_width=True):
                    st.session_state["editing_event_id"] = event.id
            with c2:
                if st.button("삭제", key=f"del_evt_{event.id}", use_container_width=True):
                    st.session_state[f"confirm_del_evt_{event.id}"] = True

            if st.session_state.get(f"confirm_del_evt_{event.id}"):
                st.warning(f"**{event.title}** 을(를) 삭제할까요?")
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("삭제 확인", key=f"del_evt_ok_{event.id}", type="primary"):
                        remove_event(event.id)
                        st.session_state.pop(f"confirm_del_evt_{event.id}", None)
                        st.success("삭제 완료")
                        st.rerun()
                with dc2:
                    if st.button("취소", key=f"del_evt_cancel_{event.id}"):
                        st.session_state.pop(f"confirm_del_evt_{event.id}", None)
                        st.rerun()

    st.divider()


# ─── Edit modal (inline) ──────────────────────────────────────

def _edit_event(event_id: str, data, course_map: dict) -> None:
    event = next((e for e in data.events if e.id == event_id), None)
    if event is None:
        st.error("일정을 찾을 수 없습니다.")
        st.session_state.pop("editing_event_id", None)
        return

    if event.source == "rule":
        st.info("규칙에서 생성된 일정입니다. 수정 시 규칙 재생성 때 덮어쓰일 수 있습니다.")

    st.subheader(f"일정 수정: {event.title}")
    default_vals = event.to_dict()

    form_data = _event_form(
        data.courses,
        default_type=event.event_type_key(),
        default_values=default_vals,
        form_key="edit_event_form",
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("저장", type="primary", key="save_edit_evt"):
            if form_data and form_data.get("title"):
                type_key = form_data.pop("event_type")
                update_event(event_id, **form_data)
                st.session_state.pop("editing_event_id", None)
                st.success("수정 완료!")
                st.rerun()
            else:
                st.error("제목을 입력하세요.")
    with c2:
        if st.button("취소", key="cancel_edit_evt"):
            st.session_state.pop("editing_event_id", None)
            st.rerun()


# ─── Main ─────────────────────────────────────────────────────

def run():
    st.title("일정 관리")

    data = load()
    if not data.courses:
        st.warning("수강 과목을 먼저 등록해 주세요. → **수강 과목** 페이지")
        return

    course_map = get_course_map(data)
    today = date.today()

    # Edit mode
    if "editing_event_id" in st.session_state:
        _edit_event(st.session_state["editing_event_id"], data, course_map)
        return

    tab_add, tab_list = st.tabs(["일정 추가", "일정 목록"])

    # ── 탭: 일정 추가 ────────────────────────────────────────
    with tab_add:
        form_data = _event_form(data.courses, form_key="new_event_form")

        st.divider()
        if st.button("저장", type="primary", key="save_new_evt"):
            if not form_data or not form_data.get("title", "").strip():
                st.error("제목을 입력하세요.")
            elif form_data.get("event_type") in _PERIOD_TYPES and not form_data.get("start_at"):
                st.error("날짜와 교시를 입력하세요.")
            elif form_data.get("event_type") in (_WINDOW_TYPES | _DEADLINE_TYPES) and not form_data.get("due_at"):
                st.error("마감일을 입력하세요.")
            else:
                _save_new_event(form_data)
                st.success("일정이 추가되었습니다!")
                st.rerun()

    # ── 탭: 일정 목록 ────────────────────────────────────────
    with tab_list:
        # Filters
        with st.expander("필터", expanded=True):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                sel_courses = st.multiselect(
                    "과목",
                    options=[c.code for c in data.courses],
                    format_func=lambda c: course_map[c].name,
                    default=[],
                    key="list_filter_courses",
                )
            with fc2:
                sel_types = st.multiselect(
                    "종류",
                    options=ALL_TYPES_ORDER,
                    format_func=lambda k: EVENT_LABEL_MAP[k],
                    default=[],
                    key="list_filter_types",
                )
            with fc3:
                sel_done = st.radio(
                    "완료 여부",
                    options=["전체", "미완료만", "완료만"],
                    horizontal=True,
                    key="list_filter_done",
                )

        events = data.events
        if sel_courses:
            events = [e for e in events if e.course_code in sel_courses]
        if sel_types:
            events = [e for e in events if e.event_type_key() in sel_types]
        if sel_done == "미완료만":
            events = [e for e in events if not e.completed]
        elif sel_done == "완료만":
            events = [e for e in events if e.completed]

        # Sort by sort_at
        events = sorted(events, key=lambda e: (e.sort_at() or datetime.max))

        if not events:
            st.info("표시할 일정이 없습니다.")
        else:
            st.caption(f"{len(events)}건")
            for evt in events:
                _render_event_row(evt, course_map, today)


run()
