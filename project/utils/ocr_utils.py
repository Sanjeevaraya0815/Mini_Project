from typing import Tuple

import fitz
import pytesseract
from PIL import Image


def extract_text_from_pdf(pdf_path: str) -> str:
    text = []
    with fitz.open(pdf_path) as document:
        for page in document:
            text.append(page.get_text())
    return "\n".join(text)


def extract_text_from_image(image_path: str) -> str:
    image = Image.open(image_path)
    return pytesseract.image_to_string(image)


def extract_certificate_text(file_path: str) -> Tuple[str, bool]:
    lower_path = file_path.lower()
    if lower_path.endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
        return text, True

    if lower_path.endswith((".png", ".jpg", ".jpeg")):
        text = extract_text_from_image(file_path)
        return text, True

    return "", False
