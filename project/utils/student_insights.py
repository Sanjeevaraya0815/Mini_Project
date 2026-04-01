import json
from pathlib import Path
from typing import Any, Dict, List

from database.db_connect import get_job_roles
from utils.resume_parser import parse_resume_skills


CODING_PROFILE_KEYS = ("leetcode", "hackerrank", "codechef", "github")


def _profile_value(profile, index: int, default=None):
    if not profile or len(profile) <= index:
        return default
    value = profile[index]
    return default if value is None else value


def decode_coding_profiles(profile_bundle: Dict[str, Any]) -> Dict[str, str]:
    profile = profile_bundle.get("profile")
    raw_profiles = _profile_value(profile, 4, None)

    if isinstance(raw_profiles, dict):
        data = raw_profiles
    else:
        try:
            data = json.loads(raw_profiles) if raw_profiles else {}
        except (TypeError, json.JSONDecodeError):
            data = {}

    return {key: str(data.get(key, "")).strip() for key in CODING_PROFILE_KEYS}


def _count_languages(profile_bundle: Dict[str, Any]) -> int:
    profile = profile_bundle.get("profile")
    raw_value = _profile_value(profile, 9, None)
    if isinstance(raw_value, list):
        return len(raw_value)
    try:
        loaded = json.loads(raw_value) if raw_value else []
    except (TypeError, json.JSONDecodeError):
        loaded = []
    return len(loaded) if isinstance(loaded, list) else 0


def profile_health_summary(profile_bundle: Dict[str, Any]) -> Dict[str, Any]:
    profile = profile_bundle.get("profile")
    coding_profiles = decode_coding_profiles(profile_bundle)
    filled_coding_profiles = [name for name, value in coding_profiles.items() if value]

    return {
        "coding_profiles": coding_profiles,
        "coding_profile_count": len(filled_coding_profiles),
        "missing_coding_profiles": [name.title() for name, value in coding_profiles.items() if not value],
        "languages_known_count": _count_languages(profile_bundle),
        "skills_count": len(profile_bundle.get("skills", [])),
        "semester_scores_count": len(profile_bundle.get("semester_scores", [])),
        "resume_present": bool(_profile_value(profile, 13, "")),
        "certificate_present": bool(_profile_value(profile, 14, "")),
    }


def compute_profile_score(profile_bundle: Dict[str, Any]) -> Dict[str, Any]:
    profile = profile_bundle.get("profile")
    semester_scores = profile_bundle.get("semester_scores", [])
    skills = profile_bundle.get("skills", [])

    if not profile:
        return {
            "score": 0.0,
            "components": [],
            "semester_average": 0.0,
        }

    attendance = float(_profile_value(profile, 0, 0) or 0)
    backlogs = float(_profile_value(profile, 1, 0) or 0)
    coding_hours = float(_profile_value(profile, 3, 0) or 0)
    internships = float(_profile_value(profile, 5, 0) or 0)
    certifications = float(_profile_value(profile, 6, 0) or 0)
    projects = float(_profile_value(profile, 7, 0) or 0)
    communication = float(_profile_value(profile, 10, 5) or 5)
    stress = float(_profile_value(profile, 11, 5) or 5)
    motivation = float(_profile_value(profile, 12, 5) or 5)
    coding_profile_count = len([value for value in decode_coding_profiles(profile_bundle).values() if value])
    languages_count = _count_languages(profile_bundle)
    semester_average = sum(float(score) for score in semester_scores) / len(semester_scores) if semester_scores else 0.0

    components = [
        {"label": "Attendance", "value": round(min(attendance, 100.0), 2)},
        {"label": "Backlogs", "value": round(max(0.0, 100.0 - min(backlogs, 10.0) * 10.0), 2)},
        {"label": "Coding Hours", "value": round(min(coding_hours * 4.0, 100.0), 2)},
        {"label": "Internships", "value": round(min(internships * 20.0, 100.0), 2)},
        {"label": "Certifications", "value": round(min(certifications * 12.5, 100.0), 2)},
        {"label": "Projects", "value": round(min(projects * 10.0, 100.0), 2)},
        {"label": "Communication", "value": round(min(communication * 10.0, 100.0), 2)},
        {"label": "Motivation", "value": round(min(motivation * 10.0, 100.0), 2)},
        {"label": "Skills", "value": round(min(len(skills) * 8.0, 100.0), 2)},
        {"label": "Coding Profiles", "value": round(min(coding_profile_count * 25.0, 100.0), 2)},
        {"label": "Languages", "value": round(min(languages_count * 15.0, 100.0), 2)},
        {"label": "Semester Avg", "value": round(min(semester_average * 10.0, 100.0), 2)},
        {"label": "Stress Penalty", "value": round(max(0.0, 100.0 - min(stress * 8.0, 80.0)), 2)},
    ]

    score = (
        attendance * 0.12
        + max(0.0, 100.0 - min(backlogs, 10.0) * 10.0) * 0.08
        + min(coding_hours * 4.0, 100.0) * 0.1
        + min(internships * 20.0, 100.0) * 0.1
        + min(certifications * 12.5, 100.0) * 0.08
        + min(projects * 10.0, 100.0) * 0.08
        + min(communication * 10.0, 100.0) * 0.08
        + min(motivation * 10.0, 100.0) * 0.08
        + min(len(skills) * 8.0, 100.0) * 0.05
        + min(coding_profile_count * 25.0, 100.0) * 0.07
        + min(languages_count * 15.0, 100.0) * 0.04
        + min(semester_average * 10.0, 100.0) * 0.08
        + max(0.0, 100.0 - min(stress * 8.0, 80.0)) * 0.04
    )

    return {
        "score": round(min(score, 100.0), 2),
        "components": components,
        "semester_average": round(semester_average, 2),
    }


