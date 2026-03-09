import streamlit as st
import pandas as pd
from pathlib import Path
import plotly.express as px

from database.db_connect import get_job_roles, get_student_profile_paths
from utils.resume_parser import parse_resume_skills
from utils.navigation import render_sidebar_navigation

st.set_page_config(page_title="Resume Scanner", page_icon="📄", layout="wide")
render_sidebar_navigation()
st.title("📄 Resume Scanner")
st.caption("Extract skills from resume and evaluate fit against role requirements.")

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


def compute_resume_strength(extracted_skills, job_roles):
	if not job_roles:
		return 0.0, []

	extracted_set = {s.lower() for s in extracted_skills}
	scored = []
	for role in job_roles:
		required = {s.lower() for s in role.get("required_skills", [])}
		if not required:
			match_pct = 0.0
		else:
			match_pct = (len(extracted_set & required) / len(required)) * 100
		scored.append((role["role_name"], round(match_pct, 2), sorted(list(extracted_set & required))))

	scored.sort(key=lambda x: x[1], reverse=True)
	resume_score = round(sum(x[1] for x in scored[:3]) / max(len(scored[:3]), 1), 2)
	return resume_score, scored


st.subheader("Choose Resume")
paths = get_student_profile_paths(user_id)
stored_resume_path = paths.get("resume_path", "")

uploaded_resume = st.file_uploader("Upload Resume PDF", type=["pdf"])

resume_path = ""
if uploaded_resume is not None:
	target_dir = Path(f"uploads/user_{user_id}/resume")
	target_dir.mkdir(parents=True, exist_ok=True)
	local_path = str(target_dir / uploaded_resume.name).replace("\\", "/")
	st.session_state["temp_resume_path"] = local_path
	with open(local_path, "wb") as f:
		f.write(uploaded_resume.getbuffer())
	resume_path = local_path
elif stored_resume_path and Path(stored_resume_path).exists():
	resume_path = stored_resume_path

if st.button("Scan Resume", type="primary"):
	if not resume_path:
		st.error("No resume found. Upload one or save in Profile Entry.")
	else:
		try:
			extracted_skills = parse_resume_skills(resume_path)
			job_roles = get_job_roles()
			strength_score, matching = compute_resume_strength(extracted_skills, job_roles)

			col1, col2 = st.columns(2)
			with col1:
				st.markdown('<div class="result-card">', unsafe_allow_html=True)
				st.metric("Resume Strength Score", f"{strength_score}/100")
				st.markdown("</div>", unsafe_allow_html=True)
			with col2:
				st.markdown('<div class="result-card">', unsafe_allow_html=True)
				st.metric("Extracted Skills", len(extracted_skills))
				st.markdown("</div>", unsafe_allow_html=True)

			st.subheader("Extracted Skills")
			if extracted_skills:
				st.write(", ".join(extracted_skills))
			else:
				st.info("No known skills found in resume text.")

			st.subheader("Role Match")
			if matching:
				rows = [
					{
						"Role": role_name,
						"Skill Match %": score,
						"Matched Skills": ", ".join(matched_skills),
					}
					for role_name, score, matched_skills in matching
				]
				match_df = pd.DataFrame(rows)
				st.dataframe(match_df, use_container_width=True)

				match_fig = px.bar(
					match_df.head(8),
					x="Role",
					y="Skill Match %",
					color="Skill Match %",
					color_continuous_scale="Blues",
					title="Top Role Match Scores",
				)
				match_fig.update_layout(template="plotly_dark", xaxis_tickangle=-20)
				st.plotly_chart(match_fig, use_container_width=True)
		except Exception as exc:
			st.error(f"Resume scanning failed: {exc}")
