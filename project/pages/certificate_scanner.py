import streamlit as st
import re
from pathlib import Path
import pandas as pd
import plotly.express as px

from database.db_connect import get_certifications, get_student_profile_paths, save_certification_scan_results
from utils.ocr_utils import extract_certificate_text
from utils.navigation import render_sidebar_navigation

st.set_page_config(page_title="Certificate Scanner", page_icon="🧾", layout="wide")
render_sidebar_navigation()
st.title("🧾 Certificate Scanner")
st.caption("Scan uploaded certificates, validate text quality, and track verified records.")

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


def verify_certificate_text(text: str) -> bool:
	text_lower = text.lower()
	quality_keywords = ["certificate", "awarded", "completed", "course", "issued", "verify"]
	hits = sum(1 for kw in quality_keywords if kw in text_lower)
	return hits >= 2 and len(text.strip()) > 60


def extract_candidate_cert_names(text: str):
	lines = [line.strip() for line in text.splitlines() if line.strip()]
	shortlist = []
	for line in lines[:40]:
		if len(line) < 4 or len(line) > 80:
			continue
		if re.search(r"certificate|certified|completion|course", line, flags=re.IGNORECASE):
			shortlist.append(line)
	unique = []
	for item in shortlist:
		if item not in unique:
			unique.append(item)
	return unique[:5]


st.subheader("Upload Certificate")
uploaded = st.file_uploader("Upload PDF/Image", type=["pdf", "png", "jpg", "jpeg"])
stored_paths = get_student_profile_paths(user_id)
stored_cert = stored_paths.get("certificate_path", "")

cert_path = ""
if uploaded is not None:
	target_dir = Path(f"uploads/user_{user_id}/certificate")
	target_dir.mkdir(parents=True, exist_ok=True)
	cert_path = str(target_dir / uploaded.name).replace("\\", "/")
	with open(cert_path, "wb") as f:
		f.write(uploaded.getbuffer())
elif stored_cert:
	cert_path = stored_cert

if st.button("Scan Certificate", type="primary"):
	if not cert_path:
		st.error("No certificate file found. Upload one or save via Profile Entry.")
	else:
		text, supported = extract_certificate_text(cert_path)
		if not supported:
			st.error("Unsupported file type.")
		elif not text.strip():
			st.warning("Could not extract meaningful text from the file.")
		else:
			is_valid = verify_certificate_text(text)
			cert_names = extract_candidate_cert_names(text)
			if is_valid and not cert_names:
				cert_names = ["Verified Certificate"]

			saved_count = save_certification_scan_results(user_id, cert_names if is_valid else [])

			c1, c2 = st.columns(2)
			with c1:
				st.markdown('<div class="result-card">', unsafe_allow_html=True)
				st.metric("Validation Status", "Verified" if is_valid else "Unverified")
				st.markdown("</div>", unsafe_allow_html=True)
			with c2:
				st.markdown('<div class="result-card">', unsafe_allow_html=True)
				st.metric("Verified Certifications", saved_count)
				st.markdown("</div>", unsafe_allow_html=True)

			with st.expander("Extracted Text Preview"):
				st.text(text[:2000])

st.subheader("Saved Certifications")
cert_rows = get_certifications(user_id)
if cert_rows:
	cert_df = pd.DataFrame(cert_rows)
	st.dataframe(cert_df, use_container_width=True)
	if "verified" in cert_df.columns:
		summary_df = (
			cert_df.groupby("verified", as_index=False)
			.size()
			.rename(columns={"size": "Count", "verified": "Verified"})
		)
		summary_df["Verified"] = summary_df["Verified"].map({True: "Verified", False: "Unverified"})
		fig = px.pie(
			summary_df,
			names="Verified",
			values="Count",
			hole=0.65,
			color="Verified",
			color_discrete_map={"Verified": "#00c48c", "Unverified": "#ff5c77"},
			title="Certification Verification Mix",
		)
		fig.update_layout(template="plotly_dark")
		st.plotly_chart(fig, use_container_width=True)
else:
	st.info("No certification records yet.")
