CREATE DATABASE IF NOT EXISTS student_performance;
USE student_performance;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    roll_number VARCHAR(30),
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'faculty') NOT NULL DEFAULT 'student',
    year_of_study TINYINT,
    department VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    attendance_pct DECIMAL(5,2) DEFAULT 0,
    backlogs_count INT DEFAULT 0,
    dsa_language VARCHAR(50),
    coding_hours_per_week DECIMAL(6,2) DEFAULT 0,
    coding_profiles JSON,
    internships_count INT DEFAULT 0,
    certifications_count INT DEFAULT 0,
    projects_completed INT DEFAULT 0,
    target_career_domain VARCHAR(120),
    languages_known JSON,
    communication_rating TINYINT,
    stress_level TINYINT,
    motivation_level TINYINT,
    resume_path VARCHAR(255),
    certificate_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_student_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS semester_scores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    semester_no TINYINT NOT NULL,
    score DECIMAL(5,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_semester (user_id, semester_no),
    CONSTRAINT fk_semester_scores_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    skill_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_skill (user_id, skill_name),
    CONSTRAINT fk_skills_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS certifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    cert_name VARCHAR(150) NOT NULL,
    issuer VARCHAR(150),
    verified TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_certifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS internships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    company_name VARCHAR(150),
    duration_months DECIMAL(4,1),
    domain VARCHAR(120),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_internships_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    academic_score DECIMAL(6,2) NOT NULL,
    placement_readiness ENUM('Low', 'Medium', 'High') NOT NULL,
    model_version VARCHAR(50) DEFAULT 'v1',
    feature_importance JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_predictions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(120) NOT NULL UNIQUE,
    required_skills JSON,
    min_internships INT DEFAULT 0,
    min_certifications INT DEFAULT 0,
    target_domain VARCHAR(120),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT IGNORE INTO job_roles (role_name, required_skills, min_internships, min_certifications, target_domain)
VALUES
('Software Engineer', JSON_ARRAY('Python', 'DSA', 'SQL', 'Git'), 1, 1, 'Software Development'),
('Data Analyst', JSON_ARRAY('Python', 'SQL', 'Excel', 'Statistics'), 0, 1, 'Data Analytics'),
('Data Scientist', JSON_ARRAY('Python', 'Machine Learning', 'Statistics', 'Pandas'), 1, 2, 'Data Science'),
('Cloud Engineer', JSON_ARRAY('Linux', 'Networking', 'AWS', 'Docker'), 1, 1, 'Cloud Computing'),
('QA Engineer', JSON_ARRAY('Testing', 'Selenium', 'API Testing', 'SQL'), 0, 0, 'Quality Assurance');
