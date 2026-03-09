import streamlit as st

from database.db_connect import create_user, get_user_by_email
from utils.auth_utils import hash_password, verify_password
from utils.navigation import render_sidebar_navigation

st.set_page_config(page_title="Faculty Login", page_icon="👩‍🏫", layout="centered")
render_sidebar_navigation()
st.title("👩‍🏫 Faculty Login")
st.caption("Faculty users can register with department and access analytics dashboard.")

st.markdown(
	"""
	<style>
	.glass-card {
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


def initialize_session() -> None:
	defaults = {
		"logged_in": False,
		"user_id": None,
		"user_name": None,
		"email": None,
		"role": None,
		"department": None,
	}
	for key, value in defaults.items():
		if key not in st.session_state:
			st.session_state[key] = value


initialize_session()

if st.session_state.logged_in and st.session_state.role == "faculty":
	st.success(f"Logged in as faculty: {st.session_state.user_name} ({st.session_state.department})")
	if st.button("Logout"):
		for key in ["logged_in", "user_id", "user_name", "email", "role", "department"]:
			st.session_state[key] = None if key != "logged_in" else False
		st.rerun()

st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.subheader("Faculty Registration")
with st.form("faculty_register_form", clear_on_submit=True):
	col1, col2 = st.columns(2)
	with col1:
		reg_name = st.text_input("Full Name")
		reg_email = st.text_input("Email")
		reg_password = st.text_input("Password", type="password")
	with col2:
		reg_dept = st.text_input("Department")
		reg_employee = st.text_input("Employee ID")

	register_btn = st.form_submit_button("Register Faculty")

if register_btn:
	if not all([reg_name.strip(), reg_email.strip(), reg_password.strip(), reg_dept.strip(), reg_employee.strip()]):
		st.error("Please fill all registration fields.")
	else:
		existing = get_user_by_email(reg_email.strip().lower())
		if existing:
			st.error("Email already registered.")
		else:
			try:
				create_user(
					name=reg_name.strip(),
					roll_number=reg_employee.strip(),
					email=reg_email.strip().lower(),
					password_hash=hash_password(reg_password),
					year_of_study=0,
					department=reg_dept.strip(),
					role="faculty",
				)
				st.success("Faculty registration successful. Please login.")
			except Exception as exc:
				st.error(f"Registration failed: {exc}")
st.markdown("</div>", unsafe_allow_html=True)

st.divider()
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.subheader("Faculty Login")
with st.form("faculty_login_form"):
	email = st.text_input("Email", key="faculty_login_email")
	password = st.text_input("Password", type="password", key="faculty_login_password")
	login_btn = st.form_submit_button("Login")

if login_btn:
	user = get_user_by_email(email.strip().lower())
	if not user:
		st.error("User not found.")
	elif user["role"] != "faculty":
		st.error("This page is for faculty login only.")
	elif not verify_password(password, user["password_hash"]):
		st.error("Invalid password.")
	else:
		st.session_state.logged_in = True
		st.session_state.user_id = user["id"]
		st.session_state.user_name = user["name"]
		st.session_state.email = user["email"]
		st.session_state.role = user["role"]
		st.session_state.department = user["department"]
		st.success("Login successful. Open Faculty Dashboard from sidebar.")
st.markdown("</div>", unsafe_allow_html=True)
