import os
import json
import numpy as np
from threading import Lock
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
from mysql.connector import Error, errorcode, pooling


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Sanjeev@123"),
    "database": os.getenv("DB_NAME", "student_performance"),
}

_SCHEMA_READY = False
_INDEX_READY = False
_AUX_READY = False
_SCHEMA_LOCK = Lock()
_INDEX_LOCK = Lock()
_AUX_LOCK = Lock()
_POOL_LOCK = Lock()
_CONNECTION_POOL = None


def _get_connection_pool() -> pooling.MySQLConnectionPool:
    global _CONNECTION_POOL
    if _CONNECTION_POOL is not None:
        return _CONNECTION_POOL

    with _POOL_LOCK:
        if _CONNECTION_POOL is not None:
            return _CONNECTION_POOL

        pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        pool_size = max(1, min(pool_size, 32))

        try:
            _CONNECTION_POOL = pooling.MySQLConnectionPool(
                pool_name="student_perf_pool",
                pool_size=pool_size,
                pool_reset_session=True,
                **DB_CONFIG,
            )
        except Error as exc:
            if getattr(exc, "errno", None) == errorcode.ER_BAD_DB_ERROR:
                _create_database_if_missing()
                _CONNECTION_POOL = pooling.MySQLConnectionPool(
                    pool_name="student_perf_pool",
                    pool_size=pool_size,
                    pool_reset_session=True,
                    **DB_CONFIG,
                )
            else:
                raise

    return _CONNECTION_POOL


def _create_database_if_missing() -> None:
    db_name = DB_CONFIG.get("database", "student_performance")
    base_config = {k: v for k, v in DB_CONFIG.items() if k != "database"}

    conn = mysql.connector.connect(**base_config)
    try:
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        conn.commit()
        cursor.close()
    finally:
        if conn.is_connected():
            conn.close()


def _ensure_schema(conn) -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    with _SCHEMA_LOCK:
        if _SCHEMA_READY:
            return

        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE 'users'")
        users_exists = cursor.fetchone() is not None
        cursor.close()

        if users_exists:
            _SCHEMA_READY = True
            return

        schema_path = Path(__file__).resolve().with_name("schema.sql")
        if not schema_path.exists():
            _SCHEMA_READY = True
            return

        schema_sql = schema_path.read_text(encoding="utf-8")
        statements = [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]

        cursor = conn.cursor()
        for statement in statements:
            cursor.execute(statement)
        conn.commit()
        cursor.close()

        _SCHEMA_READY = True


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = %s
          AND table_name = %s
          AND index_name = %s
        LIMIT 1
        """,
        (DB_CONFIG.get("database", "student_performance"), table_name, index_name),
    )
    exists = cursor.fetchone() is not None
    cursor.close()
    return exists


def _ensure_indexes(conn) -> None:
    global _INDEX_READY
    if _INDEX_READY:
        return

    with _INDEX_LOCK:
        if _INDEX_READY:
            return

        index_statements = [
            (
                "users",
                "idx_users_role_department_year_name",
                "CREATE INDEX idx_users_role_department_year_name ON users (role, department, year_of_study, name)",
            ),
            (
                "users",
                "idx_users_role_email",
                "CREATE INDEX idx_users_role_email ON users (role, email)",
            ),
            (
                "predictions",
                "idx_predictions_user_created_at",
                "CREATE INDEX idx_predictions_user_created_at ON predictions (user_id, created_at)",
            ),
            (
                "predictions",
                "idx_predictions_created_at",
                "CREATE INDEX idx_predictions_created_at ON predictions (created_at)",
            ),
            (
                "certifications",
                "idx_certifications_user_created_at",
                "CREATE INDEX idx_certifications_user_created_at ON certifications (user_id, created_at)",
            ),
        ]

        cursor = conn.cursor()
        try:
            for table_name, index_name, create_sql in index_statements:
                if not _index_exists(conn, table_name, index_name):
                    cursor.execute(create_sql)
            conn.commit()
            _INDEX_READY = True
        finally:
            cursor.close()


def _ensure_aux_tables(conn) -> None:
    global _AUX_READY
    if _AUX_READY:
        return

    with _AUX_LOCK:
        if _AUX_READY:
            return

        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS student_goals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL UNIQUE,
                target_gpa DECIMAL(4,2),
                target_attendance_pct DECIMAL(5,2),
                target_coding_hours_per_week DECIMAL(6,2),
                target_internships_count INT,
                target_certifications_count INT,
                target_projects_completed INT,
                reminder_notes VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_student_goals_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()
        cursor.close()
        _AUX_READY = True


@contextmanager
def get_connection():
    conn = None
    try:
        conn = _get_connection_pool().get_connection()

        _ensure_schema(conn)
        _ensure_indexes(conn)
        _ensure_aux_tables(conn)
        yield conn
    finally:
        if conn and conn.is_connected():
            conn.close()


def execute_query(query: str, params: Optional[Tuple[Any, ...]] = None) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        cursor.close()


def fetch_one(query: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[Tuple[Any, ...]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        cursor.close()
        return row


def fetch_all(query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Tuple[Any, ...]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows


def test_connection() -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            if conn.is_connected():
                return True, "MySQL connection successful"
        return False, "MySQL connection failed"
    except Error as exc:
        return False, f"MySQL connection error: {exc}"


def create_user(
    name: str,
    roll_number: str,
    email: str,
    password_hash: str,
    year_of_study: int,
    department: str,
    role: str = "student",
) -> None:
    query = """
    INSERT INTO users (name, roll_number, email, password_hash, role, year_of_study, department)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    execute_query(query, (name, roll_number, email, password_hash, role, year_of_study, department))


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    query = """
    SELECT id, name, roll_number, email, password_hash, role, year_of_study, department
    FROM users
    WHERE email = %s
    """
    row = fetch_one(query, (email,))
    if not row:
        return None

    keys = [
        "id",
        "name",
        "roll_number",
        "email",
        "password_hash",
        "role",
        "year_of_study",
        "department",
    ]
    return dict(zip(keys, row))


