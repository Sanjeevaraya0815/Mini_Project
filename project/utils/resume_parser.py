from typing import List

import fitz


KNOWN_SKILLS = {
    "python",
    "java",
    "c++",
    "sql",
    "machine learning",
    "deep learning",
    "tensorflow",
    "pandas",
    "numpy",
    "docker",
    "aws",
    "git",
    "data structures",
    "algorithms",
}


def extract_text_from_pdf(pdf_path: str) -> str:
    text = []
    with fitz.open(pdf_path) as document:
        for page in document:
            text.append(page.get_text())
    return "\n".join(text)


def extract_skills_from_text(text: str) -> List[str]:
    lowered = text.lower()
    skills = [skill for skill in KNOWN_SKILLS if skill in lowered]
    return sorted(list(set(skills)))


def parse_resume_skills(pdf_path: str) -> List[str]:
    text = extract_text_from_pdf(pdf_path)
    return extract_skills_from_text(text)
