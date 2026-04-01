import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from database.db_connect import get_department_analytics, get_department_prediction_trend, get_faculty_student_rows
from utils.navigation import render_sidebar_navigation


@st.cache_data(ttl=60, show_spinner=False)
def _cached_department_snapshot(department: str, risk_level: str):
	risk = risk_level if risk_level in {"Low", "Medium", "High"} else None
	student_rows = get_faculty_student_rows(department=department, risk_level=risk)
	analytics = get_department_analytics(department=department)
	trend_rows = get_department_prediction_trend(department=department, months=6)
	return student_rows, analytics, trend_rows

st.set_page_config(page_title="Faculty Dashboard", page_icon="🏫", layout="wide")
render_sidebar_navigation()
st.title("🏫 Faculty Dashboard")
st.caption("Department-level risk analytics and student-level prediction monitoring.")


def _prepare_student_df(student_rows: list[dict]) -> pd.DataFrame:
	if not student_rows:
		return pd.DataFrame()

	df = pd.DataFrame(student_rows).rename(
		columns={
			"student_id": "Student ID",
			"name": "Name",
			"roll_number": "Roll Number",
			"email": "Email",
			"year": "Year",
			"attendance_pct": "Attendance %",
			"backlogs_count": "Backlogs",
			"academic_score": "Academic Score",
			"placement_readiness": "Readiness",
			"predicted_at": "Predicted At",
		}
	)

	numeric_cols = ["Year", "Attendance %", "Backlogs", "Academic Score"]
	for col in numeric_cols:
		df[col] = pd.to_numeric(df[col], errors="coerce")

	df["Year"] = df["Year"].fillna(0).astype(int)
	df["Backlogs"] = df["Backlogs"].fillna(0).astype(int)
	df["Attendance %"] = df["Attendance %"].fillna(0.0)
	df["Academic Score"] = df["Academic Score"].fillna(0.0)
	df["Readiness"] = df["Readiness"].fillna("Not Predicted")
	df["Predicted At"] = pd.to_datetime(df["Predicted At"], errors="coerce")

	return df

