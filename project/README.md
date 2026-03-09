# Student Performance and Placement Readiness Prediction System

AI-powered Streamlit application that predicts:
- **Academic Performance Score** (regression)
- **Placement Readiness**: Low / Medium / High (classification)

It combines student academic history, skills, behavioral inputs, projects, internships, and certifications.

## Tech Stack
- Frontend/UI: Streamlit
- Database: MySQL
- ML: TensorFlow/Keras (DNN + LSTM hybrid)
- Language: Python

## Project Structure
```
project/
├── app.py
├── README.md
├── pages/
│   ├── student_login.py
│   ├── student_dashboard.py
│   ├── faculty_login.py
│   ├── faculty_dashboard.py
│   ├── profile_entry.py
│   ├── resume_scanner.py
│   ├── certificate_scanner.py
│   └── job_recommendation.py
├── model/
│   ├── train_model.py
│   ├── predict.py
│   └── saved_model/
├── database/
│   ├── db_connect.py
│   └── schema.sql
├── utils/
│   ├── auth_utils.py
│   ├── preprocessing.py
│   ├── resume_parser.py
│   └── ocr_utils.py
└── requirements.txt
```

## Features Implemented
1. **Student Login & Registration** (MySQL-backed)
2. **Student Profile Entry** (all required fields + resume/certificate upload)
3. **Hybrid DNN + LSTM model training**
4. **Prediction service** (academic score + readiness)
5. **Student Dashboard** (metrics, gauges, feature impact)
6. **Faculty Login & Registration**
7. **Faculty Dashboard** (department-wise student list, risk filter, analytics)
8. **Resume Scanner** (PDF text extraction + skill extraction + role matching)
9. **Certificate Scanner** (OCR/PDF extraction + validation + certification save)
10. **Job Recommendation** (rule-based weighted matching)

---

## How to Run (Step-by-Step)

## 1) Prerequisites
- Python 3.10+ recommended
- MySQL Server running locally or remotely
- Tesseract OCR installed (for certificate image OCR)
  - Windows installer: install Tesseract and add it to PATH

## 2) Open Terminal in project folder
```powershell
cd c:\Users\Sanjeev\Downloads\Student_performance\project
```

## 3) Create and activate virtual environment (recommended)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 4) Install dependencies
```powershell
pip install -r requirements.txt
```

## 5) Configure MySQL credentials
This app reads DB credentials from environment variables. If not set, defaults are:
- DB_HOST=localhost
- DB_PORT=3306
- DB_USER=root
- DB_PASSWORD=""
- DB_NAME=student_performance

Set them in PowerShell if needed:
```powershell
$env:DB_HOST="localhost"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD="your_mysql_password"
$env:DB_NAME="student_performance"
```

## 6) Create database schema
Run SQL file `database/schema.sql` in MySQL Workbench or mysql CLI.

Using mysql CLI:
```powershell
mysql -u root -p < database/schema.sql
```

## 7) Train model
```powershell
python model/train_model.py
```
This creates artifacts in `model/saved_model/`:
- `performance_model.keras`
- `preprocessor.joblib`
- `metrics.json`

## 8) Run Streamlit app
```powershell
streamlit run app.py
```

## Optional: Seed 1000 Faker students for stronger model training
```powershell
python database/seed_faker_students.py --count 1000
```

Then retrain:
```powershell
python model/train_model.py
```

Seeded login format:
- Email: `faker_student_0001@example.com` to `faker_student_1000@example.com`
- Password: `Student@123`

You can view/download seeded credentials in the **Student Login** page under **Demo Seeded Student Logins**.

---

## Usage Flow

## Student flow
1. Open **Student Login** page
2. Register and login as student
3. Open **Profile Entry** and submit all details
4. (One-time or after significant new data) run `python model/train_model.py`
5. Open **Student Dashboard** and click **Run / Refresh Prediction**
6. Use **Resume Scanner**, **Certificate Scanner**, and **Job Recommendation** pages

## Faculty flow
1. Open **Faculty Login** page
2. Register/login as faculty (with department)
3. Open **Faculty Dashboard**
4. Filter students by risk level and view department analytics

---

## Important Notes
- If the training dataset from DB is too small, `model/train_model.py` bootstraps with synthetic data.
- For image OCR, Tesseract must be installed and discoverable in PATH.
- Resume scanner currently uses text matching over known skill vocabulary from `utils/resume_parser.py`.
- Certificate scanner uses heuristic verification from extracted text.

---

## Troubleshooting
- **MySQL connection error**: verify env vars and MySQL service status.
- **TensorFlow import not found**: ensure venv activated and `pip install -r requirements.txt` completed.
- **OCR not working**: verify Tesseract install and PATH.
- **No predictions in dashboard**: run profile entry first and train model.

---

## Future Improvements
- spaCy NER-based skill extraction
- Certificate issuer validation against trusted registry
- Cosine-similarity embeddings for job role matching
- SHAP/LIME feature attribution for explainability
- Admin panel and audit logs
