from __future__ import annotations

import uuid
from datetime import date, time

import streamlit as st

from core.models import (
    EVENT_TYPE_MAP, EVENT_LABEL_MAP, EVENT_ICON_MAP,
    ALL_TYPES_ORDER, VISIBLE_TYPES,
    WindowCycleRule, PeriodWeeklyRule, DueWeeklyRule,
    WEEKDAY_KO,
)
from core.period import PERIOD_LABELS
from core.storage import load, add_rule, remove_rule, update_rule, get_course_map
from core.rule_engine import expand_rule, regenerate_rule, rule_preview

# Event types grouped by timing mode (visible + legacy)
_PERIOD_TYPES   = {"quiz", "zoom_meeting", "exam"}
_WINDOW_TYPES   = {"assignment", "vod", "team_project"}
_DEADLINE_TYPES = {
    "poll", "board", "survey",
    "forum", "wiki", "file", "folder", "label", "url",
}


_PATTERN_LABELS = {
    "window_cycle":  "기간형 (시작교시 → 마감 요일+시각)",
    "period_weekly": "교시형 (매주 요일+교시구간)",
    "due_weekly":    "마감형 (매주 요일+시각)",
}


def _default_pattern(type_key: str) -> str:
    if type_key in _WINDOW_TYPES:  return "window_cycle"
    if type_key in _PERIOD_TYPES:  return "period_weekly"
    return "due_weekly"


def _rule_summary(rule) -> str:
    wk = WEEKDAY_KO
    if isinstance(rule, WindowCycleRule):
        offset_str = "같은주" if rule.due_week_offset == 0 else f"{rule.due_week_offset}주 후"
        return (
            f"매주 {wk[rule.open_weekday]} {rule.open_period}교시 생성 → "
            f"{offset_str} {wk[rule.due_weekday]} {rule.due_time} 마감"
        )
    elif isinstance(rule, PeriodWeeklyRule):
        return (
            f"매주 {wk[rule.occurrence_weekday]} "
            f"{rule.start_period}~{rule.end_period}교시"
        )
    elif isinstance(rule, DueWeeklyRule):
        return f"매주 {wk[rule.due_weekday]} {rule.due_time} 마감"
    return ""


def _count_events(rule_id: str, data) -> int:
    return sum(1 for e in data.events if e.rule_id == rule_id)


