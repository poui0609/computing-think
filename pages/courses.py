"""pages/courses.py — 수강 과목 등록/관리"""
import re
import streamlit as st

from core.storage import (
    load, add_course, remove_course, update_course, load_course_mapping,
)

COURSE_CODE_PATTERN = re.compile(r"^[A-Z]{2,4}\d{3,5}$")


def run():
    st.title("수강 과목")
    st.caption("이번 학기 수강 중인 과목을 학정번호로 등록합니다.")

    mapping = load_course_mapping()
    data = load()

    # ── 과목 추가 폼 ─────────────────────────────────────────
    with st.expander("과목 추가", expanded=len(data.courses) == 0):
        code_input = st.text_input(
            "학정번호",
            placeholder="예: SWE3007",
            key="course_code_input",
        ).strip().upper()

        auto_name = mapping.get(code_input, "")
        if code_input and auto_name:
            st.success(f"매핑 확인: **{auto_name}**")
            name_input = auto_name
        elif code_input:
            st.warning("CourseMapping에 없는 학정번호입니다. 과목명을 직접 입력하세요.")
            name_input = st.text_input("과목명", key="course_name_input").strip()
        else:
            name_input = ""

        if st.button("추가", type="primary", key="add_course_btn"):
            if not code_input:
                st.error("학정번호를 입력하세요.")
            elif not COURSE_CODE_PATTERN.match(code_input):
                st.error("학정번호 형식이 올바르지 않습니다. (예: SWE3007)")
            elif not name_input:
                st.error("과목명을 입력하거나 학정번호를 다시 확인하세요.")
            else:
                try:
                    course = add_course(code_input, name_input)
                    st.success(f"{course.code} — {course.name} 등록 완료!")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    st.divider()

    # ── 등록된 과목 목록 ─────────────────────────────────────
    data = load()
    if not data.courses:
        st.info("등록된 과목이 없습니다. 위에서 과목을 추가하세요.")
        return

    st.subheader(f"등록된 과목 ({len(data.courses)}개)")

    for course in data.courses:
        col1, col2, col3 = st.columns([0.3, 6, 1.2])
        with col1:
            st.markdown(
                f'<div style="width:24px; height:24px; border-radius:50%; '
                f'background:{course.color}; margin-top:8px;"></div>',
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(f"**{course.code}** &nbsp; {course.name}")
            event_count = sum(1 for e in data.events if e.course_code == course.code)
            rule_count  = sum(1 for r in data.rules  if r.course_code == course.code)
            st.caption(f"일정 {event_count}건 · 규칙 {rule_count}개")
        with col3:
            if st.button("삭제", key=f"del_{course.code}", type="secondary"):
                st.session_state[f"confirm_del_{course.code}"] = True

        if st.session_state.get(f"confirm_del_{course.code}"):
            with st.container():
                st.warning(
                    f"**{course.name}** 과목과 연결된 모든 일정·규칙이 삭제됩니다. 계속할까요?"
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("삭제 확인", key=f"del_confirm_{course.code}", type="primary"):
                        remove_course(course.code)
                        st.session_state.pop(f"confirm_del_{course.code}", None)
                        st.success(f"{course.name} 삭제 완료")
                        st.rerun()
                with c2:
                    if st.button("취소", key=f"del_cancel_{course.code}"):
                        st.session_state.pop(f"confirm_del_{course.code}", None)
                        st.rerun()
        st.divider()

    # ── 학기 설정 ────────────────────────────────────────────
    with st.expander("학기 설정"):
        data = load()
        sem = data.semester
        col1, col2 = st.columns(2)
        with col1:
            new_start = st.date_input(
                "학기 시작일",
                value=__import__("datetime").date.fromisoformat(sem["start_date"]),
                key="sem_start",
            )
        with col2:
            new_end = st.date_input(
                "학기 종료일",
                value=__import__("datetime").date.fromisoformat(sem["end_date"]),
                key="sem_end",
            )
        if st.button("저장", key="sem_save"):
            if new_end <= new_start:
                st.error("종료일은 시작일보다 이후여야 합니다.")
            else:
                data.semester["start_date"] = new_start.isoformat()
                data.semester["end_date"]   = new_end.isoformat()
                from core.storage import save
                save(data)
                st.success("학기 기간이 저장되었습니다.")
                st.rerun()


run()
