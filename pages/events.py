"""pages/events.py — 일정 CRUD + progress UI"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time

import streamlit as st

from core.models import (
    EVENT_TYPE_MAP, EVENT_LABEL_MAP, EVENT_ICON_MAP,
    ALL_TYPES_ORDER, VISIBLE_TYPES,
    PeriodEvent, WindowEvent, DeadlineEvent,
)
from core.period import PERIOD_LABELS, periods_to_range
from core.storage import (
    load, add_event, update_event, remove_event,
    set_event_progress, toggle_event_completed,
    get_course_map,
)
from core.dday import calc_dday, dday_label, dday_color
from core.progress import progress_color, progress_bar_html
from core.rule_engine import week_number


_PERIOD_TYPES   = {"quiz", "zoom_meeting", "exam"}
_WINDOW_TYPES   = {"assignment", "vod", "group_evaluation"}
_DEADLINE_TYPES = {
    "poll", "board", "survey",
    "forum", "wiki", "file", "folder", "label", "url",
}


def _timing_mode(type_key: str) -> str:
    if type_key in _PERIOD_TYPES:  return "period"
    if type_key in _WINDOW_TYPES:  return "window"
    return "deadline"


# ─── 진행률/완료 on_change 콜백 (렌더 전에 실행 → session state 탈동기화 방지) ─

def _cb_done(event_id: str) -> None:
    """완료 체크박스 콜백: DB 저장 + 슬라이더 session state 동기화"""
    done = st.session_state[f"done_{event_id}"]
    evt  = toggle_event_completed(event_id, done)
    st.session_state[f"prog_{event_id}"] = evt.progress


def _cb_prog(event_id: str) -> None:
    """진행률 슬라이더 콜백: DB 저장 + 체크박스 session state 동기화"""
    prog = st.session_state[f"prog_{event_id}"]
    evt  = set_event_progress(event_id, prog)
    st.session_state[f"done_{event_id}"] = evt.completed


def _week_num(event) -> int | None:
    data = load()
    sem_start = date.fromisoformat(data.semester["start_date"])
    sa = event.sort_at()
    return week_number(sa.date(), sem_start) if sa else None


# ─── 일정 종류 선택 그리드 (UI 표시 6종, 1행) ─────────────────

def _set_type(ss_key: str, key: str) -> None:
    """on_click 콜백 — 렌더링 전에 session state를 갱신해 딜레이 방지."""
    st.session_state[ss_key] = key


def _type_selector(form_key: str, default_key: str = "vod") -> str:
    st.markdown("**일정 종류**")
    ss_key = f"{form_key}_selected_type"
    if ss_key not in st.session_state or st.session_state[ss_key] not in VISIBLE_TYPES:
        st.session_state[ss_key] = default_key

    cols = st.columns(6)
    for key, col in zip(VISIBLE_TYPES, cols):
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


# ─── 입력 폼 (추가 / 수정 공용) ──────────────────────────────

def _event_form(
    courses: list,
    form_key: str,
    default_type: str = "quiz",
    default_values: dict | None = None,
) -> dict | None:
    dv = default_values or {}

    if not courses:
        st.warning("수강 과목을 먼저 등록해 주세요.")
        return None

    course_opts = [c.code for c in courses]
    default_idx = (
        course_opts.index(dv["course_code"])
        if dv.get("course_code") in course_opts else 0
    )
    course_code = st.selectbox(
        "과목",
        options=course_opts,
        index=default_idx,
        format_func=lambda c: next((x.name for x in courses if x.code == c), c),
        key=f"{form_key}_course",
    )

    type_key = _type_selector(form_key, dv.get("event_type", default_type))
    mode     = _timing_mode(type_key)

    st.divider()

    title = st.text_input("제목 *", value=dv.get("title", ""), key=f"{form_key}_title")
    desc  = st.text_area("메모", value=dv.get("description", ""), height=68, key=f"{form_key}_desc")

    result: dict = {
        "course_code": course_code,
        "event_type":  type_key,
        "title":       title,
        "description": desc,
    }

    st.divider()

    if mode == "period":
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
            result.update({
                "start_at": s_dt.isoformat(), "end_at": e_dt.isoformat(),
                "start_period": sp, "end_period": ep,
            })
        except ValueError as e:
            st.error(str(e))

    elif mode == "window":
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
    cls      = EVENT_TYPE_MAP[type_key]
    valid    = {f.name for f in dc_fields(cls)}
    evt      = cls(id=str(uuid.uuid4()), **{k: v for k, v in form_data.items() if k in valid})
    evt.week_number = _week_num(evt)
    add_event(evt)


# ─── 일정 추가 팝업 (st.dialog) ──────────────────────────────

@st.dialog("일정 추가", width="large")
def _add_event_dialog(courses: list) -> None:
    form_data = _event_form(courses, form_key="dlg_add")

    st.divider()
    if st.button("저장", type="primary", key="dlg_save_btn", use_container_width=True):
        if not form_data or not form_data.get("title", "").strip():
            st.error("제목을 입력하세요.")
        elif form_data.get("event_type") in _PERIOD_TYPES and not form_data.get("start_at"):
            st.error("날짜와 교시를 입력하세요.")
        elif form_data.get("event_type") in (_WINDOW_TYPES | _DEADLINE_TYPES) and not form_data.get("due_at"):
            st.error("마감일을 입력하세요.")
        else:
            _save_new_event(form_data)
            st.toast("일정이 추가되었습니다!", icon="✅")
            st.rerun()


# ─── 수정 팝업 (st.dialog) ────────────────────────────────────

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

    form_data = _event_form(
        courses,
        form_key="dlg_edit",
        default_type=event.event_type_key(),
        default_values=event.to_dict(),
    )

    st.divider()
    if st.button("저장", type="primary", key="dlg_edit_save", use_container_width=True):
        if form_data and form_data.get("title", "").strip():
            form_data.pop("event_type")
            update_event(event_id, **form_data)
            st.toast("수정 완료!", icon="✅")
            st.rerun()
        else:
            st.error("제목을 입력하세요.")


# ─── 일정 목록 행 ────────────────────────────────────────────

def _render_event_row(event, course_map: dict, today: date, courses: list) -> None:
    course       = course_map.get(event.course_code)
    course_name  = course.name  if course else event.course_code
    course_color = course.color if course else "#999"

    dday  = calc_dday(event, today)

    with st.container():
        col_icon, col_info, col_meta = st.columns([0.5, 6, 2.5])

        with col_icon:
            st.image(event.icon_path(), width=28)

        with col_info:
            done_style = "text-decoration:line-through; color:#aaa;" if event.completed else ""
            st.markdown(
                f'<span style="font-size:12px; color:{course_color}; font-weight:bold;">[{course_name}]</span> '
                f'<span style="{done_style}">{event.title}</span>',
                unsafe_allow_html=True,
            )
            if isinstance(event, PeriodEvent) and event.start_at:
                p_info = (
                    f" ({event.start_period}~{event.end_period}교시)"
                    if event.start_period and event.end_period else ""
                )
                st.caption(
                    f"{datetime.fromisoformat(event.start_at).strftime('%m/%d(%a) %H:%M')}"
                    f" ~ {datetime.fromisoformat(event.end_at).strftime('%H:%M')}{p_info}"
                )
            elif isinstance(event, WindowEvent):
                if event.open_at:
                    st.caption(
                        f"{datetime.fromisoformat(event.open_at).strftime('%m/%d %H:%M')}"
                        f" ~ {datetime.fromisoformat(event.due_at).strftime('%m/%d %H:%M')}"
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
# 다이얼로그는 dlg_filter_* 키(임시 작업용)를 사용하고,
# "적용" 시에만 list_filter_* (실제 적용 키)로 반영합니다.
# 이렇게 분리해야 "다시 열었을 때 현재 적용값"이 정확히 보입니다.

def _open_filter_dialog() -> None:
    """필터 버튼 on_click — 적용 값을 다이얼로그 임시 키로 복사."""
    ss = st.session_state
    ss["dlg_filter_courses"] = list(ss.get("list_filter_courses", []))
    ss["dlg_filter_types"]   = list(ss.get("list_filter_types", []))
    ss["dlg_filter_done"]    = ss.get("list_filter_done", "미완료")


def _reset_dlg_filters() -> None:
    """초기화 버튼 on_click — 다이얼로그 임시 키만 리셋."""
    st.session_state["dlg_filter_courses"] = []
    st.session_state["dlg_filter_types"]   = []
    st.session_state["dlg_filter_done"]    = "미완료"


@st.dialog("필터", width="large")
def _filter_dialog(course_map: dict) -> None:
    r1, r2 = st.columns(2)
    with r1:
        st.multiselect(
            "과목",
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
        ["미완료", "완료", "전체"],
        horizontal=True,
        key="dlg_filter_done",
    )
    st.divider()
    bc1, bc2 = st.columns(2)
    with bc1:
        st.button(
            "초기화",
            use_container_width=True,
            key="filter_reset",
            on_click=_reset_dlg_filters,
        )
    with bc2:
        if st.button("적용", type="primary", use_container_width=True, key="filter_apply"):
            # 다이얼로그 임시값 → 실제 적용 키로 반영 후 닫기
            ss = st.session_state
            ss["list_filter_courses"] = list(ss.get("dlg_filter_courses", []))
            ss["list_filter_types"]   = list(ss.get("dlg_filter_types", []))
            ss["list_filter_done"]    = ss.get("dlg_filter_done", "미완료")
            st.rerun()


# ─── Main ────────────────────────────────────────────────────

def run():
    # ── 필터 적용 session state 기본값 초기화 ────────────────
    if "list_filter_done" not in st.session_state:
        st.session_state["list_filter_done"] = "미완료"
    if "list_filter_courses" not in st.session_state:
        st.session_state["list_filter_courses"] = []
    if "list_filter_types" not in st.session_state:
        st.session_state["list_filter_types"] = []

    data = load()

    # 기본값(미완료 + 필터 없음)과 다르면 버튼 강조
    _any_filter = bool(
        st.session_state["list_filter_courses"]
        or st.session_state["list_filter_types"]
        or st.session_state["list_filter_done"] != "미완료"
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
            on_click=_open_filter_dialog,   # 열기 전에 현재값 복사
        ):
            if data.courses:
                _filter_dialog(get_course_map(data))
    with col_add:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button("＋ 일정 추가", type="primary", use_container_width=True, key="open_add_dialog"):
            if not data.courses:
                st.warning("수강 과목을 먼저 등록하세요.")
            else:
                _add_event_dialog(data.courses)

    if not data.courses:
        st.warning("수강 과목을 먼저 등록해 주세요. → **수강 과목** 페이지")
        return

    course_map = get_course_map(data)
    today      = date.today()

    # ── 필터 적용 ─────────────────────────────────────────────
    sel_courses = st.session_state["list_filter_courses"]
    sel_types   = st.session_state["list_filter_types"]
    sel_done    = st.session_state["list_filter_done"]

    events = data.events
    if sel_courses:
        events = [e for e in events if e.course_code in sel_courses]
    if sel_types:
        events = [e for e in events if e.event_type_key() in sel_types]
    if sel_done == "미완료":
        events = [e for e in events if not e.completed]
    elif sel_done == "완료":
        events = [e for e in events if e.completed]

    events = sorted(events, key=lambda e: (e.sort_at() or datetime.max))

    if not events:
        st.info("표시할 일정이 없습니다. 오른쪽 상단 **＋ 일정 추가** 버튼을 눌러 일정을 추가하세요.")
    else:
        st.caption(f"{len(events)}건")
        for evt in events:
            _render_event_row(evt, course_map, today, data.courses)


run()
