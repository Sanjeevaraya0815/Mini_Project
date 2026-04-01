import streamlit as st
import plotly.express as px
import pandas as pd

from database.db_connect import test_connection
from utils.navigation import render_sidebar_navigation


@st.cache_data(ttl=30, show_spinner=False)
def _cached_db_status():
    return test_connection()

st.set_page_config(page_title="Student Performance Predictor", page_icon="🎓", layout="wide")
render_sidebar_navigation()

st.markdown(
    """
    <style>
    .hero {
        background: linear-gradient(135deg, #111827, #1f2937);
        border: 1px solid #30363d;
        border-radius: 16px;
        padding: 18px;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎓 Student Performance and Placement Readiness System")
st.markdown(
    '<div class="hero">Use the sidebar to navigate modules. Start with Student Login, fill Profile Entry, and view predictions in Student Dashboard.</div>',
    unsafe_allow_html=True,
)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "email" not in st.session_state:
    st.session_state.email = None
if "department" not in st.session_state:
    st.session_state.department = None

with st.expander("System Status", expanded=True):
    ok, msg = _cached_db_status()
    if ok:
        st.success(msg)
    else:
        st.error(msg)

c1, c2, c3 = st.columns(3)
c1.metric("Login Status", "Logged In" if st.session_state.logged_in else "Logged Out")
c2.metric("Role", st.session_state.role or "N/A")
c3.metric("User ID", str(st.session_state.user_id) if st.session_state.user_id else "N/A")

st.info(
    "Flow: Student Login → Profile Entry → Train model/train_model.py → Student Dashboard. "
    "Additional modules available: Resume Scanner, Certificate Scanner, Job Recommendation, Faculty Login, Faculty Dashboard."
)

st.subheader("📌 Workflow Snapshot")
wf_col1, wf_col2 = st.columns([2, 1])

with wf_col1:
    flow_df = pd.DataFrame(
        {
            "Stage": ["Student Login", "Profile Entry", "Model Trained", "Prediction Viewed"],
            "Progress": [100, 80, 65, 55],
        }
    )
    flow_fig = px.funnel(
        flow_df,
        x="Progress",
        y="Stage",
        title="System Usage Flow",
    )
    flow_fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=45, b=10))
    st.plotly_chart(flow_fig, use_container_width=True)

with wf_col2:
    st.markdown('<div class="hero">', unsafe_allow_html=True)
    st.markdown("### Next Best Steps")
    st.markdown("- Login with your role")
    st.markdown("- Complete profile details")
    st.markdown("- Refresh prediction dashboard")
    st.markdown("- Track readiness and risks")
    st.markdown("</div>", unsafe_allow_html=True)

st.subheader("🧩 Module Coverage")
module_df = pd.DataFrame(
    {
        "Module": [
            "Student Login",
            "Profile Entry",
            "Student Dashboard",
            "Resume Scanner",
            "Certificate Scanner",
            "Job Recommendation",
            "Faculty Login",
            "Faculty Dashboard",
        ],
        "Visual Depth": [4, 3, 5, 3, 3, 3, 2, 4],
    }
)
module_fig = px.bar(
    module_df,
    x="Module",
    y="Visual Depth",
    color="Visual Depth",
    color_continuous_scale="Blues",
    title="Current Visualization Intensity by Module",
)
module_fig.update_layout(template="plotly_dark", xaxis_tickangle=-30, margin=dict(l=10, r=10, t=45, b=10))
st.plotly_chart(module_fig, use_container_width=True)
