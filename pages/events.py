"""pages/events.py — 일정 CRUD + 3도메인(수업/학사/개인) 지원"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time

import streamlit as st

from core.models import (
    EVENT_TYPE_MAP, EVENT_LABEL_MAP, EVENT_ICON_MAP,
    ALL_TYPES_ORDER, COURSE_TYPES, ACADEMIC_TYPES, PERSONAL_TYPES,
    PERSONAL_OPEN_TYPES, DOMAIN_LABEL,
    PeriodEvent, DeadlineEvent, RangeEvent, OpenEvent,
    is_timed, timed_auto_done,
)

from core.period import PERIOD_LABELS, periods_to_range
from core.storage import (
    load, add_event, update_event, remove_event,
    set_event_progress, toggle_event_completed,
    get_course_map,
)
from core.dday import calc_dday, dday_label, dday_color
from core.progress import progress_color, progress_bar_html, is_todo
from core.rule_engine import week_number


# ─── Timing 분류 ──────────────────────────────────────────────

_PERIOD_TYPES  = {"quiz", "zoom_meeting", "exam"}
_DEADLINE_TYPES = {
    "assignment", "vod", "team_project",
    "dept_competition",
    "poll", "board", "survey", "forum", "wiki", "file", "folder", "label", "url",
}
_RANGE_TYPES = {
    "seminar", "exhibition", "official_event",
    "exam_prep", "quiz_prep", "self_study",
    "club", "volunteer", "ext_competition", "personal_custom",
}
_OPEN_TYPES = set(PERSONAL_OPEN_TYPES)   # 개인 오픈형 — start_at 만 입력


def _timing_mode(type_key: str) -> str:
    if type_key in _PERIOD_TYPES:   return "period"
    if type_key in _DEADLINE_TYPES: return "deadline"
    if type_key in _OPEN_TYPES:     return "open"
    return "range"


# ─── on_change 콜백 ───────────────────────────────────────────

def _cb_done(event_id: str) -> None:
    done = st.session_state[f"done_{event_id}"]
    evt  = toggle_event_completed(event_id, done)
    st.session_state[f"prog_{event_id}"] = evt.progress


def _cb_prog(event_id: str) -> None:
    prog = st.session_state[f"prog_{event_id}"]
    evt  = set_event_progress(event_id, prog)
    st.session_state[f"done_{event_id}"] = evt.completed


def _week_num(event) -> int | None:
    data = load()
    sem_start = date.fromisoformat(data.semester["start_date"])
    sa = event.sort_at()
    return week_number(sa.date(), sem_start) if sa else None


# ─── 수업 타입 선택 그리드 (1행 6열) ──────────────────────────

def _set_type(ss_key: str, key: str) -> None:
    st.session_state[ss_key] = key


def _course_type_selector(form_key: str, default_key: str = "vod") -> str:
    st.markdown("**일정 종류**")
    ss_key = f"{form_key}_selected_type"
    if ss_key not in st.session_state or st.session_state[ss_key] not in COURSE_TYPES:
        st.session_state[ss_key] = default_key

    cols = st.columns(6)
    for key, col in zip(COURSE_TYPES, cols):
        with col:
            is_sel = st.session_state[ss_key] == key
            with st.container(border=True):
                st.image(EVENT_ICON_MAP[key], width=28)
                st.button(
                    EVENT_LABEL_MAP[key],
                    key=f"{form_key}_type_{key}",
                    use_container_width=True,
                    type="primary" if is_sel else "secondary",
                    on_click=_set_type,
                    args=(ss_key, key),
                )
    return st.session_state[ss_key]


def _preset_selector(form_key: str, preset_list: list[str], default_key: str) -> str:
    """학사/개인 프리셋 선택 (2열 그리드)"""
    ss_key = f"{form_key}_selected_type"
    if ss_key not in st.session_state or st.session_state[ss_key] not in preset_list:
        st.session_state[ss_key] = default_key

    st.markdown("**일정 종류**")
    cols_per_row = 4
    for row_start in range(0, len(preset_list), cols_per_row):
        row_keys = preset_list[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for key, col in zip(row_keys, cols):
            with col:
                is_sel = st.session_state[ss_key] == key
                with st.container(border=True):
                    st.image(EVENT_ICON_MAP[key], width=24)
                    st.button(
                        EVENT_LABEL_MAP[key],
                        key=f"{form_key}_type_{key}",
                        use_container_width=True,
                        type="primary" if is_sel else "secondary",
                        on_click=_set_type,
                        args=(ss_key, key),
                    )
    return st.session_state[ss_key]


# ─── 시간 입력 공통 헬퍼 ─────────────────────────────────────

def _period_inputs(form_key: str, dv: dict) -> dict:
    """PeriodTiming 입력 폼 → result dict"""
    st.markdown("**날짜 및 교시**")
    d_val = (
        datetime.fromisoformat(dv["start_at"]).date()
        if dv.get("start_at") else date.today()
    )
    d = st.date_input("날짜", value=d_val, key=f"{form_key}_date")
    c1, c2 = st.columns(2)
    with c1:
        sp = st.selectbox(
            "시작 교시", list(PERIOD_LABELS.keys()),
            format_func=lambda x: PERIOD_LABELS[x],
            index=(dv.get("start_period", 1) - 1),
            key=f"{form_key}_sp",
        )
    with c2:
        ep_opts = [x for x in PERIOD_LABELS if x >= sp]
        ep_def  = dv.get("end_period", sp)
        ep = st.selectbox(
            "종료 교시", ep_opts,
            format_func=lambda x: PERIOD_LABELS[x],
            index=ep_opts.index(ep_def) if ep_def in ep_opts else 0,
            key=f"{form_key}_ep",
        )
    try:
        s_dt, e_dt = periods_to_range(d, sp, ep)
        st.info(f"{s_dt.strftime('%H:%M')} ~ {e_dt.strftime('%H:%M')}")
        return {
            "start_at": s_dt.isoformat(), "end_at": e_dt.isoformat(),
            "start_period": sp, "end_period": ep,
        }
    except ValueError as e:
        st.error(str(e))
        return {}


def _deadline_inputs(form_key: str, dv: dict, show_open: bool = True) -> dict:
    """DeadlineTiming 입력 폼 → result dict"""
    result = {}
    if show_open:
        use_open = st.checkbox(
            "시작 시각 설정 (선택)",
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
            result["open_at"] = datetime.combine(open_date, open_time).isoformat()
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
    if show_open and result.get("open_at") and datetime.fromisoformat(result["open_at"]) >= due_dt:
        st.error("시작 시각은 마감 시각보다 이전이어야 합니다.")
    else:
        result["due_at"] = due_dt.isoformat()
    return result


def _range_inputs(form_key: str, dv: dict) -> dict:
    """RangeTiming 입력 폼 → result dict"""
    st.markdown("**시간 구간**")
    c1, c2 = st.columns(2)
    with c1:
        s_date = st.date_input(
            "시작일",
            value=datetime.fromisoformat(dv["start_at"]).date() if dv.get("start_at") else date.today(),
            key=f"{form_key}_s_date",
        )
        s_time = st.time_input(
            "시작 시각",
            value=datetime.fromisoformat(dv["start_at"]).time() if dv.get("start_at") else time(9, 0),
            key=f"{form_key}_s_time",
        )
    with c2:
        e_date = st.date_input(
            "종료일",
            value=datetime.fromisoformat(dv["end_at"]).date() if dv.get("end_at") else date.today(),
            key=f"{form_key}_e_date",
        )
        e_time = st.time_input(
            "종료 시각",
            value=datetime.fromisoformat(dv["end_at"]).time() if dv.get("end_at") else time(18, 0),
            key=f"{form_key}_e_time",
        )
    s_dt = datetime.combine(s_date, s_time)
    e_dt = datetime.combine(e_date, e_time)
    if e_dt <= s_dt:
        st.error("종료 시각은 시작 시각보다 이후여야 합니다.")
        return {}
    st.info(f"{s_dt.strftime('%m/%d %H:%M')} ~ {e_dt.strftime('%m/%d %H:%M')}")
    return {"start_at": s_dt.isoformat(), "end_at": e_dt.isoformat()}


def _open_inputs(form_key: str, dv: dict) -> dict:
    """OpenTiming 입력 폼 — 시작 날짜·시각만 입력, 마감 없음"""
    st.markdown("**시작 날짜 / 시각**")
    c1, c2 = st.columns(2)
    with c1:
        s_date = st.date_input(
            "시작일",
            value=datetime.fromisoformat(dv["start_at"]).date() if dv.get("start_at") else date.today(),
            key=f"{form_key}_open_s_date",
        )
    with c2:
        s_time = st.time_input(
            "시작 시각",
            value=datetime.fromisoformat(dv["start_at"]).time() if dv.get("start_at") else time(9, 0),
            key=f"{form_key}_open_s_time",
        )
    s_dt = datetime.combine(s_date, s_time)
    st.info(f"시작: {s_dt.strftime('%Y/%m/%d %H:%M')}  |  마감 없음 (오픈형)")
    return {"start_at": s_dt.isoformat()}


# ─── 도메인별 폼 ──────────────────────────────────────────────

def _course_form(courses: list, form_key: str, dv: dict) -> dict | None:
    """수업 일정 입력 폼"""
    if not courses:
        st.warning("수강 과목을 먼저 등록해 주세요.")
        return None

    course_opts = [c.code for c in courses]
    default_idx = course_opts.index(dv["course_code"]) if dv.get("course_code") in course_opts else 0
    course_code = st.selectbox(
        "과목 *",
        options=course_opts,
        index=default_idx,
        format_func=lambda c: next((x.name for x in courses if x.code == c), c),
        key=f"{form_key}_course",
    )

    default_type = dv.get("event_type", "vod")
    if default_type not in COURSE_TYPES:
        default_type = "vod"
    type_key = _course_type_selector(form_key, default_type)
    mode     = _timing_mode(type_key)

    st.divider()
    title = st.text_input("제목 *", value=dv.get("title", ""), key=f"{form_key}_title")
    desc  = st.text_area("메모", value=dv.get("description", ""), height=68, key=f"{form_key}_desc")

    result: dict = {
        "domain": "course",
        "course_code": course_code,
        "event_type":  type_key,
        "title":       title,
        "description": desc,
    }
    st.divider()

    if mode == "period":
        result.update(_period_inputs(form_key, dv))
    else:
        result.update(_deadline_inputs(form_key, dv, show_open=True))

    return result


def _academic_form(form_key: str, dv: dict) -> dict | None:
    """학사 일정 입력 폼"""
    default_type = dv.get("event_type", "seminar")
    if default_type not in ACADEMIC_TYPES:
        default_type = "seminar"
    type_key = _preset_selector(form_key, ACADEMIC_TYPES, default_type)
    mode     = _timing_mode(type_key)

    st.divider()
    title = st.text_input("제목 *", value=dv.get("title", ""), key=f"{form_key}_title")
    organizer = st.text_input("주관 (선택)", value=dv.get("description", ""), key=f"{form_key}_organizer",
                              placeholder="예: 소프트웨어학부")
    desc  = st.text_area("메모", value="", height=60, key=f"{form_key}_desc")

    result: dict = {
        "domain": "academic",
        "course_code": "",
        "event_type":  type_key,
        "title":       title,
        "description": f"{organizer}\n{desc}".strip() if organizer else desc,
    }
    st.divider()

    if mode == "deadline":
        result.update(_deadline_inputs(form_key, dv, show_open=True))
    else:
        result.update(_range_inputs(form_key, dv))

    return result


def _personal_form(form_key: str, dv: dict) -> dict | None:
    """개인 일정 입력 폼 — 구간형 / 오픈형 탭 분리"""
    RANGE_LIST = [t for t in PERSONAL_TYPES if t not in PERSONAL_OPEN_TYPES]
    OPEN_LIST  = list(PERSONAL_OPEN_TYPES)

    # 기존 편집 이벤트의 타이밍을 기준으로 초기 탭 결정
    default_type = dv.get("event_type", "self_study")
    initial_tab  = 1 if default_type in PERSONAL_OPEN_TYPES else 0

    tab_range, tab_open = st.tabs(["📅 구간형 (시작 ~ 종료)", "🔓 오픈형 (시작만)"])

    # ── 구간형 탭 ─────────────────────────────────────
    with tab_range:
        r_default = default_type if default_type in RANGE_LIST else "self_study"
        r_type_key = _preset_selector(f"{form_key}_r", RANGE_LIST, r_default)

    # ── 오픈형 탭 ─────────────────────────────────────
    with tab_open:
        o_default = default_type if default_type in OPEN_LIST else "personal_goal"
        o_type_key = _preset_selector(f"{form_key}_o", OPEN_LIST, o_default)

    # 활성 탭을 세션 스테이트로 추적
    tab_key = f"{form_key}_tab"
    if tab_key not in st.session_state:
        st.session_state[tab_key] = initial_tab

    # 두 탭의 type 변경을 감지해 활성 탭 갱신
    prev_r = st.session_state.get(f"{form_key}_r_prev", r_type_key)
    prev_o = st.session_state.get(f"{form_key}_o_prev", o_type_key)
    if r_type_key != prev_r:
        st.session_state[tab_key] = 0
    if o_type_key != prev_o:
        st.session_state[tab_key] = 1
    st.session_state[f"{form_key}_r_prev"] = r_type_key
    st.session_state[f"{form_key}_o_prev"] = o_type_key

    active_tab = st.session_state[tab_key]
    type_key   = o_type_key if active_tab == 1 else r_type_key
    mode       = _timing_mode(type_key)

    st.divider()
    title = st.text_input("제목 *", value=dv.get("title", ""), key=f"{form_key}_title")
    desc  = st.text_area("메모", value=dv.get("description", ""), height=60, key=f"{form_key}_desc")

    result: dict = {
        "domain": "personal",
        "course_code": "",
        "event_type":  type_key,
        "title":       title,
        "description": desc,
    }
    st.divider()

    if mode == "open":
        result.update(_open_inputs(form_key, dv))
    else:
        result.update(_range_inputs(form_key, dv))

    return result


# ─── 저장 헬퍼 ────────────────────────────────────────────────

def _save_new_event(form_data: dict) -> None:
    from dataclasses import fields as dc_fields
    type_key = form_data.pop("event_type")
    cls      = EVENT_TYPE_MAP[type_key]
    valid    = {f.name for f in dc_fields(cls)}
    evt      = cls(id=str(uuid.uuid4()), **{k: v for k, v in form_data.items() if k in valid})
    evt.week_number = _week_num(evt)
    add_event(evt)


def _validate(form_data: dict | None) -> str | None:
    """None이면 OK, str이면 에러 메시지"""
    if not form_data or not form_data.get("title", "").strip():
        return "제목을 입력하세요."
    mode = _timing_mode(form_data.get("event_type", ""))
    if mode == "period" and not form_data.get("start_at"):
        return "날짜와 교시를 입력하세요."
    if mode in ("deadline",) and not form_data.get("due_at"):
        return "마감일을 입력하세요."
    if mode == "range" and not form_data.get("start_at"):
        return "시작 시각을 입력하세요."
    if mode == "open" and not form_data.get("start_at"):
        return "시작 날짜·시각을 입력하세요."
    return None


# ─── 일정 추가 팝업 ──────────────────────────────────────────

@st.dialog("일정 추가", width="large")
def _add_event_dialog(courses: list) -> None:
    tab_labels = ["📚 수업", "🏫 학사", "👤 개인"]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        fd = _course_form(courses, "dlg_add_c", {})
        if st.button("저장", type="primary", key="dlg_c_save", use_container_width=True):
            err = _validate(fd)
            if err:
                st.error(err)
            else:
                _save_new_event(fd)
                st.toast("일정이 추가되었습니다!", icon="✅")
                st.rerun()

    with tabs[1]:
        fd = _academic_form("dlg_add_a", {})
        if st.button("저장", type="primary", key="dlg_a_save", use_container_width=True):
            err = _validate(fd)
            if err:
                st.error(err)
            else:
                _save_new_event(fd)
                st.toast("일정이 추가되었습니다!", icon="✅")
                st.rerun()

    with tabs[2]:
        fd = _personal_form("dlg_add_p", {})
        if st.button("저장", type="primary", key="dlg_p_save", use_container_width=True):
            err = _validate(fd)
            if err:
                st.error(err)
            else:
                _save_new_event(fd)
                st.toast("일정이 추가되었습니다!", icon="✅")
                st.rerun()


# ─── 수정 팝업 ────────────────────────────────────────────────

@st.dialog("일정 수정", width="large")
def _edit_event_dialog(event_id: str, courses: list) -> None:
    data  = load()
    event = next((e for e in data.events if e.id == event_id), None)
    if event is None:
        st.error("일정을 찾을 수 없습니다.")
        st.rerun()
        return

    if event.source == "rule":
        st.info("규칙에서 생성된 일정입니다. 수정 시 규칙 재생성 때 덮어쓰일 수 있습니다.")

    domain = getattr(event, "domain", "course")
    dv     = event.to_dict()

    if domain == "course":
        form_data = _course_form(courses, "dlg_edit", dv)
    elif domain == "academic":
        form_data = _academic_form("dlg_edit", dv)
    else:
        form_data = _personal_form("dlg_edit", dv)

    st.divider()
    if st.button("저장", type="primary", key="dlg_edit_save", use_container_width=True):
        err = _validate(form_data)
        if err:
            st.error(err)
        else:
            form_data.pop("event_type", None)
            update_event(event_id, **form_data)
            st.toast("수정 완료!", icon="✅")
            st.rerun()


# ─── 일정 목록 행 ─────────────────────────────────────────────

def _time_caption(event) -> str:
    if isinstance(event, PeriodEvent) and event.start_at:
        if event.start_period and event.end_period:
            sp, ep = event.start_period, event.end_period
            p_info = (
                f" ({sp}교시)" if sp == ep
                else f" ({sp}\\~{ep} 교시)"   # \\~ → 마크다운 subscript 방지
            )
        else:
            p_info = ""
        s = datetime.fromisoformat(event.start_at).strftime('%m/%d(%a) %H:%M')
        e = datetime.fromisoformat(event.end_at).strftime('%H:%M') if event.end_at else "?"
        return f"{s}–{e}{p_info}"
    if isinstance(event, RangeEvent) and event.start_at:
        s = datetime.fromisoformat(event.start_at).strftime('%m/%d %H:%M')
        e = datetime.fromisoformat(event.end_at).strftime('%m/%d %H:%M') if event.end_at else "?"
        return f"{s} ~ {e}"
    if isinstance(event, DeadlineEvent):
        if event.open_at:
            return (
                f"{datetime.fromisoformat(event.open_at).strftime('%m/%d %H:%M')}"
                f" ~ {datetime.fromisoformat(event.due_at).strftime('%m/%d %H:%M')}"
            )
        if event.due_at:
            return f"~ {datetime.fromisoformat(event.due_at).strftime('%m/%d(%a) %H:%M')}"
    return ""


def _render_event_row(event, course_map: dict, today: date, courses: list) -> None:
    domain = getattr(event, "domain", "course")
    course = course_map.get(event.course_code)

    if domain == "course" and course:
        badge_label = course.name
        badge_color = course.color
    else:
        domain_colors = {"academic": "#9B59B6", "personal": "#1ABC9C"}
        badge_label = DOMAIN_LABEL.get(domain, domain)
        badge_color = domain_colors.get(domain, "#888")

    dday       = calc_dday(event, today)
    timed      = is_timed(event)
    auto_done  = timed_auto_done(event)
    visual_done = event.completed or auto_done

    with st.container():
        col_icon, col_info, col_meta = st.columns([0.5, 6, 2.5])

        with col_icon:
            st.image(event.icon_path(), width=28)

        with col_info:
            done_style = "text-decoration:line-through; color:#aaa;" if visual_done else ""
            st.markdown(
                f'<span style="font-size:12px; color:{badge_color}; font-weight:bold;">[{badge_label}]</span> '
                f'<span style="{done_style}">{event.title}</span>',
                unsafe_allow_html=True,
            )
            cap = _time_caption(event)
            if cap:
                st.caption(cap)
            if event.source == "rule":
                st.caption("🔄 규칙에서 생성된 일정")
            if not timed:
                st.markdown(progress_bar_html(event.progress, height=4), unsafe_allow_html=True)

        with col_meta:
            if timed:
                badge_text  = "자동 완료" if auto_done else "진행 중"
                badge_color2 = "#00ACC1" if auto_done else "#F39C12"
                st.markdown(
                    f'<span style="background:{badge_color2}; color:white; padding:2px 8px; '
                    f'border-radius:12px; font-size:12px; font-weight:bold;">'
                    f'{badge_text}</span>',
                    unsafe_allow_html=True,
                )
            else:
                if dday is not None:
                    bc = dday_color(dday)
                    st.markdown(
                        f'<span style="background:{bc}; color:white; padding:2px 8px; '
                        f'border-radius:12px; font-size:12px; font-weight:bold;">'
                        f'{dday_label(dday)}</span>',
                        unsafe_allow_html=True,
                    )
                st.checkbox(
                    "완료", value=event.completed,
                    key=f"done_{event.id}",
                    on_change=_cb_done, args=(event.id,),
                )

        if not timed:
            st.slider(
                "진행률", 0, 100, event.progress,
                key=f"prog_{event.id}", format="%d%%",
                label_visibility="collapsed",
                on_change=_cb_prog, args=(event.id,),
            )

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("✏️ 수정", key=f"edit_{event.id}", use_container_width=True):
                _edit_event_dialog(event.id, courses)
        with c2:
            if st.button("🗑️ 삭제", key=f"del_evt_{event.id}", use_container_width=True):
                st.session_state[f"confirm_del_{event.id}"] = True

        if st.session_state.get(f"confirm_del_{event.id}"):
            st.warning(f"**{event.title}** 을(를) 삭제할까요?")
            dc1, dc2 = st.columns(2)
            with dc1:
                if st.button("삭제 확인", key=f"del_ok_{event.id}", type="primary"):
                    remove_event(event.id)
                    st.session_state.pop(f"confirm_del_{event.id}", None)
                    st.toast("삭제되었습니다.", icon="🗑️")
                    st.rerun()
            with dc2:
                if st.button("취소", key=f"del_cancel_{event.id}"):
                    st.session_state.pop(f"confirm_del_{event.id}", None)
                    st.rerun()

    st.divider()


# ─── 필터 팝업 ────────────────────────────────────────────────

def _open_filter_dialog() -> None:
    ss = st.session_state
    ss["dlg_filter_courses"] = list(ss.get("list_filter_courses", []))
    ss["dlg_filter_types"]   = list(ss.get("list_filter_types", []))
    ss["dlg_filter_done"]    = ss.get("list_filter_done", "TODO")
    ss["dlg_filter_domain"]  = ss.get("list_filter_domain", "전체")


def _reset_dlg_filters() -> None:
    st.session_state["dlg_filter_courses"] = []
    st.session_state["dlg_filter_types"]   = []
    st.session_state["dlg_filter_done"]    = "TODO"
    st.session_state["dlg_filter_domain"]  = "전체"


@st.dialog("필터", width="large")
def _filter_dialog(course_map: dict) -> None:
    st.radio(
        "도메인",
        ["전체", "수업", "학사", "개인"],
        horizontal=True,
        key="dlg_filter_domain",
    )
    r1, r2 = st.columns(2)
    with r1:
        st.multiselect(
            "과목 (수업 일정만)",
            options=list(course_map.keys()),
            format_func=lambda c: course_map[c].name,
            key="dlg_filter_courses",
        )
    with r2:
        st.multiselect(
            "종류",
            options=ALL_TYPES_ORDER,
            format_func=lambda k: EVENT_LABEL_MAP[k],
            key="dlg_filter_types",
        )
    st.radio(
        "표시 범위",
        ["TODO", "완료", "전체"],
        horizontal=True,
        key="dlg_filter_done",
        captions=[
            "현재 진행 가능한 일정만 — 오픈 전·마감 경과·완료 항목 제외",
            "완료·자동 완료된 일정",
            "모든 일정",
        ],
    )
    st.divider()
    bc1, bc2 = st.columns(2)
    with bc1:
        st.button("초기화", use_container_width=True, key="filter_reset", on_click=_reset_dlg_filters)
    with bc2:
        if st.button("적용", type="primary", use_container_width=True, key="filter_apply"):
            ss = st.session_state
            ss["list_filter_courses"] = list(ss.get("dlg_filter_courses", []))
            ss["list_filter_types"]   = list(ss.get("dlg_filter_types", []))
            ss["list_filter_done"]    = ss.get("dlg_filter_done", "TODO")
            ss["list_filter_domain"]  = ss.get("dlg_filter_domain", "전체")
            st.rerun()


# ─── Main ─────────────────────────────────────────────────────

def run():
    for key, default in [
        ("list_filter_done",    "TODO"),
        ("list_filter_courses", []),
        ("list_filter_types",   []),
        ("list_filter_domain",  "전체"),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    data = load()

    _any_filter = bool(
        st.session_state["list_filter_courses"]
        or st.session_state["list_filter_types"]
        or st.session_state["list_filter_done"] != "TODO"
        or st.session_state["list_filter_domain"] != "전체"
    )

    col_title, col_filter, col_add = st.columns([6, 1.4, 1.4])
    with col_title:
        st.title("일정 관리")
    with col_filter:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button(
            "🔍 필터",
            use_container_width=True,
            key="open_filter_dialog",
            type="primary" if _any_filter else "secondary",
            on_click=_open_filter_dialog,
        ):
            _filter_dialog(get_course_map(data))
    with col_add:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button("＋ 일정 추가", type="primary", use_container_width=True, key="open_add_dialog"):
            _add_event_dialog(data.courses)

    course_map = get_course_map(data)
    today      = date.today()

    # ── 필터 적용 ─────────────────────────────────────────────
    sel_courses = st.session_state["list_filter_courses"]
    sel_types   = st.session_state["list_filter_types"]
    sel_done    = st.session_state["list_filter_done"]
    sel_domain  = st.session_state["list_filter_domain"]

    domain_map = {"수업": "course", "학사": "academic", "개인": "personal"}

    events = data.events
    if sel_domain != "전체":
        d_key = domain_map.get(sel_domain, sel_domain)
        events = [e for e in events if getattr(e, "domain", "course") == d_key]
    if sel_courses:
        events = [e for e in events if e.course_code in sel_courses]
    if sel_types:
        events = [e for e in events if e.event_type_key() in sel_types]
    if sel_done == "TODO":
        now    = datetime.now()
        events = [e for e in events if is_todo(e, now)]
    elif sel_done == "완료":
        now    = datetime.now()
        events = [e for e in events if e.completed or timed_auto_done(e)]

    events = sorted(events, key=lambda e: (e.sort_at() or datetime.max))

    if not events:
        st.info("표시할 일정이 없습니다. 오른쪽 상단 **＋ 일정 추가** 버튼을 눌러 일정을 추가하세요.")
    else:
        st.caption(f"{len(events)}건")
        for evt in events:
            _render_event_row(evt, course_map, today, data.courses)


run()
