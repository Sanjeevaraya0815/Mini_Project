import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database.db_connect import get_profile_bundle
from model.predict import get_latest_or_predict, predict_for_user
from utils.navigation import render_sidebar_navigation


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
        st.success("Prediction updated successfully.")
    except Exception as exc:
        st.error(f"Prediction failed: {exc}")
        st.stop()

try:
    result = get_latest_or_predict(user_id)
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
    st.plotly_chart(gauge_fig, use_container_width=True)
with g2:
    st.plotly_chart(readiness_fig, use_container_width=True)

profile_bundle = get_profile_bundle(user_id)
semester_scores = profile_bundle.get("semester_scores", [])
profile = profile_bundle.get("profile")

if semester_scores:
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
        st.plotly_chart(trend_fig, use_container_width=True)
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
        st.plotly_chart(band_fig, use_container_width=True)

if profile:
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
        st.plotly_chart(comp_fig, use_container_width=True)
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
        st.plotly_chart(donut_fig, use_container_width=True)
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
        st.plotly_chart(radar_fig, use_container_width=True)

helping = feature_importance.get("helping", {})
hurting = feature_importance.get("hurting", {})

if helping or hurting:
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
            st.plotly_chart(fig_help, use_container_width=True)
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
            st.plotly_chart(fig_hurt, use_container_width=True)
else:
    st.info("No feature importance data available yet.")
