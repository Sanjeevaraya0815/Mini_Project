import streamlit as st
import pandas as pd
import plotly.express as px

from database.db_connect import get_job_roles, get_profile_bundle
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


def recommend_roles(profile_bundle, role_catalog):
	profile = profile_bundle.get("profile")
	student_skills = {skill.lower() for skill in profile_bundle.get("skills", [])}

	internships = int(profile[5] if profile else 0)
	certifications = int(profile[6] if profile else 0)
	target_domain = str(profile[8] if profile else "").lower()

	scored_roles = []
	for role in role_catalog:
		required = {skill.lower() for skill in role.get("required_skills", [])}

		skill_match = (len(student_skills & required) / len(required)) if required else 0.0
		internship_match = 1.0 if internships >= role.get("min_internships", 0) else internships / max(role.get("min_internships", 1), 1)
		cert_match = 1.0 if certifications >= role.get("min_certifications", 0) else certifications / max(role.get("min_certifications", 1), 1)
		domain_match = 1.0 if target_domain and target_domain == str(role.get("target_domain", "")).lower() else 0.0

		final_score = (
			skill_match * 0.55
			+ internship_match * 0.2
			+ cert_match * 0.15
			+ domain_match * 0.1
		) * 100

		scored_roles.append(
			{
				"Role": role.get("role_name"),
				"Recommendation Score": round(final_score, 2),
				"Skill Match %": round(skill_match * 100, 2),
				"Internship Match": round(internship_match * 100, 2),
				"Certification Match": round(cert_match * 100, 2),
				"Domain Match": "Yes" if domain_match == 1.0 else "No",
			}
		)

	scored_roles.sort(key=lambda x: x["Recommendation Score"], reverse=True)
	return scored_roles


if st.button("Generate Recommendations", type="primary"):
	profile_bundle = get_profile_bundle(user_id)
	if not profile_bundle.get("profile"):
		st.error("Please complete Profile Entry before requesting recommendations.")
	else:
		role_catalog = get_job_roles()
		recommendations = recommend_roles(profile_bundle, role_catalog)
		top3 = recommendations[:3]
		all_df = pd.DataFrame(recommendations)

		st.subheader("Top Matching Job Roles")
		st.dataframe(pd.DataFrame(top3), use_container_width=True)

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
			st.plotly_chart(fig, use_container_width=True)

		st.subheader("All Role Scores")
		st.dataframe(all_df, use_container_width=True)
