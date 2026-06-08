"""app.py — 이그잼 플래너 Streamlit 진입점"""
import streamlit as st

st.set_page_config(
    page_title="이그잼 플래너",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation(
    [
        st.Page("pages/home.py",     title="홈",               icon="🏠"),
        st.Page("pages/courses.py",  title="수강 과목",          icon="📚"),
        st.Page("pages/events.py",   title="일정 관리",          icon="📅"),
        st.Page("pages/rules.py",    title="반복 규칙",          icon="🔄"),
        st.Page("pages/calendar.py", title="캘린더",             icon="📆"),
        st.Page("pages/io_page.py",  title="가져오기/내보내기",   icon="💾"),
    ]
)

pg.run()
