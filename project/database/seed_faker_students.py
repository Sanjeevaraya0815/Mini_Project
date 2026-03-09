import argparse
import json
import random
import sys
from pathlib import Path

from faker import Faker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db_connect import get_connection
from utils.auth_utils import hash_password


DEPARTMENTS = [
    "CSE",
    "IT",
    "ECE",
    "EEE",
    "Mechanical",
    "Civil",
    "AI&DS",
]

DSA_LANGUAGES = ["Python", "Java", "C++", "C", "JavaScript"]

CAREER_DOMAINS = [
    "Software Development",
    "Data Science",
    "Data Analytics",
    "Cloud Computing",
    "Cyber Security",
    "Quality Assurance",
    "Product Management",
]

SKILL_POOL = [
    "Python",
    "Java",
    "C++",
    "SQL",
    "Machine Learning",
    "Deep Learning",
    "Data Structures",
    "Algorithms",
    "Web Development",
    "Cloud",
    "Docker",
    "Git",
    "AWS",
    "Pandas",
    "NumPy",
    "Power BI",
    "Linux",
]

DEFAULT_PASSWORD = "Student@123"


def _generate_student_record(fake: Faker, idx: int):
    year = random.randint(1, 4)
    department = random.choice(DEPARTMENTS)
    ability = random.random()

    attendance_pct = round(max(55, min(99, random.gauss(65 + ability * 30, 6))), 2)
    backlogs_count = max(0, int(round(random.gauss((1.6 - ability) * 3.5, 1.5))))

    coding_hours_per_week = round(max(1, min(35, random.gauss(4 + ability * 20, 4))), 2)
    internships_count = max(0, min(4, int(round(random.gauss(ability * 2.5, 0.8)))))
    certifications_count = max(0, min(8, int(round(random.gauss(ability * 4, 1.2)))))
    projects_completed = max(0, min(10, int(round(random.gauss(ability * 6, 1.8)))))

    communication_rating = max(1, min(10, int(round(random.gauss(4 + ability * 5, 1.2)))))
    stress_level = max(1, min(10, int(round(random.gauss(7 - ability * 4, 1.4)))))
    motivation_level = max(1, min(10, int(round(random.gauss(4 + ability * 5, 1.2)))))

    base_sem = max(5.0, min(9.7, random.gauss(5.6 + ability * 3.0, 0.35)))
    semester_scores = []
    for sem in range(1, 9):
        trend = (sem - 1) * random.uniform(0.0, 0.06)
        score = max(4.8, min(9.9, base_sem + trend + random.uniform(-0.25, 0.25)))
        semester_scores.append(round(score, 2))

    skills_count = max(3, min(12, int(round(3 + ability * 9 + random.uniform(-1, 1)))))
    selected_skills = random.sample(SKILL_POOL, k=min(skills_count, len(SKILL_POOL)))

    primary_domain = random.choice(CAREER_DOMAINS)
    dsa_language = random.choice(DSA_LANGUAGES)

    name = fake.name()
    email = f"faker_student_{idx:04d}@example.com"
    roll_number = f"FAK{year}{idx:05d}"

    coding_profiles = {
        "leetcode": f"https://leetcode.com/u/faker{idx}",
        "hackerrank": f"https://www.hackerrank.com/faker{idx}",
        "codechef": f"https://www.codechef.com/users/faker{idx}",
        "github": f"https://github.com/faker-student-{idx}",
    }

    languages_known = ["English"]
    if random.random() < 0.7:
        languages_known.append(random.choice(["Hindi", "Tamil", "Telugu", "Kannada", "Malayalam"]))

    return {
        "name": name,
        "roll_number": roll_number,
        "email": email,
        "year": year,
        "department": department,
        "dsa_language": dsa_language,
        "attendance_pct": attendance_pct,
        "backlogs_count": backlogs_count,
        "coding_hours_per_week": coding_hours_per_week,
        "internships_count": internships_count,
        "certifications_count": certifications_count,
        "projects_completed": projects_completed,
        "target_career_domain": primary_domain,
        "communication_rating": communication_rating,
        "stress_level": stress_level,
        "motivation_level": motivation_level,
        "coding_profiles": json.dumps(coding_profiles),
        "languages_known": json.dumps(languages_known),
        "semester_scores": semester_scores,
        "skills": selected_skills,
    }


def seed_students(count: int = 1000, start_index: int = 1, default_password: str = DEFAULT_PASSWORD):
    fake = Faker("en_IN")
    hashed_password = hash_password(default_password)

    inserted = 0
    skipped = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        for i in range(start_index, start_index + count):
            payload = _generate_student_record(fake, i)

            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (payload["email"],),
            )
            existing = cursor.fetchone()
            if existing:
                skipped += 1
                continue

            cursor.execute(
                """
                INSERT INTO users (name, roll_number, email, password_hash, role, year_of_study, department)
                VALUES (%s, %s, %s, %s, 'student', %s, %s)
                """,
                (
                    payload["name"],
                    payload["roll_number"],
                    payload["email"],
                    hashed_password,
                    payload["year"],
                    payload["department"],
                ),
            )
            user_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO student_profiles (
                    user_id, attendance_pct, backlogs_count, dsa_language, coding_hours_per_week,
                    coding_profiles, internships_count, certifications_count, projects_completed,
                    target_career_domain, languages_known, communication_rating, stress_level,
                    motivation_level, resume_path, certificate_path
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
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
                    "",
                    "",
                ),
            )

            sem_values = [
                (user_id, sem_no + 1, payload["semester_scores"][sem_no])
                for sem_no in range(8)
            ]
            cursor.executemany(
                "INSERT INTO semester_scores (user_id, semester_no, score) VALUES (%s, %s, %s)",
                sem_values,
            )

            skill_values = [(user_id, skill) for skill in payload["skills"]]
            cursor.executemany(
                "INSERT INTO skills (user_id, skill_name) VALUES (%s, %s)",
                skill_values,
            )

            inserted += 1
            if inserted % 100 == 0:
                conn.commit()
                print(f"Inserted {inserted} students...")

        conn.commit()
        cursor.close()

    print("Seeding complete")
    print(f"Inserted: {inserted}")
    print(f"Skipped (already exists): {skipped}")
    print(f"Default login password for seeded accounts: {default_password}")
    print("Sample email format: faker_student_0001@example.com")


def main():
    parser = argparse.ArgumentParser(description="Seed fake students into MySQL for model training.")
    parser.add_argument("--count", type=int, default=1000, help="Number of students to seed")
    parser.add_argument("--start-index", type=int, default=1, help="Start index for generated email IDs")
    parser.add_argument(
        "--password",
        type=str,
        default=DEFAULT_PASSWORD,
        help="Common password for all seeded student accounts",
    )
    args = parser.parse_args()

    seed_students(count=args.count, start_index=args.start_index, default_password=args.password)


if __name__ == "__main__":
    main()