def upsert_student_profile(user_id: int, payload: Dict[str, Any]) -> None:
    query = """
    INSERT INTO student_profiles (
        user_id, attendance_pct, backlogs_count, dsa_language, coding_hours_per_week,
        coding_profiles, internships_count, certifications_count, projects_completed,
        target_career_domain, languages_known, communication_rating, stress_level,
        motivation_level, resume_path, certificate_path
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON DUPLICATE KEY UPDATE
        attendance_pct = VALUES(attendance_pct),
        backlogs_count = VALUES(backlogs_count),
        dsa_language = VALUES(dsa_language),
        coding_hours_per_week = VALUES(coding_hours_per_week),
        coding_profiles = VALUES(coding_profiles),
        internships_count = VALUES(internships_count),
        certifications_count = VALUES(certifications_count),
        projects_completed = VALUES(projects_completed),
        target_career_domain = VALUES(target_career_domain),
        languages_known = VALUES(languages_known),
        communication_rating = VALUES(communication_rating),
        stress_level = VALUES(stress_level),
        motivation_level = VALUES(motivation_level),
        resume_path = VALUES(resume_path),
        certificate_path = VALUES(certificate_path)
    """
    params = (
        user_id,
        payload["attendance_pct"],
        payload["backlogs_count"],
        payload["dsa_language"],
        payload["coding_hours_per_week"],
        payload["coding_profiles"],
        payload["internships_count"],
        payload["certifications_count"],
        payload["projects_completed"],
        payload["target_career_domain"],
        payload["languages_known"],
        payload["communication_rating"],
        payload["stress_level"],
        payload["motivation_level"],
        payload["resume_path"],
        payload["certificate_path"],
    )
    execute_query(query, params)


def replace_semester_scores(user_id: int, scores: List[float]) -> None:
    delete_query = "DELETE FROM semester_scores WHERE user_id = %s"
    execute_query(delete_query, (user_id,))

    insert_query = """
    INSERT INTO semester_scores (user_id, semester_no, score)
    VALUES (%s, %s, %s)
    """
    score_rows = [(user_id, idx, score) for idx, score in enumerate(scores, start=1)]
    if not score_rows:
        return

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(insert_query, score_rows)
        conn.commit()
        cursor.close()


