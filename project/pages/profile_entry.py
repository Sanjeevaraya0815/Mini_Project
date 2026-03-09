import json
import os
from pathlib import Path

import streamlit as st

from database.db_connect import replace_semester_scores, replace_skills, upsert_student_profile
from utils.navigation import render_sidebar_navigation


st.set_page_config(page_title="Profile Entry", page_icon="📝", layout="wide")
render_sidebar_navigation()
st.title("📝 Student Profile & Data Entry")
st.caption("Fill all dimensions carefully — these values drive your prediction and recommendations.")

st.markdown(
    """
    <style>
    .section-card {
        background: linear-gradient(145deg, #161b22, #0f141a);
        border: 1px solid #30363d;
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if not st.session_state.get("logged_in") or st.session_state.get("role") != "student":
    st.warning("Please login as student from Student Login page.")
    st.stop()

user_id = st.session_state["user_id"]


def save_uploaded_file(uploaded_file, category: str) -> str:
    if uploaded_file is None:
        return ""

    base_dir = Path("uploads") / f"user_{user_id}" / category
    base_dir.mkdir(parents=True, exist_ok=True)
    file_path = base_dir / uploaded_file.name

    with open(file_path, "wb") as file_obj:
        file_obj.write(uploaded_file.getbuffer())

    return str(file_path).replace("\\", "/")


available_skills = [
    "Python",
    "Java",
    "C++",
    "SQL",
    "Machine Learning",
    "Deep Learning",
    "Data Structures",
    "Algorithms",
    "Web Development",
    "Cloud",
    "Docker",
    "Git",
]

career_domains = [
    "Software Development",
    "Data Science",
    "Data Analytics",
    "Cloud Computing",
    "Cyber Security",
    "Quality Assurance",
    "Product Management",
]

with st.form("profile_form"):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        attendance_pct = st.number_input("Attendance (%)", 0.0, 100.0, 75.0, 0.5)
        backlogs_count = st.number_input("Backlogs Count", 0, 50, 0)
        dsa_language = st.selectbox("DSA Language", ["Python", "Java", "C++", "C", "JavaScript"])
        coding_hours = st.number_input("Coding Hours per Week", 0.0, 100.0, 8.0, 0.5)

    with col2:
        internships_count = st.number_input("Internships Count", 0, 20, 0)
        certifications_count = st.number_input("Certifications Count", 0, 50, 0)
        projects_completed = st.number_input("Projects Completed", 0, 100, 1)
        target_domain = st.selectbox("Target Career Domain", career_domains)

    with col3:
        communication_rating = st.slider("Communication Skill Rating", 1, 10, 6)
        stress_level = st.slider("Stress Level", 1, 10, 5)
        motivation_level = st.slider("Motivation Level", 1, 10, 7)
        languages_known = st.multiselect(
            "Languages Known",
            ["English", "Hindi", "Tamil", "Telugu", "Kannada", "Malayalam", "Other"],
            default=["English"],
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Semester Scores")
    sem_cols = st.columns(4)
    semester_scores = []
    for i in range(8):
        with sem_cols[i % 4]:
            score = st.number_input(f"S{i + 1} Score", 0.0, 10.0, 7.0, 0.1)
            semester_scores.append(score)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Skills and Coding Profiles")
    selected_skills = st.multiselect("Technical Skills", available_skills)
    profile_cols = st.columns(4)
    with profile_cols[0]:
        leetcode = st.text_input("LeetCode Profile URL")
    with profile_cols[1]:
        hackerrank = st.text_input("HackerRank Profile URL")
    with profile_cols[2]:
        codechef = st.text_input("CodeChef Profile URL")
    with profile_cols[3]:
        github = st.text_input("GitHub Profile URL")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Documents")
    resume_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])
    cert_file = st.file_uploader("Upload Certificate (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
    st.markdown("</div>", unsafe_allow_html=True)

    submit_btn = st.form_submit_button("Save Profile")

if submit_btn:
    try:
        resume_path = save_uploaded_file(resume_file, "resume") if resume_file else ""
        cert_path = save_uploaded_file(cert_file, "certificate") if cert_file else ""

        profile_payload = {
            "attendance_pct": float(attendance_pct),
            "backlogs_count": int(backlogs_count),
            "dsa_language": dsa_language,
            "coding_hours_per_week": float(coding_hours),
            "coding_profiles": json.dumps(
                {
                    "leetcode": leetcode,
                    "hackerrank": hackerrank,
                    "codechef": codechef,
                    "github": github,
                }
            ),
            "internships_count": int(internships_count),
            "certifications_count": int(certifications_count),
            "projects_completed": int(projects_completed),
            "target_career_domain": target_domain,
            "languages_known": json.dumps(languages_known),
            "communication_rating": int(communication_rating),
            "stress_level": int(stress_level),
            "motivation_level": int(motivation_level),
            "resume_path": resume_path,
            "certificate_path": cert_path,
        }

        upsert_student_profile(user_id, profile_payload)
        replace_semester_scores(user_id, semester_scores)
        replace_skills(user_id, selected_skills)
        st.success("Profile saved successfully.")
    except Exception as exc:
        st.error(f"Failed to save profile: {exc}")