def _rule_form(
    courses,
    default_values: dict | None = None,
    form_key: str = "add_rule_form",
) -> dict | None:
    dv = default_values or {}

    if not courses:
        st.warning("수강 과목을 먼저 등록하세요.")
        return None

    # Course
    course_opts = [c.code for c in courses]
    course_code = st.selectbox(
        "과목",
        options=course_opts,
        index=course_opts.index(dv.get("course_code", course_opts[0]))
              if dv.get("course_code") in course_opts else 0,
        format_func=lambda c: next((x.name for x in courses if x.code == c), c),
        key=f"{form_key}_course",
    )

    # Event type (UI에서는 VISIBLE_TYPES 6개만 표시)
    _ev_default = dv.get("event_type", "assignment")
    if _ev_default not in VISIBLE_TYPES:
        _ev_default = "assignment"
    type_key = st.selectbox(
        "일정 종류",
        options=VISIBLE_TYPES,
        index=VISIBLE_TYPES.index(_ev_default),
        format_func=lambda k: EVENT_LABEL_MAP[k],
        key=f"{form_key}_type",
    )

    # Pattern (auto-suggested)
    suggested = _default_pattern(type_key)
    pattern_opts = list(_PATTERN_LABELS.keys())
    pattern = st.selectbox(
        "반복 패턴",
        options=pattern_opts,
        index=pattern_opts.index(dv.get("pattern", suggested)),
        format_func=lambda p: _PATTERN_LABELS[p],
        key=f"{form_key}_pattern",
    )

    # Title template
    title_template = st.text_input(
        "제목 템플릿",
        value=dv.get("title_template", f"{{week}}주차 {EVENT_LABEL_MAP[type_key]}"),
        help="{week}=주차 번호, {label}=유형 한국어명",
        key=f"{form_key}_title_tpl",
    )

    # Date range
    data = load()
    sem = data.semester
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input(
            "시작일",
            value=date.fromisoformat(dv.get("start_date", sem["start_date"])),
            key=f"{form_key}_start",
        )
    with c2:
        end_date = st.date_input(
            "종료일",
            value=date.fromisoformat(dv.get("end_date", sem["end_date"])),
            key=f"{form_key}_end",
        )

    st.divider()

    result: dict = {
        "course_code":     course_code,
        "event_type":      type_key,
        "pattern":         pattern,
        "title_template":  title_template,
        "start_date":      start_date.isoformat(),
        "end_date":        end_date.isoformat(),
    }

    # Pattern-specific fields
    if pattern == "window_cycle":
        st.markdown("**생성 시점 (매주 열리는 날)**")
        c1, c2 = st.columns(2)
        with c1:
            open_weekday = st.selectbox(
                "요일",
                options=list(range(7)),
                index=dv.get("open_weekday", 2),
                format_func=lambda x: WEEKDAY_KO[x],
                key=f"{form_key}_open_wd",
            )
        with c2:
            open_period = st.selectbox(
                "교시 (open_at)",
                options=list(PERIOD_LABELS.keys()),
                format_func=lambda x: PERIOD_LABELS[x],
                index=dv.get("open_period", 1) - 1,
                key=f"{form_key}_open_p",
            )

        st.markdown("**마감 시점**")
        c1, c2, c3 = st.columns(3)
        with c1:
            due_weekday = st.selectbox(
                "요일",
                options=list(range(7)),
                index=dv.get("due_weekday", 1),
                format_func=lambda x: WEEKDAY_KO[x],
                key=f"{form_key}_due_wd",
            )
        with c2:
            due_week_offset = st.selectbox(
                "주차 offset",
                options=[0, 1, 2],
                index=dv.get("due_week_offset", 1),
                format_func=lambda x: ("같은 주" if x == 0 else f"{x}주 후"),
                key=f"{form_key}_due_off",
            )
        with c3:
            due_time_str = st.text_input(
                "마감 시각 (HH:MM)",
                value=dv.get("due_time", "23:59"),
                key=f"{form_key}_due_time",
            )

        result.update({
            "open_weekday":    open_weekday,
            "open_period":     open_period,
            "due_weekday":     due_weekday,
            "due_week_offset": due_week_offset,
            "due_time":        due_time_str,
        })

    elif pattern == "period_weekly":
        st.markdown("**매주 발생 요일 및 교시**")
        c1, c2, c3 = st.columns(3)
        with c1:
            occurrence_weekday = st.selectbox(
                "요일",
                options=list(range(7)),
                index=dv.get("occurrence_weekday", 4),
                format_func=lambda x: WEEKDAY_KO[x],
                key=f"{form_key}_occ_wd",
            )
        with c2:
            start_period = st.selectbox(
                "시작 교시",
                options=list(PERIOD_LABELS.keys()),
                format_func=lambda x: PERIOD_LABELS[x],
                index=dv.get("start_period", 1) - 1,
                key=f"{form_key}_sp",
            )
        with c3:
            ep_opts = [x for x in PERIOD_LABELS if x >= start_period]
            end_period = st.selectbox(
                "종료 교시",
                options=ep_opts,
                format_func=lambda x: PERIOD_LABELS[x],
                index=0,
                key=f"{form_key}_ep",
            )

        result.update({
            "occurrence_weekday": occurrence_weekday,
            "start_period":       start_period,
            "end_period":         end_period,
        })

    else:  # due_weekly
        st.markdown("**매주 마감 요일 및 시각**")
        c1, c2 = st.columns(2)
        with c1:
            due_weekday = st.selectbox(
                "요일",
                options=list(range(7)),
                index=dv.get("due_weekday", 4),
                format_func=lambda x: WEEKDAY_KO[x],
                key=f"{form_key}_due_wd",
            )
        with c2:
            due_time_str = st.text_input(
                "마감 시각 (HH:MM)",
                value=dv.get("due_time", "23:59"),
                key=f"{form_key}_due_time",
            )

        result.update({
            "due_weekday": due_weekday,
            "due_time":    due_time_str,
        })

    # Preview
    preview_rule = _build_rule_obj("preview_rule_id", result)
    if preview_rule:
        sem_start = load().semester["start_date"]
        preview = rule_preview(preview_rule, sem_start)
        if preview:
            st.info(f"첫 주 미리보기: {preview}")

    return result