def replace_skills(user_id: int, skills: List[str]) -> None:
    execute_query("DELETE FROM skills WHERE user_id = %s", (user_id,))
    if not skills:
        return

    query = "INSERT INTO skills (user_id, skill_name) VALUES (%s, %s)"
    skill_rows = [(user_id, skill_name) for skill_name in skills]
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(query, skill_rows)
        conn.commit()
        cursor.close()


def save_student_profile_bundle(
    user_id: int,
    payload: Dict[str, Any],
    scores: List[float],
    skills: List[str],
) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            profile_query = """
            INSERT INTO student_profiles (
                user_id, attendance_pct, backlogs_count, dsa_language, coding_hours_per_week,
                coding_profiles, internships_count, certifications_count, projects_completed,
                target_career_domain, languages_known, communication_rating, stress_level,
                motivation_level, resume_path, certificate_path
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                attendance_pct = VALUES(attendance_pct),
                backlogs_count = VALUES(backlogs_count),
                dsa_language = VALUES(dsa_language),
                coding_hours_per_week = VALUES(coding_hours_per_week),
                coding_profiles = VALUES(coding_profiles),
                internships_count = VALUES(internships_count),
                certifications_count = VALUES(certifications_count),
                projects_completed = VALUES(projects_completed),
                target_career_domain = VALUES(target_career_domain),
                languages_known = VALUES(languages_known),
                communication_rating = VALUES(communication_rating),
                stress_level = VALUES(stress_level),
                motivation_level = VALUES(motivation_level),
                resume_path = VALUES(resume_path),
                certificate_path = VALUES(certificate_path)
            """
            profile_params = (
                user_id,
                payload["attendance_pct"],
                payload["backlogs_count"],
                payload["dsa_language"],
                payload["coding_hours_per_week"],
                payload["coding_profiles"],
                payload["internships_count"],
                payload["certifications_count"],
                payload["projects_completed"],
                payload["target_career_domain"],
                payload["languages_known"],
                payload["communication_rating"],
                payload["stress_level"],
                payload["motivation_level"],
                payload["resume_path"],
                payload["certificate_path"],
            )
            cursor.execute(profile_query, profile_params)

            cursor.execute("DELETE FROM semester_scores WHERE user_id = %s", (user_id,))
            score_rows = [(user_id, idx, score) for idx, score in enumerate(scores, start=1)]
            if score_rows:
                cursor.executemany(
                    """
                    INSERT INTO semester_scores (user_id, semester_no, score)
                    VALUES (%s, %s, %s)
                    """,
                    score_rows,
                )

            cursor.execute("DELETE FROM skills WHERE user_id = %s", (user_id,))
            skill_rows = [(user_id, skill_name) for skill_name in skills]
            if skill_rows:
                cursor.executemany(
                    "INSERT INTO skills (user_id, skill_name) VALUES (%s, %s)",
                    skill_rows,
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def get_profile_bundle(user_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT attendance_pct, backlogs_count, dsa_language, coding_hours_per_week,
                   coding_profiles, internships_count, certifications_count, projects_completed,
                   target_career_domain, languages_known, communication_rating, stress_level,
                   motivation_level, resume_path, certificate_path
            FROM student_profiles
            WHERE user_id = %s
            """,
            (user_id,),
        )
        profile_row = cursor.fetchone()

        cursor.execute(
            "SELECT semester_no, score FROM semester_scores WHERE user_id = %s ORDER BY semester_no",
            (user_id,),
        )
        score_rows = cursor.fetchall()

        cursor.execute("SELECT skill_name FROM skills WHERE user_id = %s", (user_id,))
        skill_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT target_gpa, target_attendance_pct, target_coding_hours_per_week,
                   target_internships_count, target_certifications_count,
                   target_projects_completed, reminder_notes, created_at, updated_at
            FROM student_goals
            WHERE user_id = %s
            """,
            (user_id,),
        )
        goal_row = cursor.fetchone()
        cursor.close()

    return {
        "profile": profile_row,
        "semester_scores": [row[1] for row in score_rows],
        "skills": [row[0] for row in skill_rows],
        "goals": goal_row,
    }


def save_student_goals(user_id: int, payload: Dict[str, Any]) -> None:
    query = """
    INSERT INTO student_goals (
        user_id, target_gpa, target_attendance_pct, target_coding_hours_per_week,
        target_internships_count, target_certifications_count, target_projects_completed,
        reminder_notes
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        target_gpa = VALUES(target_gpa),
        target_attendance_pct = VALUES(target_attendance_pct),
        target_coding_hours_per_week = VALUES(target_coding_hours_per_week),
        target_internships_count = VALUES(target_internships_count),
        target_certifications_count = VALUES(target_certifications_count),
        target_projects_completed = VALUES(target_projects_completed),
        reminder_notes = VALUES(reminder_notes)
    """
    execute_query(
        query,
        (
            user_id,
            payload.get("target_gpa"),
            payload.get("target_attendance_pct"),
            payload.get("target_coding_hours_per_week"),
            payload.get("target_internships_count"),
            payload.get("target_certifications_count"),
            payload.get("target_projects_completed"),
            payload.get("reminder_notes"),
        ),
    )


def get_student_goals(user_id: int) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        """
        SELECT target_gpa, target_attendance_pct, target_coding_hours_per_week,
               target_internships_count, target_certifications_count,
               target_projects_completed, reminder_notes, created_at, updated_at
        FROM student_goals
        WHERE user_id = %s
        """,
        (user_id,),
    )
    if not row:
        return None

    return {
        "target_gpa": float(row[0]) if row[0] is not None else None,
        "target_attendance_pct": float(row[1]) if row[1] is not None else None,
        "target_coding_hours_per_week": float(row[2]) if row[2] is not None else None,
        "target_internships_count": int(row[3]) if row[3] is not None else None,
        "target_certifications_count": int(row[4]) if row[4] is not None else None,
        "target_projects_completed": int(row[5]) if row[5] is not None else None,
        "reminder_notes": row[6] or "",
        "created_at": row[7],
        "updated_at": row[8],
    }