def compute_resume_insight(resume_path: str) -> Dict[str, Any]:
    if not resume_path:
        return {
            "score": 0.0,
            "extracted_skills": [],
            "top_roles": [],
        }

    path = Path(resume_path)
    if not path.exists():
        return {
            "score": 0.0,
            "extracted_skills": [],
            "top_roles": [],
        }

    extracted_skills = parse_resume_skills(str(path))
    role_catalog = get_job_roles()

    if not role_catalog:
        return {
            "score": 0.0,
            "extracted_skills": extracted_skills,
            "top_roles": [],
        }

    extracted_set = {skill.lower() for skill in extracted_skills}
    scored = []
    for role in role_catalog:
        required = {skill.lower() for skill in role.get("required_skills", [])}
        if not required:
            match_pct = 0.0
        else:
            match_pct = (len(extracted_set & required) / len(required)) * 100
        scored.append((role["role_name"], round(match_pct, 2), sorted(list(extracted_set & required))))

    scored.sort(key=lambda item: item[1], reverse=True)
    resume_score = round(sum(item[1] for item in scored[:3]) / max(len(scored[:3]), 1), 2)

    return {
        "score": resume_score,
        "extracted_skills": extracted_skills,
        "top_roles": scored[:5],
    }


def build_goal_progress(profile_bundle: Dict[str, Any], goal_row: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    profile = profile_bundle.get("profile")
    semester_scores = profile_bundle.get("semester_scores", [])
    if not goal_row:
        return []

    attendance = float(_profile_value(profile, 0, 0) or 0)
    coding_hours = float(_profile_value(profile, 3, 0) or 0)
    internships = float(_profile_value(profile, 5, 0) or 0)
    certifications = float(_profile_value(profile, 6, 0) or 0)
    projects = float(_profile_value(profile, 7, 0) or 0)
    semester_average = sum(float(score) for score in semester_scores) / len(semester_scores) if semester_scores else 0.0

    metrics = [
        ("Target Attendance %", attendance, goal_row.get("target_attendance_pct")),
        ("Target GPA/CGPA", semester_average, goal_row.get("target_gpa")),
        ("Target Coding Hours", coding_hours, goal_row.get("target_coding_hours_per_week")),
        ("Target Internships", internships, goal_row.get("target_internships_count")),
        ("Target Certifications", certifications, goal_row.get("target_certifications_count")),
        ("Target Projects", projects, goal_row.get("target_projects_completed")),
    ]

    progress_rows: List[Dict[str, Any]] = []
    for label, current, target in metrics:
        if target is None:
            continue
        target_value = float(target)
        if target_value <= 0:
            progress = 100.0
        else:
            progress = min((float(current) / target_value) * 100.0, 100.0)
        progress_rows.append(
            {
                "label": label,
                "current": round(float(current), 2),
                "target": round(target_value, 2),
                "progress": round(progress, 2),
            }
        )

    return progress_rows


def build_alerts(profile_bundle: Dict[str, Any], goal_row: Dict[str, Any] | None, profile_score: float, resume_score: float) -> List[Dict[str, str]]:
    profile = profile_bundle.get("profile")
    semester_scores = profile_bundle.get("semester_scores", [])
    alerts: List[Dict[str, str]] = []

    attendance = float(_profile_value(profile, 0, 0) or 0)
    backlogs = int(_profile_value(profile, 1, 0) or 0)
    coding_hours = float(_profile_value(profile, 3, 0) or 0)
    internships = int(_profile_value(profile, 5, 0) or 0)
    certifications = int(_profile_value(profile, 6, 0) or 0)
    skills_count = len(profile_bundle.get("skills", []))
    semester_average = sum(float(score) for score in semester_scores) / len(semester_scores) if semester_scores else 0.0

    if attendance < 75:
        alerts.append({"level": "warning", "message": f"Attendance is {attendance:.1f}%, which is below the safe threshold of 75%."})
    if backlogs > 0:
        alerts.append({"level": "warning", "message": f"You currently have {backlogs} backlog(s). Clearing them should be a priority."})
    if coding_hours < 5:
        alerts.append({"level": "info", "message": "Increase coding time to at least 5 hours per week to improve readiness."})
    if internships == 0:
        alerts.append({"level": "info", "message": "No internship is recorded yet. Add one or set an internship goal."})
    if certifications == 0:
        alerts.append({"level": "info", "message": "No certifications are recorded yet. Add one or set a certification goal."})
    if skills_count < 3:
        alerts.append({"level": "info", "message": "Your technical skills list is small. Add more skills for stronger recommendations."})
    if semester_average and semester_average < 7.0:
        alerts.append({"level": "warning", "message": f"Your semester average is {semester_average:.2f}. Aim for 7.0 or above."})
    if profile_score < 60:
        alerts.append({"level": "warning", "message": f"Profile score is {profile_score:.1f}/100. Several areas still need attention."})
    if resume_score and resume_score < 45:
        alerts.append({"level": "warning", "message": f"Resume score is {resume_score:.1f}/100. Improve skills alignment and keywords."})

    if goal_row:
        target_attendance = goal_row.get("target_attendance_pct")
        if target_attendance is not None and attendance < float(target_attendance):
            alerts.append({"level": "info", "message": f"Attendance is below your goal of {float(target_attendance):.1f}%."})

        target_gpa = goal_row.get("target_gpa")
        if target_gpa is not None and semester_average < float(target_gpa):
            alerts.append({"level": "info", "message": f"Semester average is below your goal of {float(target_gpa):.2f}."})

        target_coding_hours = goal_row.get("target_coding_hours_per_week")
        if target_coding_hours is not None and coding_hours < float(target_coding_hours):
            alerts.append({"level": "info", "message": f"Coding hours are below your goal of {float(target_coding_hours):.1f} hours/week."})

        target_internships = goal_row.get("target_internships_count")
        if target_internships is not None and internships < int(target_internships):
            alerts.append({"level": "info", "message": f"Internships are below your goal of {int(target_internships)}."})

        target_certifications = goal_row.get("target_certifications_count")
        if target_certifications is not None and certifications < int(target_certifications):
            alerts.append({"level": "info", "message": f"Certifications are below your goal of {int(target_certifications)}."})

    return alerts


def profile_completeness(profile_bundle: Dict[str, Any]) -> Dict[str, Any]:
    profile = profile_bundle.get("profile")
    coding_profiles = decode_coding_profiles(profile_bundle)
    semester_scores = profile_bundle.get("semester_scores", [])
    skills = profile_bundle.get("skills", [])

    checks = [
        ("Attendance entered", bool(profile and _profile_value(profile, 0, None) is not None)),
        ("DSA language selected", bool(profile and str(_profile_value(profile, 2, "")).strip())),
        ("Coding hours entered", bool(profile and float(_profile_value(profile, 3, 0) or 0) > 0)),
        ("At least 1 technical skill", len(skills) > 0),
        ("At least 1 coding profile URL", any(bool(value) for value in coding_profiles.values())),
        ("Semester scores filled", len(semester_scores) >= 8),
        ("Target domain selected", bool(profile and str(_profile_value(profile, 8, "")).strip())),
        ("Languages known selected", _count_languages(profile_bundle) > 0),
        ("Resume uploaded", bool(profile and str(_profile_value(profile, 13, "")).strip())),
        ("Certificate uploaded", bool(profile and str(_profile_value(profile, 14, "")).strip())),
    ]

    completed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    missing = [label for label, ok in checks if not ok]

    return {
        "percent": round((completed / total) * 100.0, 1) if total else 0.0,
        "completed": completed,
        "total": total,
        "missing": missing,
    }


def rule_based_tips(profile_bundle: Dict[str, Any], profile_score: float, resume_score: float) -> List[str]:
    profile = profile_bundle.get("profile")
    semester_scores = profile_bundle.get("semester_scores", [])
    skills = profile_bundle.get("skills", [])
    coding_profiles = decode_coding_profiles(profile_bundle)

    attendance = float(_profile_value(profile, 0, 0) or 0)
    backlogs = int(_profile_value(profile, 1, 0) or 0)
    coding_hours = float(_profile_value(profile, 3, 0) or 0)
    internships = int(_profile_value(profile, 5, 0) or 0)
    certifications = int(_profile_value(profile, 6, 0) or 0)
    projects = int(_profile_value(profile, 7, 0) or 0)
    semester_avg = sum(float(score) for score in semester_scores) / len(semester_scores) if semester_scores else 0.0

    tips: List[str] = []
    if attendance < 80:
        tips.append("Push attendance above 80% to improve both academic and readiness outcomes.")
    if backlogs > 0:
        tips.append("Clear at least one backlog this term to reduce risk quickly.")
    if coding_hours < 7:
        tips.append("Increase coding practice to 7-10 hours/week for better placement readiness.")
    if len(skills) < 5:
        tips.append("Add 2-3 more relevant technical skills to strengthen your profile.")
    if internships < 1:
        tips.append("Target at least one internship to improve real-world readiness.")
    if certifications < 2:
        tips.append("Complete 1-2 certifications in your target domain.")
    if projects < 3:
        tips.append("Build more projects and keep one project portfolio-ready.")
    if semester_avg and semester_avg < 7.5:
        tips.append("Aim for semester average above 7.5 by focusing weak subjects.")
    if not any(bool(value) for value in coding_profiles.values()):
        tips.append("Add at least one coding profile URL (LeetCode/GitHub) for visibility.")
    if resume_score < 55:
        tips.append("Improve resume keywords to better match target job role requirements.")
    if profile_score < 65:
        tips.append("Focus this month on attendance, coding hours, and one measurable project milestone.")

    if not tips:
        tips.append("You are on a strong track. Maintain consistency and keep updating your profile.")
    return tips[:5]


def achievement_badges(profile_bundle: Dict[str, Any], profile_score: float, resume_score: float, readiness: str) -> List[str]:
    profile = profile_bundle.get("profile")
    semester_scores = profile_bundle.get("semester_scores", [])
    skills = profile_bundle.get("skills", [])
    coding_profiles = decode_coding_profiles(profile_bundle)

    attendance = float(_profile_value(profile, 0, 0) or 0)
    backlogs = int(_profile_value(profile, 1, 0) or 0)
    coding_hours = float(_profile_value(profile, 3, 0) or 0)
    internships = int(_profile_value(profile, 5, 0) or 0)
    certifications = int(_profile_value(profile, 6, 0) or 0)
    projects = int(_profile_value(profile, 7, 0) or 0)
    semester_avg = sum(float(score) for score in semester_scores) / len(semester_scores) if semester_scores else 0.0

    badges: List[str] = []
    if profile and str(_profile_value(profile, 13, "")).strip():
        badges.append("Resume Uploaded")
    if profile and str(_profile_value(profile, 14, "")).strip():
        badges.append("Certificate Uploaded")
    if len(skills) >= 5:
        badges.append("Skill Explorer")
    if any(bool(value) for value in coding_profiles.values()):
        badges.append("Coding Presence")
    if projects >= 3:
        badges.append("Project Builder")
    if certifications >= 2:
        badges.append("Certification Sprint")
    if internships >= 1:
        badges.append("Industry Ready")
    if attendance >= 85:
        badges.append("Attendance Star")
    if semester_avg >= 8.0:
        badges.append("Academic Performer")
    if coding_hours >= 10:
        badges.append("Consistent Coder")
    if backlogs == 0:
        badges.append("No Backlog")
    if profile_score >= 75:
        badges.append("Strong Profile")
    if resume_score >= 65:
        badges.append("Resume Optimized")
    if readiness == "High":
        badges.append("High Readiness")

    return badges[:8]
