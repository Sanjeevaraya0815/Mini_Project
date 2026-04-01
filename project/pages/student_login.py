import streamlit as st
import pandas as pd

from database.db_connect import create_user, get_seeded_student_count, get_seeded_student_logins, get_user_by_email
from utils.auth_utils import hash_password, verify_password
from utils.navigation import render_sidebar_navigation


st.set_page_config(page_title="Student Login", page_icon="🔐", layout="centered")
render_sidebar_navigation()
st.title("🔐 Student Login & Registration")
st.caption("Create your account, login securely, and continue to profile setup.")

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

if st.session_state.logged_in and st.session_state.role == "student":
    st.success(f"Logged in as {st.session_state.user_name} ({st.session_state.email})")
    if st.button("Logout"):
        for key in ["logged_in", "user_id", "user_name", "email", "role", "department"]:
            st.session_state[key] = None if key != "logged_in" else False
        st.rerun()

st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.subheader("New Student Registration")
with st.form("register_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        reg_name = st.text_input("Full Name")
        reg_roll = st.text_input("Roll Number")
        reg_email = st.text_input("Email")
    with col2:
        reg_password = st.text_input("Password", type="password")
        reg_year = st.selectbox("Year", [1, 2, 3, 4])
        reg_dept = st.text_input("Department")

    register_btn = st.form_submit_button("Register")

if register_btn:
    if not all([reg_name.strip(), reg_roll.strip(), reg_email.strip(), reg_password.strip(), reg_dept.strip()]):
        st.error("Please fill all registration fields.")
    else:
        existing = get_user_by_email(reg_email.strip())
        if existing:
            st.error("Email already registered. Please login.")
        else:
            try:
                create_user(
                    name=reg_name.strip(),
                    roll_number=reg_roll.strip(),
                    email=reg_email.strip().lower(),
                    password_hash=hash_password(reg_password),
                    year_of_study=int(reg_year),
                    department=reg_dept.strip(),
                    role="student",
                )
                st.success("Registration successful. You can now login.")
            except Exception as exc:
                st.error(f"Registration failed: {exc}")
st.markdown("</div>", unsafe_allow_html=True)

st.divider()
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.subheader("Student Login")
with st.form("login_form"):
    login_email = st.text_input("Email", key="login_email")
    login_password = st.text_input("Password", type="password", key="login_password")
    login_btn = st.form_submit_button("Login")

if login_btn:
    user = get_user_by_email(login_email.strip().lower())
    if not user:
        st.error("User not found. Please register first.")
    elif user["role"] != "student":
        st.error("This page is for student login only.")
    elif not verify_password(login_password, user["password_hash"]):
        st.error("Invalid password.")
    else:
        st.session_state.logged_in = True
        st.session_state.user_id = user["id"]
        st.session_state.user_name = user["name"]
        st.session_state.email = user["email"]
        st.session_state.role = user["role"]
        st.session_state.department = user["department"]
        st.success("Login successful. Go to Profile Entry page.")
st.markdown("</div>", unsafe_allow_html=True)

st.divider()
with st.expander("Demo Seeded Student Logins", expanded=False):
    seeded_count = get_seeded_student_count()
    if seeded_count == 0:
        st.info("No Faker-seeded accounts found yet. Run: python database/seed_faker_students.py --count 1000")
    else:
        st.success(f"Seeded student accounts available: {seeded_count}")
        st.write("Common password for all seeded students: `Student@123`")

        preview_limit = st.slider("Preview rows", min_value=10, max_value=200, value=50, step=10)
        preview_rows = get_seeded_student_logins(limit=preview_limit)
        preview_df = pd.DataFrame(preview_rows)
        st.dataframe(preview_df, width="stretch")

        all_rows = get_seeded_student_logins(limit=None)
        all_df = pd.DataFrame(all_rows)
        st.download_button(
            label="Download all seeded logins (CSV)",
            data=all_df.to_csv(index=False),
            file_name="seeded_student_logins.csv",
            mime="text/csv",
        )