def save_prediction(
    user_id: int,
    academic_score: float,
    placement_readiness: str,
    feature_importance_json: str,
    model_version: str = "v1",
) -> None:
    query = """
    INSERT INTO predictions (user_id, academic_score, placement_readiness, model_version, feature_importance)
    VALUES (%s, %s, %s, %s, %s)
    """
    execute_query(query, (user_id, academic_score, placement_readiness, model_version, feature_importance_json))


def fetch_latest_prediction(user_id: int) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        """
        SELECT academic_score, placement_readiness, feature_importance, created_at
        FROM predictions
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    )
    if not row:
        return None

    return {
        "academic_score": float(row[0]),
        "placement_readiness": row[1],
        "feature_importance": row[2],
        "created_at": row[3],
    }


def get_student_profile_paths(user_id: int) -> Dict[str, str]:
    row = fetch_one(
        """
        SELECT resume_path, certificate_path
        FROM student_profiles
        WHERE user_id = %s
        """,
        (user_id,),
    )
    if not row:
        return {"resume_path": "", "certificate_path": ""}
    return {
        "resume_path": row[0] or "",
        "certificate_path": row[1] or "",
    }


def save_certification_scan_results(user_id: int, cert_names: List[str], issuer: str = "Scanned") -> int:
    execute_query("DELETE FROM certifications WHERE user_id = %s", (user_id,))
    if not cert_names:
        return 0

    with get_connection() as conn:
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO certifications (user_id, cert_name, issuer, verified)
        VALUES (%s, %s, %s, %s)
        """
        rows = [(user_id, cert_name, issuer, 1) for cert_name in cert_names]
        cursor.executemany(insert_query, rows)
        conn.commit()
        cursor.close()

    execute_query(
        """
        UPDATE student_profiles
        SET certifications_count = %s
        WHERE user_id = %s
        """,
        (len(cert_names), user_id),
    )
    return len(cert_names)