def _build_rule_obj(rule_id: str, d: dict):
    pattern = d.get("pattern")
    base = dict(
        id=rule_id,
        course_code=d["course_code"],
        event_type=d["event_type"],
        title_template=d.get("title_template", ""),
        start_date=d["start_date"],
        end_date=d["end_date"],
    )
    try:
        if pattern == "window_cycle":
            return WindowCycleRule(
                **base,
                open_weekday=d["open_weekday"],
                open_period=d["open_period"],
                due_weekday=d["due_weekday"],
                due_week_offset=d["due_week_offset"],
                due_time=d["due_time"],
            )
        elif pattern == "period_weekly":
            return PeriodWeeklyRule(
                **base,
                occurrence_weekday=d["occurrence_weekday"],
                start_period=d["start_period"],
                end_period=d["end_period"],
            )
        elif pattern == "due_weekly":
            return DueWeeklyRule(
                **base,
                due_weekday=d["due_weekday"],
                due_time=d["due_time"],
            )
    except (KeyError, TypeError):
        return None


def run():
    st.title("반복 규칙")
    st.caption("학기 전체 반복 일정 패턴을 등록하면 일정이 자동 생성됩니다.")

    data = load()
    if not data.courses:
        st.warning("수강 과목을 먼저 등록하세요. → **수강 과목** 페이지")
        return

    course_map = get_course_map(data)

    # Edit mode
    if "editing_rule_id" in st.session_state:
        rule_id = st.session_state["editing_rule_id"]
        rule = next((r for r in data.rules if r.id == rule_id), None)
        if rule is None:
            st.session_state.pop("editing_rule_id")
        else:
            st.subheader(f"규칙 수정: {rule.title_template}")
            st.warning("수정 시 이 규칙의 미완료 일정이 삭제되고 재생성됩니다.")
            dv = rule.to_dict()
            form_data = _rule_form(data.courses, default_values=dv, form_key="edit_rule_form")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("저장 및 재생성", type="primary", key="save_edit_rule"):
                    if not form_data or not form_data.get("title_template"):
                        st.error("제목 템플릿을 입력하세요.")
                    elif form_data["start_date"] >= form_data["end_date"]:
                        st.error("종료일은 시작일보다 이후여야 합니다.")
                    else:
                        # update rule fields
                        new_rule = _build_rule_obj(rule_id, form_data)
                        if new_rule:
                            from core.storage import save as ssave
                            d2 = load()
                            d2.rules = [new_rule if r.id == rule_id else r for r in d2.rules]
                            ssave(d2)
                            new_events = regenerate_rule(rule_id)
                            st.session_state.pop("editing_rule_id")
                            st.success(f"규칙 수정 완료. {len(new_events)}개 일정 재생성.")
                            st.rerun()
            with c2:
                if st.button("취소", key="cancel_edit_rule"):
                    st.session_state.pop("editing_rule_id")
                    st.rerun()
            return

    tab_add, tab_list = st.tabs(["규칙 추가", "규칙 목록"])

    with tab_add:
        form_data = _rule_form(data.courses, form_key="new_rule_form")

        st.divider()
        if st.button("저장 및 일정 생성", type="primary", key="save_new_rule"):
            if not form_data or not form_data.get("title_template"):
                st.error("제목 템플릿을 입력하세요.")
            elif form_data["start_date"] >= form_data["end_date"]:
                st.error("종료일은 시작일보다 이후여야 합니다.")
            else:
                rule_id = str(uuid.uuid4())
                new_rule = _build_rule_obj(rule_id, form_data)
                if new_rule is None:
                    st.error("규칙 생성 실패. 입력값을 확인하세요.")
                else:
                    add_rule(new_rule)
                    new_events = expand_rule(new_rule)
                    from core.storage import add_event
                    for evt in new_events:
                        add_event(evt)
                    st.success(f"규칙 저장 완료! {len(new_events)}개 일정 생성됨.")
                    st.rerun()

    with tab_list:
        data = load()
        if not data.rules:
            st.info("등록된 반복 규칙이 없습니다.")
            return

        for rule in data.rules:
            course = course_map.get(rule.course_code)
            cname  = course.name if course else rule.course_code
            ccolor = course.color if course else "#999"
            cnt    = _count_events(rule.id, data)
            label  = EVENT_LABEL_MAP.get(rule.event_type, rule.event_type)
            icon   = EVENT_ICON_MAP.get(rule.event_type, "")

            with st.container(border=True):
                col_icon, col_info, col_actions = st.columns([0.5, 6, 2])
                with col_icon:
                    if icon:
                        st.image(icon, width=28)
                with col_info:
                    st.markdown(
                        f'<span style="color:{ccolor}; font-weight:bold;">[{cname}]</span> '
                        f'**{rule.title_template}** · {label}',
                        unsafe_allow_html=True,
                    )
                    st.caption(_rule_summary(rule))
                    st.caption(
                        f"{rule.start_date} ~ {rule.end_date} | "
                        f"생성 일정 {cnt}건 | "
                        f"{'✅ 활성' if rule.enabled else '⏸ 비활성'}"
                    )
                with col_actions:
                    if st.button("수정", key=f"edit_rule_{rule.id}", use_container_width=True):
                        st.session_state["editing_rule_id"] = rule.id
                        st.rerun()
                    if st.button("재생성", key=f"regen_{rule.id}", use_container_width=True):
                        st.session_state[f"confirm_regen_{rule.id}"] = True
                    if st.button("삭제", key=f"del_rule_{rule.id}", use_container_width=True):
                        st.session_state[f"confirm_del_rule_{rule.id}"] = True

                if st.session_state.get(f"confirm_regen_{rule.id}"):
                    st.warning("미완료 연결 일정이 삭제되고 재생성됩니다. 진행률이 초기화됩니다.")
                    r1, r2 = st.columns(2)
                    with r1:
                        if st.button("재생성 확인", key=f"regen_ok_{rule.id}", type="primary"):
                            new_evts = regenerate_rule(rule.id)
                            st.session_state.pop(f"confirm_regen_{rule.id}")
                            st.success(f"{len(new_evts)}개 재생성 완료")
                            st.rerun()
                    with r2:
                        if st.button("취소", key=f"regen_cancel_{rule.id}"):
                            st.session_state.pop(f"confirm_regen_{rule.id}")
                            st.rerun()

                if st.session_state.get(f"confirm_del_rule_{rule.id}"):
                    st.warning(f"규칙 및 연결된 모든 일정({cnt}건)이 삭제됩니다.")
                    d1, d2 = st.columns(2)
                    with d1:
                        if st.button("삭제 확인", key=f"del_rule_ok_{rule.id}", type="primary"):
                            remove_rule(rule.id)
                            st.session_state.pop(f"confirm_del_rule_{rule.id}")
                            st.success("규칙 삭제 완료")
                            st.rerun()
                    with d2:
                        if st.button("취소", key=f"del_rule_cancel_{rule.id}"):
                            st.session_state.pop(f"confirm_del_rule_{rule.id}")
                            st.rerun()


run()
