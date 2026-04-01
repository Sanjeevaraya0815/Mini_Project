import json
from typing import Any, Dict, List, Sequence


CODING_PROFILE_KEYS = ("leetcode", "hackerrank", "codechef", "github")


def _profile_value(profile, index: int, default=0):
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


def profile_health_summary(profile_bundle: Dict[str, Any]) -> Dict[str, Any]:
    profile = profile_bundle.get("profile")
    coding_profiles = decode_coding_profiles(profile_bundle)
    filled_coding_profiles = [name for name, value in coding_profiles.items() if value]
    missing_coding_profiles = [name.title() for name, value in coding_profiles.items() if not value]

    languages_known = _profile_value(profile, 9, None)
    if isinstance(languages_known, list):
        language_count = len(languages_known)
    else:
        try:
            language_count = len(json.loads(languages_known)) if languages_known else 0
        except (TypeError, json.JSONDecodeError):
            language_count = 0

    return {
        "coding_profiles": coding_profiles,
        "coding_profile_count": len(filled_coding_profiles),
        "missing_coding_profiles": missing_coding_profiles,
        "languages_known_count": language_count,
    }


def recommend_roles(profile_bundle: Dict[str, Any], role_catalog: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    profile = profile_bundle.get("profile")
    student_skills = {skill.lower() for skill in profile_bundle.get("skills", [])}

    internships = int(_profile_value(profile, 5, 0) or 0)
    certifications = int(_profile_value(profile, 6, 0) or 0)
    target_domain = str(_profile_value(profile, 8, "") or "").lower()

    scored_roles: List[Dict[str, Any]] = []
    for role in role_catalog:
        required = {skill.lower() for skill in role.get("required_skills", [])}

        skill_match = (len(student_skills & required) / len(required)) if required else 0.0

        min_internships = int(role.get("min_internships", 0) or 0)
        min_certifications = int(role.get("min_certifications", 0) or 0)
        internship_match = 1.0 if internships >= min_internships else internships / max(min_internships, 1)
        cert_match = 1.0 if certifications >= min_certifications else certifications / max(min_certifications, 1)
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

    scored_roles.sort(key=lambda item: item["Recommendation Score"], reverse=True)
    return scored_roles