def get_certifications(user_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT cert_name, issuer, verified, created_at
        FROM certifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        """,
        (user_id,),
    )
    return [
        {
            "cert_name": row[0],
            "issuer": row[1],
            "verified": bool(row[2]),
            "created_at": row[3],
        }
        for row in rows
    ]


def get_job_roles() -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT role_name, required_skills, min_internships, min_certifications, target_domain
        FROM job_roles
        ORDER BY role_name
        """
    )

    results: List[Dict[str, Any]] = []
    for row in rows:
        required_skills = row[1]
        if isinstance(required_skills, str):
            try:
                required_skills = json.loads(required_skills)
            except json.JSONDecodeError:
                required_skills = []

        results.append(
            {
                "role_name": row[0],
                "required_skills": required_skills if isinstance(required_skills, list) else [],
                "min_internships": int(row[2] or 0),
                "min_certifications": int(row[3] or 0),
                "target_domain": row[4] or "",
            }
        )
    return results


def get_student_department(user_id: int) -> str:
    row = fetch_one("SELECT department FROM users WHERE id = %s", (user_id,))
    return row[0] if row and row[0] else ""


def get_faculty_student_rows(department: str, risk_level: Optional[str] = None) -> List[Dict[str, Any]]:
    params: List[Any] = [department]
    risk_clause = ""
    if risk_level in {"Low", "Medium", "High"}:
        risk_clause = "AND p.placement_readiness = %s"
        params.append(risk_level)

    rows = fetch_all(
        f"""
        SELECT
            u.id,
            u.name,
            u.roll_number,
            u.email,
            u.year_of_study,
            COALESCE(sp.attendance_pct, 0),
            COALESCE(sp.backlogs_count, 0),
            p.academic_score,
            p.placement_readiness,
            p.created_at
        FROM users u
        LEFT JOIN student_profiles sp ON sp.user_id = u.id
        LEFT JOIN (
            SELECT p1.user_id, p1.academic_score, p1.placement_readiness, p1.created_at
            FROM predictions p1
            JOIN (
                SELECT user_id, MAX(created_at) AS max_created_at
                FROM predictions
                GROUP BY user_id
            ) p2 ON p2.user_id = p1.user_id AND p2.max_created_at = p1.created_at
        ) p ON p.user_id = u.id
        WHERE u.role = 'student'
          AND u.department = %s
          {risk_clause}
        ORDER BY u.year_of_study, u.name
        """,
        tuple(params),
    )

    results = []
    for row in rows:
        results.append(
            {
                "student_id": row[0],
                "name": row[1],
                "roll_number": row[2],
                "email": row[3],
                "year": row[4],
                "attendance_pct": float(row[5] or 0),
                "backlogs_count": int(row[6] or 0),
                "academic_score": float(row[7]) if row[7] is not None else None,
                "placement_readiness": row[8],
                "predicted_at": row[9],
            }
        )
    return results


def get_department_analytics(department: str) -> Dict[str, Any]:
    total_students_row = fetch_one(
        "SELECT COUNT(*) FROM users WHERE role = 'student' AND department = %s",
        (department,),
    )
    total_students = int(total_students_row[0] if total_students_row else 0)

    aggregates_row = fetch_one(
        """
        SELECT
            COALESCE(SUM(latest.placement_readiness = 'Low'), 0) AS low_count,
            COALESCE(SUM(latest.placement_readiness = 'Medium'), 0) AS medium_count,
            COALESCE(SUM(latest.placement_readiness = 'High'), 0) AS high_count,
            COALESCE(AVG(latest.academic_score), 0) AS avg_score
        FROM (
            SELECT p.user_id, p.placement_readiness, p.academic_score
            FROM predictions p
            JOIN (
                SELECT user_id, MAX(created_at) AS max_created_at
                FROM predictions
                GROUP BY user_id
            ) lp ON lp.user_id = p.user_id AND lp.max_created_at = p.created_at
        ) latest
        JOIN users u ON u.id = latest.user_id
        WHERE u.department = %s AND u.role = 'student'
        """,
        (department,),
    )
    readiness_counts = {
        "Low": int(aggregates_row[0] if aggregates_row else 0),
        "Medium": int(aggregates_row[1] if aggregates_row else 0),
        "High": int(aggregates_row[2] if aggregates_row else 0),
    }

    return {
        "total_students": total_students,
        "avg_academic_score": float(aggregates_row[3]) if aggregates_row and aggregates_row[3] is not None else 0.0,
        "readiness_counts": readiness_counts,
    }


