from __future__ import annotations

import streamlit as st

from core.storage import load, get_course_map
from core.models import EVENT_LABEL_MAP
from core.io import export_json, import_json, export_ics


def run():
    st.title("가져오기 / 내보내기")

    tab_json, tab_ics = st.tabs(["JSON (완전 백업)", "ICS (외부 캘린더 연동)"])

    data = load()

    with tab_json:
        st.subheader("JSON 내보내기")
        st.caption("모든 과목·규칙·일정을 JSON 파일로 저장합니다.")

        json_bytes = export_json(data)
        sem = data.semester
        filename = f"exam_planner_{sem.get('year', 2026)}-{sem.get('term', 1)}.json"

        st.download_button(
            label="JSON 내보내기",
            data=json_bytes,
            file_name=filename,
            mime="application/json",
            type="primary",
        )

        st.caption(
            f"포함: 과목 {len(data.courses)}개 · 규칙 {len(data.rules)}개 · "
            f"일정 {len(data.events)}개"
        )

        st.divider()
        st.subheader("JSON 가져오기")
        st.caption(
            "이전에 내보낸 JSON 파일을 가져옵니다. "
            "**전체 교체** 또는 **병합** 모드를 선택하세요."
        )

        uploaded = st.file_uploader("JSON 파일 선택", type=["json"], key="json_upload")
        if uploaded:
            import json as _json
            try:
                raw = _json.loads(uploaded.read())
                st.info(
                    f"파일 내용: 과목 {len(raw.get('courses', []))}개 · "
                    f"규칙 {len(raw.get('rules', []))}개 · "
                    f"일정 {len(raw.get('events', []))}개 (버전 {raw.get('version')})"
                )
                mode = st.radio(
                    "가져오기 모드",
                    options=["전체 교체", "병합 (기존 데이터 유지)"],
                    key="json_import_mode",
                )
                mode_key = "replace" if mode == "전체 교체" else "merge"

                if st.button("가져오기 실행", type="primary", key="run_json_import"):
                    try:
                        raw_bytes = _json.dumps(raw).encode("utf-8")
                        _, msg = import_json(raw_bytes, mode=mode_key)
                        st.success(msg)
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            except Exception as e:
                st.error(f"파일 파싱 오류: {e}")

    with tab_ics:
        st.subheader("ICS 내보내기")
        st.caption(
            "Google Calendar, Apple Calendar 등 외부 캘린더 앱에서 가져올 수 있는 "
            "`.ics` 파일을 생성합니다. **가져오기(import)는 지원하지 않습니다.**"
        )

        course_map = get_course_map(data)

        ic1, ic2 = st.columns(2)
        with ic1:
            ics_courses = st.multiselect(
                "과목 필터 (비워두면 전체)",
                options=[c.code for c in data.courses],
                format_func=lambda c: course_map[c].name if c in course_map else c,
                key="ics_courses",
            )
        with ic2:
            ics_types = st.multiselect(
                "종류 필터 (비워두면 전체)",
                options=list(EVENT_LABEL_MAP.keys()),
                format_func=lambda k: EVENT_LABEL_MAP[k],
                key="ics_types",
            )

        excl_completed = st.checkbox("완료된 일정 제외", value=True, key="ics_excl_done")
        preview_events = data.events
        if ics_courses:
            preview_events = [e for e in preview_events if e.course_code in ics_courses]
        if ics_types:
            preview_events = [e for e in preview_events if e.event_type_key() in ics_types]
        if excl_completed:
            preview_events = [e for e in preview_events if not e.completed]
        valid_preview = [e for e in preview_events if e.sort_at() is not None]

        st.info(f"내보낼 일정: {len(valid_preview)}건")

        sem = data.semester
        ics_filename = f"exam_planner_{sem.get('year', 2026)}-{sem.get('term', 1)}.ics"

        if st.button("ICS 생성", type="primary", key="gen_ics"):
            try:
                ics_bytes = export_ics(
                    data=data,
                    course_codes=ics_courses or None,
                    event_types=ics_types or None,
                    exclude_completed=excl_completed,
                )
                st.download_button(
                    label="ICS 파일 다운로드",
                    data=ics_bytes,
                    file_name=ics_filename,
                    mime="text/calendar",
                    type="primary",
                    key="dl_ics",
                )
                st.success(f"{len(valid_preview)}개 일정이 ICS 파일로 준비되었습니다.")
            except Exception as e:
                st.error(f"ICS 생성 오류: {e}")


run()
