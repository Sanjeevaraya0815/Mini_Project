import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database.db_connect import get_job_roles, get_profile_bundle, save_student_goals
from model.predict import get_latest_or_predict, predict_for_user
from utils.recommendation_engine import profile_health_summary, recommend_roles
from utils.student_insights import (
    achievement_badges,
    build_alerts,
    build_goal_progress,
    compute_profile_score,
    compute_resume_insight,
    profile_completeness,
    rule_based_tips,
)
from utils.reporting import generate_student_report_pdf
from utils.navigation import render_sidebar_navigation


@st.cache_data(ttl=45, show_spinner=False)
def _cached_prediction(user_id: int):
    return get_latest_or_predict(user_id)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_profile_bundle(user_id: int):
    return get_profile_bundle(user_id)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_job_roles():
    return get_job_roles()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_resume_insight(resume_path: str, modified_at: float):
    _ = modified_at
    return compute_resume_insight(resume_path)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_student_report(
    student_name: str,
    user_id: int,
    department: str,
    academic_score: float,
    readiness: str,
    profile_score: float,
    resume_score: float,
    feature_importance: dict,
    recommendations: list,
    profile_bundle: dict,
    profile_summary: dict,
    goal_progress: list,
    alerts: list,
):
    return generate_student_report_pdf(
        student_name=student_name,
        user_id=user_id,
        department=department,
        academic_score=academic_score,
        readiness=readiness,
        profile_score=profile_score,
        resume_score=resume_score,
        feature_importance=feature_importance,
        recommendations=recommendations,
        profile_bundle=profile_bundle,
        profile_summary=profile_summary,
        goal_progress=goal_progress,
        alerts=alerts,
    )


st.set_page_config(page_title="Student Dashboard", page_icon="📊", layout="wide")
render_sidebar_navigation()
st.title("📊 Student Dashboard")