def get_department_prediction_trend(department: str, months: int = 6) -> List[Dict[str, Any]]:
    safe_months = months if months > 0 else 6
    rows = fetch_all(
        """
        SELECT DATE_FORMAT(p.created_at, '%Y-%m') AS month_label, COUNT(*) AS prediction_count
        FROM predictions p
        JOIN users u ON u.id = p.user_id
        WHERE u.role = 'student'
          AND u.department = %s
          AND p.created_at >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
        GROUP BY DATE_FORMAT(p.created_at, '%Y-%m')
        ORDER BY month_label
        """,
        (department, safe_months),
    )

    return [
        {
            "month": row[0],
            "predictions": int(row[1] or 0),
        }
        for row in rows
    ]


def get_seeded_student_count() -> int:
    row = fetch_one(
        """
        SELECT COUNT(*)
        FROM users
        WHERE role = 'student' AND email LIKE 'faker_student_%@example.com'
        """
    )
    return int(row[0] if row else 0)


def get_seeded_student_logins(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    limit_clause = ""
    params: Tuple[Any, ...] = ()
    if limit is not None and limit > 0:
        limit_clause = "LIMIT %s"
        params = (limit,)

    rows = fetch_all(
        f"""
        SELECT name, roll_number, email, year_of_study, department
        FROM users
        WHERE role = 'student' AND email LIKE 'faker_student_%@example.com'
        ORDER BY id
        {limit_clause}
        """,
        params,
    )

    return [
        {
            "name": row[0],
            "roll_number": row[1],
            "email": row[2],
            "year": row[3],
            "department": row[4],
        }
        for row in rows
    ]


def seed_synthetic_students(total_rows: int = 10_000, batch_size: int = 500) -> Dict[str, int]:
    if total_rows <= 0:
        return {"requested": 0, "inserted": 0}

    existing = get_seeded_student_count()
    start_idx = existing + 1

    dept_options = ["CSE", "IT", "ECE", "EEE", "MECH"]
    domain_options = [
        "Software Development",
        "Data Science",
        "Data Analytics",
        "Cloud Computing",
        "Cyber Security",
    ]
    dsa_options = ["Python", "Java", "C++", "C", "JavaScript"]
    lang_pool = ["English", "Hindi", "Tamil", "Telugu", "Kannada", "Malayalam"]
    skill_pool = [
        "Python", "Java", "C++", "SQL", "Machine Learning", "Deep Learning",
        "Data Structures", "Algorithms", "Web Development", "Cloud", "Docker", "Git",
    ]

    inserted_total = 0
    rng = np.random.default_rng(42 + existing)

    with get_connection() as conn:
        cursor = conn.cursor()

        insert_user_q = """
        INSERT INTO users (name, roll_number, email, password_hash, role, year_of_study, department)
        VALUES (%s, %s, %s, %s, 'student', %s, %s)
        """
        insert_profile_q = """
        INSERT INTO student_profiles (
            user_id, attendance_pct, backlogs_count, dsa_language, coding_hours_per_week,
            coding_profiles, internships_count, certifications_count, projects_completed,
            target_career_domain, languages_known, communication_rating, stress_level,
            motivation_level, resume_path, certificate_path
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '', '')
        """
        insert_sem_q = """
        INSERT INTO semester_scores (user_id, semester_no, score)
        VALUES (%s, %s, %s)
        """
        insert_skill_q = """
        INSERT IGNORE INTO skills (user_id, skill_name)
        VALUES (%s, %s)
        """

        for batch_start in range(0, total_rows, batch_size):
            current_batch = min(batch_size, total_rows - batch_start)
            user_rows = []
            synthetic_rows = []

            for offset in range(current_batch):
                serial = start_idx + batch_start + offset
                roll = f"SYN{serial:06d}"
                email = f"faker_student_{serial}@example.com"
                name = f"Synthetic Student {serial}"
                year = int(rng.integers(1, 5))
                dept = str(rng.choice(dept_options))

                attendance = round(float(rng.uniform(60, 100)), 2)
                backlogs = int(rng.integers(0, 7))
                dsa_language = str(rng.choice(dsa_options))
                coding_hours = round(float(rng.uniform(2, 35)), 2)

                coding_profiles = {
                    "leetcode": f"https://leetcode.com/u/syn{serial}" if rng.random() > 0.35 else "",
                    "hackerrank": f"https://hackerrank.com/syn{serial}" if rng.random() > 0.45 else "",
                    "codechef": f"https://codechef.com/users/syn{serial}" if rng.random() > 0.55 else "",
                    "github": f"https://github.com/syn{serial}" if rng.random() > 0.30 else "",
                }

                internships = int(rng.integers(0, 4))
                certifications = int(rng.integers(0, 9))
                projects = int(rng.integers(0, 11))
                target_domain = str(rng.choice(domain_options))

                lang_count = int(rng.integers(1, 4))
                lang_indices = rng.choice(len(lang_pool), size=lang_count, replace=False)
                languages_known = [lang_pool[i] for i in lang_indices]

                communication = int(rng.integers(3, 10))
                stress = int(rng.integers(1, 10))
                motivation = int(rng.integers(3, 10))

                semester_scores = [round(float(rng.uniform(5.0, 9.9)), 2) for _ in range(8)]
                skill_count = int(rng.integers(3, 8))
                skill_indices = rng.choice(len(skill_pool), size=skill_count, replace=False)
                chosen_skills = [skill_pool[i] for i in skill_indices]

                user_rows.append((name, roll, email, "synthetic_hash", year, dept))
                synthetic_rows.append(
                    {
                        "roll": roll,
                        "attendance": attendance,
                        "backlogs": backlogs,
                        "dsa_language": dsa_language,
                        "coding_hours": coding_hours,
                        "coding_profiles": json.dumps(coding_profiles),
                        "internships": internships,
                        "certifications": certifications,
                        "projects": projects,
                        "target_domain": target_domain,
                        "languages_known": json.dumps(languages_known),
                        "communication": communication,
                        "stress": stress,
                        "motivation": motivation,
                        "semester_scores": semester_scores,
                        "skills": chosen_skills,
                    }
                )

            cursor.executemany(insert_user_q, user_rows)

            roll_list = [row[1] for row in user_rows]
            placeholders = ",".join(["%s"] * len(roll_list))
            cursor.execute(
                f"SELECT id, roll_number FROM users WHERE roll_number IN ({placeholders})",
                tuple(roll_list),
            )
            id_rows = cursor.fetchall()
            roll_to_id = {roll_number: user_id for user_id, roll_number in id_rows}

            profile_rows = []
            sem_rows = []
            skill_rows = []
            for row in synthetic_rows:
                user_id = roll_to_id.get(row["roll"])
                if not user_id:
                    continue

                profile_rows.append(
                    (
                        user_id,
                        row["attendance"],
                        row["backlogs"],
                        row["dsa_language"],
                        row["coding_hours"],
                        row["coding_profiles"],
                        row["internships"],
                        row["certifications"],
                        row["projects"],
                        row["target_domain"],
                        row["languages_known"],
                        row["communication"],
                        row["stress"],
                        row["motivation"],
                    )
                )

                for sem_no, sem_score in enumerate(row["semester_scores"], start=1):
                    sem_rows.append((user_id, sem_no, sem_score))

                for skill_name in row["skills"]:
                    skill_rows.append((user_id, skill_name))

            if profile_rows:
                cursor.executemany(insert_profile_q, profile_rows)
            if sem_rows:
                cursor.executemany(insert_sem_q, sem_rows)
            if skill_rows:
                cursor.executemany(insert_skill_q, skill_rows)

            conn.commit()
            inserted_total += len(profile_rows)

        cursor.close()

    return {
        "requested": int(total_rows),
        "inserted": int(inserted_total),
        "existing_before": int(existing),
        "existing_after": int(existing + inserted_total),
    }
