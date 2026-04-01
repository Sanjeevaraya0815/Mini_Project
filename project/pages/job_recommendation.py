import streamlit as st
import pandas as pd
import plotly.express as px

from database.db_connect import get_job_roles, get_profile_bundle
from utils.recommendation_engine import recommend_roles
from utils.navigation import render_sidebar_navigation

st.set_page_config(page_title="Job Recommendation", page_icon="💼", layout="wide")
render_sidebar_navigation()
st.title("💼 Job Recommendation")
st.caption("Get role recommendations based on skills, internships, certifications, and career target.")

st.markdown(
	"""
	<style>
	.result-card {
		background: linear-gradient(145deg, #161b22, #0f141a);
		border: 1px solid #30363d;
		border-radius: 14px;
		padding: 14px;
		margin-bottom: 10px;
	}
	</style>
	""",
	unsafe_allow_html=True,
)

if not st.session_state.get("logged_in") or st.session_state.get("role") != "student":
	st.warning("Please login as student from Student Login page.")
	st.stop()

user_id = st.session_state["user_id"]


@st.cache_data(ttl=120, show_spinner=False)
def _cached_profile_bundle(user_id: int):
	return get_profile_bundle(user_id)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_job_roles():
	return get_job_roles()


if st.button("Generate Recommendations", type="primary"):
	profile_bundle = _cached_profile_bundle(user_id)
	if not profile_bundle.get("profile"):
		st.error("Please complete Profile Entry before requesting recommendations.")
	else:
		role_catalog = _cached_job_roles()
		recommendations = recommend_roles(profile_bundle, role_catalog)
		top3 = recommendations[:3]
		all_df = pd.DataFrame(recommendations)

		st.subheader("Top Matching Job Roles")
		st.dataframe(pd.DataFrame(top3), width="stretch")

		if top3:
			st.markdown('<div class="result-card">', unsafe_allow_html=True)
			st.metric("Best Match", top3[0]["Role"], f"Score: {top3[0]['Recommendation Score']}")
			st.markdown("</div>", unsafe_allow_html=True)

			fig = px.bar(
				all_df.head(8),
				x="Role",
				y="Recommendation Score",
				color="Recommendation Score",
				color_continuous_scale="Tealgrn",
				title="Role Recommendation Ranking",
			)
			fig.update_layout(template="plotly_dark", xaxis_tickangle=-20)
			st.plotly_chart(fig, width="stretch")

		st.subheader("All Role Scores")
		st.dataframe(all_df, width="stretch")
