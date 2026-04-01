from datetime import datetime
from typing import Any, Dict, Iterable, List

import fitz


def _safe_text(value: Any, default: str = "N/A") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _profile_value(profile, index: int, default="N/A"):
    if not profile or len(profile) <= index:
        return default
    value = profile[index]
    return default if value is None else value


def _write_line(page, y: float, text: str, *, fontsize: int = 11, bold: bool = False, color=(0, 0, 0)):
    page.insert_text((40, y), text, fontsize=fontsize, fontname="helv", color=color)
    return page, y + (fontsize + 6)


def _write_section(doc, page, y: float, title: str, lines: Iterable[str]):
    if page is None:
        page = doc.new_page()
        y = 44

    if y > 760:
        page = doc.new_page()
        y = 44

    page, y = _write_line(page, y, title, fontsize=14, bold=True)
    for line in lines:
        if y > 760:
            page = doc.new_page()
            y = 44
        page, y = _write_line(page, y, f"- {line}", fontsize=10)
    return page, y + 4


def generate_student_report_pdf(
    *,
    student_name: str,
    user_id: int,
    department: str,
    academic_score: float,
    readiness: str,
    profile_score: float,
    resume_score: float,
    feature_importance: Dict[str, Dict[str, float]],
    recommendations: List[Dict[str, Any]],
    profile_bundle: Dict[str, Any],
    profile_summary: Dict[str, Any],
    goal_progress: List[Dict[str, Any]],
    alerts: List[Dict[str, str]],
) -> bytes:
    profile = profile_bundle.get("profile")
    semester_scores = profile_bundle.get("semester_scores", [])
    skills = profile_bundle.get("skills", [])

    doc = fitz.open()
    page = doc.new_page()
    y = 44

    page, y = _write_line(page, y, "Student Performance Report", fontsize=20, bold=True)
    page, y = _write_line(page, y, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", fontsize=10)
    page, y = _write_line(page, y, f"Student: {student_name} | User ID: {user_id} | Department: {_safe_text(department)}", fontsize=11)
    page, y = _write_line(page, y, f"Academic Score: {academic_score:.2f}/100 | Readiness: {_safe_text(readiness)}", fontsize=11, bold=True)
    page, y = _write_line(page, y, f"Profile Score: {profile_score:.2f}/100 | Resume Score: {resume_score:.2f}/100", fontsize=11)

    summary_lines = [
        f"Attendance: {_safe_text(_profile_value(profile, 0), '0')}",
        f"Backlogs: {_safe_text(_profile_value(profile, 1), '0')}",
        f"DSA Language: {_safe_text(_profile_value(profile, 2))}",
        f"Coding Hours/Week: {_safe_text(_profile_value(profile, 3), '0')}",
        f"Internships: {_safe_text(_profile_value(profile, 5), '0')}",
        f"Certifications: {_safe_text(_profile_value(profile, 6), '0')}",
        f"Projects Completed: {_safe_text(_profile_value(profile, 7), '0')}",
        f"Target Domain: {_safe_text(_profile_value(profile, 8))}",
    ]
    page, y = _write_section(doc, page, y + 8, "Profile Snapshot", summary_lines)

    if semester_scores:
        score_lines = [f"S{i + 1}: {float(score):.2f}" for i, score in enumerate(semester_scores)]
    else:
        score_lines = ["No semester scores available"]
    page, y = _write_section(doc, page, y, "Semester Performance", score_lines)

    helping = feature_importance.get("helping", {}) if isinstance(feature_importance, dict) else {}
    hurting = feature_importance.get("hurting", {}) if isinstance(feature_importance, dict) else {}
    feature_lines = [
        *(f"Helping: {feature} ({impact:.3f})" for feature, impact in helping.items()),
        *(f"Hurting: {feature} ({impact:.3f})" for feature, impact in hurting.items()),
    ] or ["No feature importance data available"]
    page, y = _write_section(doc, page, y, "Explainable Prediction", feature_lines)

    top_roles = recommendations[:5]
    recommendation_lines = [
        f"{item['Role']} - Score {item['Recommendation Score']:.2f}"
        for item in top_roles
    ] or ["No role recommendations available"]
    page, y = _write_section(doc, page, y, "Personalized Recommendations", recommendation_lines)

    health_lines = [
        f"Technical skills tagged: {len(skills)}",
        f"Coding profiles filled: {profile_summary.get('coding_profile_count', 0)} / 4",
        f"Coding profile URLs missing: {', '.join(profile_summary.get('missing_coding_profiles', [])) or 'None'}",
        f"Languages known: {profile_summary.get('languages_known_count', 0)}",
    ]
    page, y = _write_section(doc, page, y, "Profile Health", health_lines)

    if goal_progress:
        goal_lines = [
            f"{row['label']}: {row['current']} / {row['target']} ({row['progress']:.1f}%)"
            for row in goal_progress
        ]
    else:
        goal_lines = ["No goals saved yet"]
    page, y = _write_section(doc, page, y, "Goal Progress", goal_lines)

    if alerts:
        alert_lines = [f"{item['level'].title()}: {item['message']}" for item in alerts[:8]]
    else:
        alert_lines = ["No active alerts"]
    page, y = _write_section(doc, page, y, "Alerts and Reminders", alert_lines)

    return doc.tobytes()