st.markdown(
    """
    <style>
    .metric-card {
        background: linear-gradient(145deg, #161b22, #0f141a);
        border: 1px solid #30363d;
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if not st.session_state.get("logged_in") or st.session_state.get("role") != "student":
    st.warning("Please login as student from Student Login page.")
    st.stop()

user_id = st.session_state["user_id"]

btn_col1, btn_col2 = st.columns([1, 3])
with btn_col1:
    run_prediction = st.button("Run / Refresh Prediction", type="primary")

if run_prediction:
    try:
        predict_for_user(user_id=user_id, persist=True)
        _cached_prediction.clear()
        _cached_profile_bundle.clear()
        st.success("Prediction updated successfully.")
    except Exception as exc:
        st.error(f"Prediction failed: {exc}")
        st.stop()

try:
    result = _cached_prediction(user_id)
except Exception as exc:
    st.error(f"Could not load prediction: {exc}")
    st.info("Make sure your profile is filled and model is trained using model/train_model.py")
    st.stop()

academic_score = float(result.get("academic_score", 0.0))
readiness = result.get("placement_readiness", "Low")
feature_importance = result.get("feature_importance", {})

if isinstance(feature_importance, str):
    try:
        feature_importance = json.loads(feature_importance)
    except json.JSONDecodeError:
        feature_importance = {}

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Academic Performance Score", f"{academic_score:.2f}/100")
    st.markdown("</div>", unsafe_allow_html=True)
with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Placement Readiness", readiness)
    st.markdown("</div>", unsafe_allow_html=True)
with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Student", st.session_state.get("user_name", "N/A"))
    st.markdown("</div>", unsafe_allow_html=True)

readiness_value = {"Low": 30, "Medium": 65, "High": 90}.get(readiness, 30)

gauge_fig = go.Figure(
    go.Indicator(
        mode="gauge+number",
        value=academic_score,
        title={"text": "Academic Score Gauge"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#4f8cff"},
            "steps": [
                {"range": [0, 40], "color": "#5d1f28"},
                {"range": [40, 70], "color": "#6b5f1a"},
                {"range": [70, 100], "color": "#1f5d3f"},
            ],
        },
    )
)
gauge_fig.update_layout(template="plotly_dark", margin=dict(l=15, r=15, t=50, b=15))

readiness_fig = go.Figure(
    go.Indicator(
        mode="gauge+number",
        value=readiness_value,
        title={"text": "Placement Readiness Gauge"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#00c48c"},
            "steps": [
                {"range": [0, 40], "color": "#5d1f28"},
                {"range": [40, 70], "color": "#6b5f1a"},
                {"range": [70, 100], "color": "#1f5d3f"},
            ],
        },
    )
)
readiness_fig.update_layout(template="plotly_dark", margin=dict(l=15, r=15, t=50, b=15))

g1, g2 = st.columns(2)
with g1:
    st.plotly_chart(gauge_fig, width="stretch")
with g2:
    st.plotly_chart(readiness_fig, width="stretch")

profile_bundle = _cached_profile_bundle(user_id)
semester_scores = profile_bundle.get("semester_scores", [])
profile = profile_bundle.get("profile")
goal_data = profile_bundle.get("goals")
profile_summary = profile_health_summary(profile_bundle)
role_catalog = _cached_job_roles()
recommendations = recommend_roles(profile_bundle, role_catalog)[:5] if profile else []
profile_score_data = compute_profile_score(profile_bundle)
profile_score = profile_score_data["score"]
resume_path = str(profile[13] or "") if profile else ""
resume_modified_at = Path(resume_path).stat().st_mtime if resume_path and Path(resume_path).exists() else 0.0
resume_insight = _cached_resume_insight(resume_path, resume_modified_at) if resume_path else {"score": 0.0, "extracted_skills": [], "top_roles": []}
resume_score = resume_insight["score"]
goal_progress = build_goal_progress(profile_bundle, goal_data)
alerts = build_alerts(profile_bundle, goal_data, profile_score, resume_score)
completeness = profile_completeness(profile_bundle)
tips = rule_based_tips(profile_bundle, profile_score, resume_score)
badges = achievement_badges(profile_bundle, profile_score, resume_score, readiness)

show_advanced = st.toggle("Enable advanced visuals", value=False)

st.subheader("Profile Health")
health_cols = st.columns(4)
with health_cols[0]:
    st.metric("Skills Tagged", len(profile_bundle.get("skills", [])))
with health_cols[1]:
    st.metric("Coding Profiles", f"{profile_summary['coding_profile_count']}/4")
with health_cols[2]:
    st.metric("Languages Known", profile_summary["languages_known_count"])
with health_cols[3]:
    st.metric("Semester Scores", len(semester_scores))

if profile_summary["missing_coding_profiles"]:
    st.warning("Missing coding profile links: " + ", ".join(profile_summary["missing_coding_profiles"]))

st.subheader("Profile Completeness")
st.metric("Completion", f"{completeness['percent']:.1f}%", f"{completeness['completed']}/{completeness['total']} checks")
st.progress(min(max(completeness["percent"] / 100.0, 0.0), 1.0))
if completeness["missing"]:
    st.caption("Missing items: " + ", ".join(completeness["missing"][:6]))
else:
    st.success("All core profile items are complete.")

st.subheader("Improvement Tips")
for idx, tip in enumerate(tips, start=1):
    st.write(f"{idx}. {tip}")

st.subheader("Achievement Badges")
if badges:
    badge_text = " | ".join(badges)
    st.success(badge_text)
else:
    st.info("Complete more profile and performance milestones to unlock badges.")

score_cols = st.columns(2)
with score_cols[0]:
    st.subheader("Profile Score")
    st.metric("Overall Profile Score", f"{profile_score:.1f}/100")
    st.progress(min(max(profile_score / 100.0, 0.0), 1.0))
with score_cols[1]:
    st.subheader("Resume Score")
    st.metric("Resume Match Score", f"{resume_score:.1f}/100")
    st.progress(min(max(resume_score / 100.0, 0.0), 1.0))

if resume_insight["extracted_skills"]:
    st.caption("Resume skills: " + ", ".join(resume_insight["extracted_skills"][:12]))

st.subheader("Goal Tracking")
goal_defaults = {
    "target_gpa": float(goal_data[0]) if goal_data and goal_data[0] is not None else (round(profile_score_data["semester_average"], 2) if profile_score_data["semester_average"] else 7.5),
    "target_attendance_pct": float(goal_data[1]) if goal_data and goal_data[1] is not None else float(profile[0] or 75) if profile else 75.0,
    "target_coding_hours_per_week": float(goal_data[2]) if goal_data and goal_data[2] is not None else float(profile[3] or 8) if profile else 8.0,
    "target_internships_count": int(goal_data[3]) if goal_data and goal_data[3] is not None else int(profile[5] or 1) if profile else 1,
    "target_certifications_count": int(goal_data[4]) if goal_data and goal_data[4] is not None else int(profile[6] or 1) if profile else 1,
    "target_projects_completed": int(goal_data[5]) if goal_data and goal_data[5] is not None else int(profile[7] or 3) if profile else 3,
    "reminder_notes": goal_data[6] if goal_data and goal_data[6] else "",
}

with st.form("goal_form"):
    goal_col1, goal_col2, goal_col3 = st.columns(3)
    with goal_col1:
        target_gpa = st.number_input("Target GPA / CGPA", 0.0, 10.0, float(goal_defaults["target_gpa"]), 0.1)
        target_attendance = st.number_input("Target Attendance %", 0.0, 100.0, float(goal_defaults["target_attendance_pct"]), 0.5)
    with goal_col2:
        target_coding_hours = st.number_input("Target Coding Hours / Week", 0.0, 100.0, float(goal_defaults["target_coding_hours_per_week"]), 0.5)
        target_internships = st.number_input("Target Internships", 0, 20, int(goal_defaults["target_internships_count"]))
    with goal_col3:
        target_certifications = st.number_input("Target Certifications", 0, 50, int(goal_defaults["target_certifications_count"]))
        target_projects = st.number_input("Target Projects", 0, 100, int(goal_defaults["target_projects_completed"]))
    reminder_notes = st.text_input("Reminder Notes", value=str(goal_defaults["reminder_notes"]))
    save_goals = st.form_submit_button("Save Goals")

if save_goals:
    save_student_goals(
        user_id,
        {
            "target_gpa": float(target_gpa),
            "target_attendance_pct": float(target_attendance),
            "target_coding_hours_per_week": float(target_coding_hours),
            "target_internships_count": int(target_internships),
            "target_certifications_count": int(target_certifications),
            "target_projects_completed": int(target_projects),
            "reminder_notes": reminder_notes,
        },
    )
    _cached_profile_bundle.clear()
    st.success("Goals saved successfully.")
    st.rerun()

if goal_progress:
    progress_cols = st.columns(2)
    left_rows = goal_progress[: (len(goal_progress) + 1) // 2]
    right_rows = goal_progress[(len(goal_progress) + 1) // 2 :]
    with progress_cols[0]:
        for row in left_rows:
            st.caption(f"{row['label']}: {row['current']} / {row['target']}")
            st.progress(min(max(row["progress"] / 100.0, 0.0), 1.0))
    with progress_cols[1]:
        for row in right_rows:
            st.caption(f"{row['label']}: {row['current']} / {row['target']}")
            st.progress(min(max(row["progress"] / 100.0, 0.0), 1.0))

st.subheader("Alerts and Reminders")
if alerts:
    for alert in alerts[:8]:
        if alert["level"] == "warning":
            st.warning(alert["message"])
        else:
            st.info(alert["message"])
else:
    st.success("No active alerts right now.")


def _explain_prediction(importance: dict, current_readiness: str) -> str:
    helping = importance.get("helping", {}) if isinstance(importance, dict) else {}
    hurting = importance.get("hurting", {}) if isinstance(importance, dict) else {}

    helping_text = ", ".join(f"{key} ({value:.2f})" for key, value in list(helping.items())[:3])
    hurting_text = ", ".join(f"{key} ({value:.2f})" for key, value in list(hurting.items())[:3])

    if current_readiness == "High":
        base = "The model classifies the profile as strong for placement readiness."
    elif current_readiness == "Medium":
        base = "The model sees a mixed profile with room to improve readiness."
    else:
        base = "The model sees a risk profile that needs focused improvement."

    details = []
    if helping_text:
        details.append(f"Strongest positive factors: {helping_text}.")
    if hurting_text:
        details.append(f"Main pressure points: {hurting_text}.")
    return " ".join([base, *details])


st.subheader("Explainable Prediction")
st.info(_explain_prediction(feature_importance, readiness))

if semester_scores and show_advanced:
    st.subheader("Academic Trend")
    sem_df = pd.DataFrame(
        {
            "Semester": [f"S{i+1}" for i in range(len(semester_scores))],
            "Score": semester_scores,
        }
    )
    t1, t2 = st.columns(2)
    with t1:
        trend_fig = px.line(
            sem_df,
            x="Semester",
            y="Score",
            markers=True,
            title="Semester-wise Score Progress",
        )
        trend_fig.update_traces(line_color="#4f8cff", marker_color="#00c48c", line_width=3)
        trend_fig.update_layout(template="plotly_dark", yaxis_range=[0, 10])
        st.plotly_chart(trend_fig, width="stretch")
    with t2:
        sem_df["Band"] = pd.cut(
            sem_df["Score"],
            bins=[-0.01, 5.0, 7.0, 10.0],
            labels=["Needs Improvement", "Moderate", "Strong"],
        )
        band_df = sem_df.groupby("Band", as_index=False).size().rename(columns={"size": "Count"})
        band_fig = px.pie(
            band_df,
            names="Band",
            values="Count",
            hole=0.6,
            title="Score Band Distribution",
        )
        band_fig.update_layout(template="plotly_dark")
        st.plotly_chart(band_fig, width="stretch")

if profile and show_advanced:
    st.subheader("Readiness Components")
    comp_df = pd.DataFrame(
        [
            {"Component": "Attendance", "Value": float(profile[0] or 0)},
            {"Component": "Coding Hours", "Value": min(float(profile[3] or 0) * 3.33, 100)},
            {"Component": "Internships", "Value": min(float(profile[5] or 0) * 20, 100)},
            {"Component": "Certifications", "Value": min(float(profile[6] or 0) * 12.5, 100)},
            {"Component": "Communication", "Value": min(float(profile[10] or 0) * 10, 100)},
            {"Component": "Motivation", "Value": min(float(profile[12] or 0) * 10, 100)},
        ]
    )
    c3, c4, c5 = st.columns(3)
    with c3:
        comp_fig = px.bar(
            comp_df,
            x="Component",
            y="Value",
            title="Normalized Components (0-100)",
            color="Value",
            color_continuous_scale="Tealgrn",
        )
        comp_fig.update_layout(template="plotly_dark", yaxis_range=[0, 100])
        st.plotly_chart(comp_fig, width="stretch")
    with c4:
        donut_df = pd.DataFrame(
            {
                "Readiness": ["Low", "Medium", "High"],
                "Value": [
                    1 if readiness == "Low" else 0,
                    1 if readiness == "Medium" else 0,
                    1 if readiness == "High" else 0,
                ],
            }
        )
        donut_fig = px.pie(
            donut_df,
            names="Readiness",
            values="Value",
            hole=0.7,
            title="Current Readiness Band",
            color="Readiness",
            color_discrete_map={"Low": "#ff5c77", "Medium": "#ffce56", "High": "#00c48c"},
        )
        donut_fig.update_layout(template="plotly_dark")
        st.plotly_chart(donut_fig, width="stretch")
    with c5:
        radar_fig = go.Figure()
        radar_fig.add_trace(
            go.Scatterpolar(
                r=comp_df["Value"].tolist() + [comp_df["Value"].tolist()[0]],
                theta=comp_df["Component"].tolist() + [comp_df["Component"].tolist()[0]],
                fill="toself",
                name="Readiness Shape",
                line=dict(color="#4f8cff"),
            )
        )
        radar_fig.update_layout(
            template="plotly_dark",
            title="Component Radar",
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            margin=dict(l=10, r=10, t=45, b=10),
        )
        st.plotly_chart(radar_fig, width="stretch")

helping = feature_importance.get("helping", {})
hurting = feature_importance.get("hurting", {})

if (helping or hurting) and show_advanced:
    st.subheader("Feature Importance")

    helping_df = pd.DataFrame(helping.items(), columns=["Feature", "Impact"])
    hurting_df = pd.DataFrame(hurting.items(), columns=["Feature", "Impact"])

    c1, c2 = st.columns(2)
    with c1:
        if not helping_df.empty:
            fig_help = px.bar(
                helping_df,
                x="Impact",
                y="Feature",
                orientation="h",
                title="Helping Factors",
                color="Impact",
                color_continuous_scale="Blues",
            )
            fig_help.update_layout(template="plotly_dark")
            st.plotly_chart(fig_help, width="stretch")
    with c2:
        if not hurting_df.empty:
            fig_hurt = px.bar(
                hurting_df,
                x="Impact",
                y="Feature",
                orientation="h",
                title="Hurting Factors",
                color="Impact",
                color_continuous_scale="Reds",
            )
            fig_hurt.update_layout(template="plotly_dark")
            st.plotly_chart(fig_hurt, width="stretch")
else:
    if show_advanced:
        st.info("No feature importance data available yet.")

st.subheader("Personalized Recommendations")
if recommendations:
    rec_df = pd.DataFrame(recommendations)
    st.dataframe(rec_df, width="stretch", hide_index=True)
    rec_fig = px.bar(
        rec_df.head(6),
        x="Role",
        y="Recommendation Score",
        color="Recommendation Score",
        color_continuous_scale="Tealgrn",
        title="Top Matching Roles",
    )
    rec_fig.update_layout(template="plotly_dark", xaxis_tickangle=-20)
    st.plotly_chart(rec_fig, width="stretch")
else:
    st.info("Complete your profile to unlock role recommendations.")

st.subheader("PDF Report")
if st.button("Generate PDF Report"):
    st.session_state["student_report_bytes"] = _cached_student_report(
        student_name=st.session_state.get("user_name", "Student"),
        user_id=user_id,
        department=st.session_state.get("department", ""),
        academic_score=academic_score,
        readiness=readiness,
        profile_score=profile_score,
        resume_score=resume_score,
        feature_importance=feature_importance,
        recommendations=recommendations,
        profile_bundle=profile_bundle,
        profile_summary=profile_summary,
        goal_progress=goal_progress,
        alerts=alerts,
    )

report_bytes = st.session_state.get("student_report_bytes")
if report_bytes:
    st.download_button(
        "Download Student Report PDF",
        data=report_bytes,
        file_name=f"student_report_{user_id}.pdf",
        mime="application/pdf",
    )
else:
    st.caption("Generate the report once, then download it.")