st.markdown(
	"""
	<style>
	.metric-card {
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

if not st.session_state.get("logged_in") or st.session_state.get("role") != "faculty":
	st.warning("Please login as faculty from Faculty Login page.")
	st.stop()

department = st.session_state.get("department", "")
st.caption(f"Department: {department}")

if not department:
	st.error("Faculty account has no department mapped. Please update faculty profile and login again.")
	st.stop()

risk_filter = st.selectbox("Filter by Risk Level", ["All", "Low", "Medium", "High", "Not Predicted"], index=0)
refresh_col, _ = st.columns([1, 5])
with refresh_col:
	if st.button("Refresh Data"):
		_cached_department_snapshot.clear()

student_rows, analytics, trend_rows = _cached_department_snapshot(department, risk_filter)
df = _prepare_student_df(student_rows)

if risk_filter == "Not Predicted" and not df.empty:
	df = df[df["Readiness"] == "Not Predicted"]

predicted_count = 0 if df.empty else int((df["Readiness"] != "Not Predicted").sum())
avg_score_display = float(df["Academic Score"].mean()) if not df.empty else analytics["avg_academic_score"]
low_count = int(analytics["readiness_counts"].get("Low", 0))
medium_count = int(analytics["readiness_counts"].get("Medium", 0))
high_count = int(analytics["readiness_counts"].get("High", 0))
at_risk_count = low_count + medium_count

col1, col2, col3 = st.columns(3)
with col1:
	st.markdown('<div class="metric-card">', unsafe_allow_html=True)
	st.metric("Students in View", 0 if df.empty else len(df))
	st.markdown("</div>", unsafe_allow_html=True)
with col2:
	st.markdown('<div class="metric-card">', unsafe_allow_html=True)
	st.metric("Average Academic Score", f"{avg_score_display:.2f}")
	st.markdown("</div>", unsafe_allow_html=True)
with col3:
	st.markdown('<div class="metric-card">', unsafe_allow_html=True)
	st.metric("Students with Predictions", predicted_count)
	st.markdown("</div>", unsafe_allow_html=True)

col4, col5 = st.columns(2)
with col4:
	st.markdown('<div class="metric-card">', unsafe_allow_html=True)
	st.metric("At Risk Students", at_risk_count)
	st.markdown("</div>", unsafe_allow_html=True)
with col5:
	st.markdown('<div class="metric-card">', unsafe_allow_html=True)
	st.metric("High Readiness", high_count)
	st.markdown("</div>", unsafe_allow_html=True)

st.subheader("Readiness Distribution")
if df.empty:
	readiness_df = pd.DataFrame(
		[
			{"Readiness": "Low", "Count": analytics["readiness_counts"].get("Low", 0)},
			{"Readiness": "Medium", "Count": analytics["readiness_counts"].get("Medium", 0)},
			{"Readiness": "High", "Count": analytics["readiness_counts"].get("High", 0)},
			{"Readiness": "Not Predicted", "Count": 0},
		]
	)
else:
	readiness_df = (
		df["Readiness"]
		.value_counts(dropna=False)
		.reindex(["Low", "Medium", "High", "Not Predicted"], fill_value=0)
		.rename_axis("Readiness")
		.reset_index(name="Count")
	)

fig = px.bar(readiness_df, x="Readiness", y="Count", color="Readiness", title="Department Risk Levels")
fig.update_layout(template="plotly_dark")

dc1, dc2 = st.columns(2)
with dc1:
	st.plotly_chart(fig, width="stretch")
with dc2:
	donut = go.Figure(
		data=[
			go.Pie(
				labels=readiness_df["Readiness"],
				values=readiness_df["Count"],
				hole=0.65,
				marker=dict(colors=["#ff5c77", "#ffce56", "#00c48c", "#6b7280"]),
			)
		]
	)
	donut.update_layout(template="plotly_dark", title="Risk Mix")
	st.plotly_chart(donut, width="stretch")

st.subheader("Department Overview")
if df.empty:
	st.info("No student records found for this department and filter.")
else:
	o1, o2 = st.columns(2)
	with o1:
		year_count_df = (
			df.groupby("Year", dropna=False)["Student ID"]
			.count()
			.reset_index(name="Students")
			.sort_values("Year")
		)
		year_fig = px.bar(year_count_df, x="Year", y="Students", title="Students by Year")
		year_fig.update_layout(template="plotly_dark")
		st.plotly_chart(year_fig, width="stretch")
	with o2:
		year_readiness_df = (
			df.groupby(["Year", "Readiness"], dropna=False)
			.size()
			.reset_index(name="Count")
			.sort_values("Year")
		)
		stacked_fig = px.bar(
			year_readiness_df,
			x="Year",
			y="Count",
			color="Readiness",
			title="Readiness by Year",
		)
		stacked_fig.update_layout(template="plotly_dark", barmode="stack")
		st.plotly_chart(stacked_fig, width="stretch")

st.subheader("Prediction Trend (Last 6 Months)")
if not trend_rows:
	st.info("No prediction activity found for this department in the selected period.")
else:
	trend_df = pd.DataFrame(trend_rows)
	trend_fig = px.line(
		trend_df,
		x="month",
		y="predictions",
		markers=True,
		title="Monthly Prediction Count",
	)
	trend_fig.update_layout(template="plotly_dark", xaxis_title="Month", yaxis_title="Predictions")
	st.plotly_chart(trend_fig, width="stretch")

st.subheader("Students in Department")
if df.empty:
	st.info("No student records found for this department and filter.")
else:
	st.subheader("Risk Drivers Visuals")
	v1, v2 = st.columns(2)
	with v1:
		scatter_source = df[df["Academic Score"] > 0]
		if scatter_source.empty:
			st.info("Attendance vs score chart needs at least one student with prediction score.")
		else:
			scatter_fig = px.scatter(
				scatter_source,
				x="Attendance %",
				y="Academic Score",
				color="Readiness",
				size="Backlogs",
				hover_data=["Name", "Roll Number", "Year"],
				title="Attendance vs Academic Score",
			)
			scatter_fig.update_layout(template="plotly_dark")
			st.plotly_chart(scatter_fig, width="stretch")
	with v2:
		backlog_fig = px.histogram(
			df,
			x="Backlogs",
			color="Readiness",
			nbins=8,
			title="Backlog Distribution by Readiness",
		)
		backlog_fig.update_layout(template="plotly_dark")
		st.plotly_chart(backlog_fig, width="stretch")

	st.subheader("At-Risk Students")
	risk_priority_df = df.copy()
	risk_priority_df["Risk Rank"] = risk_priority_df["Readiness"].map({"Low": 1, "Medium": 2, "High": 3, "Not Predicted": 2}).fillna(2)
	risk_priority_df = risk_priority_df.sort_values(["Risk Rank", "Academic Score", "Backlogs", "Attendance %"], ascending=[True, True, False, True])
	risk_view = risk_priority_df[["Name", "Roll Number", "Year", "Attendance %", "Backlogs", "Academic Score", "Readiness", "Predicted At"]].head(10)
	st.dataframe(risk_view, width="stretch", hide_index=True)

	st.dataframe(df.sort_values(["Year", "Name"]), width="stretch")
