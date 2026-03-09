import streamlit as st


def render_sidebar_navigation() -> None:
    st.sidebar.markdown("### Navigation")

    page_items = [
        ("pages/student_login.py", "student login", "🔐"),
        ("pages/faculty_login.py", "faculty login", "👩‍🏫"),
        ("pages/profile_entry.py", "profile entry", "📝"),
        ("pages/student_dashboard.py", "student dashboard", "📊"),
        ("pages/faculty_dashboard.py", "faculty dashboard", "🏫"),
        ("pages/resume_scanner.py", "resume scanner", "📄"),
        ("pages/certificate_scanner.py", "certificate scanner", "🧾"),
        ("pages/job_recommendation.py", "job recommendation", "💼"),
        ("app.py", "app", "🎓"),
    ]

    if hasattr(st.sidebar, "page_link"):
        for page_path, label, icon in page_items:
            st.sidebar.page_link(page_path, label=label, icon=icon, use_container_width=True)
    else:
        st.sidebar.info("Sidebar navigation links are not supported in this Streamlit version.")

    st.sidebar.divider()
    if st.session_state.get("logged_in"):
        user_name = st.session_state.get("user_name", "User")
        role = st.session_state.get("role", "")
        st.sidebar.caption(f"Logged in: {user_name} ({role})")
