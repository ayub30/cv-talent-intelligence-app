import sqlite3
from datetime import datetime, timezone


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    reply_company TEXT NOT NULL,
    location TEXT NOT NULL,
    seniority TEXT NOT NULL CHECK(seniority IN ('junior', 'mid', 'senior', 'principal')),
    availability_status TEXT NOT NULL CHECK(availability_status IN ('available', 'on_project', 'on_bench', 'rolling_off')),
    current_project_name TEXT,
    last_updated TEXT NOT NULL,
    chroma_doc_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employee_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    skill TEXT NOT NULL,
    years_experience REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);
"""

_SEED_EMPLOYEES = [
    {
        "id": "emp_001",
        "name": "Maya Okafor",
        "reply_company": "Data Reply",
        "location": "London",
        "seniority": "principal",
        "availability_status": "on_project",
        "current_project_name": "NHS Azure Migration",
        "skills": [
            ("Azure Databricks", 4.0),
            ("Python", 7.0),
            ("Apache Spark", 5.0),
            ("RAG Pipelines", 2.0),
        ],
        "cv_text": (
            "Maya Okafor is a Principal Data Engineer at Data Reply with 8 years of experience. "
            "Led Azure Databricks migration across clinical datasets for NHS Digital. "
            "Built RAG retrieval pipelines for healthcare document search. "
            "Expert in Apache Spark, Python, and large-scale data architecture."
        ),
    },
    {
        "id": "emp_002",
        "name": "Daniel Hughes",
        "reply_company": "Cluster Reply",
        "location": "Manchester",
        "seniority": "senior",
        "availability_status": "rolling_off",
        "current_project_name": "MOD Secure Platform",
        "skills": [
            ("Azure", 6.0),
            ("Terraform", 4.0),
            ("Security Architecture", 5.0),
            ("Kubernetes", 3.0),
        ],
        "cv_text": (
            "Daniel Hughes is a Senior Cloud Architect at Cluster Reply. "
            "Designed secure Azure landing zones and Terraform modules for MOD. "
            "SC-cleared with 6 years of Azure delivery experience. "
            "Specialises in Kubernetes, IaC, and zero-trust network architecture."
        ),
    },
    {
        "id": "emp_003",
        "name": "Aisha Rahman",
        "reply_company": "Machine Learning Reply",
        "location": "London",
        "seniority": "senior",
        "availability_status": "available",
        "current_project_name": None,
        "skills": [
            ("LLM Evaluation", 3.0),
            ("RAG", 2.0),
            ("Product Management", 5.0),
            ("Python", 4.0),
        ],
        "cv_text": (
            "Aisha Rahman is an AI Product Lead at Machine Learning Reply. "
            "Led LLM evaluation frameworks and RAG governance for enterprise clients. "
            "Delivered stakeholder-facing AI assistant products end-to-end. "
            "Strong background in AI product strategy and cross-functional team leadership."
        ),
    },
    {
        "id": "emp_004",
        "name": "James Carter",
        "reply_company": "Data Reply",
        "location": "Birmingham",
        "seniority": "senior",
        "availability_status": "on_project",
        "current_project_name": "Retail Demand Forecasting",
        "skills": [
            ("Python", 6.0),
            ("Machine Learning", 5.0),
            ("Scikit-learn", 5.0),
            ("SQL", 6.0),
        ],
        "cv_text": (
            "James Carter is a Senior Data Scientist at Data Reply with 7 years of experience. "
            "Built demand forecasting models reducing inventory costs by 18% for a FTSE 100 retailer. "
            "Expert in scikit-learn, XGBoost, and production ML pipelines. "
            "Strong SQL and data engineering background."
        ),
    },
    {
        "id": "emp_005",
        "name": "Sophie Williams",
        "reply_company": "Open Reply",
        "location": "Leeds",
        "seniority": "mid",
        "availability_status": "available",
        "current_project_name": None,
        "skills": [
            ("React", 3.0),
            ("TypeScript", 3.0),
            ("Node.js", 3.0),
            ("FastAPI", 1.5),
        ],
        "cv_text": (
            "Sophie Williams is a Mid-level Full Stack Developer at Open Reply. "
            "Three years delivering React and TypeScript frontends with Node.js backends. "
            "Recent experience with FastAPI microservices and REST API design. "
            "Strong focus on accessibility, UI/UX, and component-driven development."
        ),
    },
    {
        "id": "emp_006",
        "name": "Ravi Patel",
        "reply_company": "Spike Reply",
        "location": "London",
        "seniority": "senior",
        "availability_status": "on_bench",
        "current_project_name": None,
        "skills": [
            ("Kubernetes", 5.0),
            ("CI/CD", 6.0),
            ("AWS", 4.0),
            ("Helm", 3.0),
        ],
        "cv_text": (
            "Ravi Patel is a Senior DevOps Engineer at Spike Reply. "
            "Delivered Kubernetes platform engineering for financial services clients. "
            "Expert in CI/CD pipelines, Helm charts, and AWS EKS. "
            "Six years automating release workflows at scale."
        ),
    },
    {
        "id": "emp_007",
        "name": "Elena Müller",
        "reply_company": "TechReply",
        "location": "Berlin",
        "seniority": "principal",
        "availability_status": "on_project",
        "current_project_name": "Enterprise API Gateway Redesign",
        "skills": [
            ("System Design", 10.0),
            ("Java", 8.0),
            ("Microservices", 7.0),
            ("Event-Driven Architecture", 5.0),
        ],
        "cv_text": (
            "Elena Müller is a Principal Software Architect at TechReply with 12 years of experience. "
            "Redesigned enterprise API gateway handling 200M requests per day. "
            "Deep expertise in Java microservices, event-driven architecture, and DDD. "
            "Trusted technical authority for complex systems transformation programmes."
        ),
    },
    {
        "id": "emp_008",
        "name": "Tom Bradley",
        "reply_company": "Retail Reply",
        "location": "Bristol",
        "seniority": "junior",
        "availability_status": "available",
        "current_project_name": None,
        "skills": [
            ("SQL", 1.5),
            ("Python", 1.0),
            ("Power BI", 1.5),
            ("Excel", 2.0),
        ],
        "cv_text": (
            "Tom Bradley is a Junior Data Analyst at Retail Reply with 2 years of experience. "
            "Built Power BI dashboards for retail performance reporting. "
            "Comfortable with SQL queries, Python data wrangling, and Excel modelling. "
            "Eager to grow into data engineering and ML workflows."
        ),
    },
    {
        "id": "emp_009",
        "name": "Priya Nair",
        "reply_company": "Machine Learning Reply",
        "location": "London",
        "seniority": "senior",
        "availability_status": "rolling_off",
        "current_project_name": "Financial Fraud Detection",
        "skills": [
            ("PyTorch", 4.0),
            ("MLOps", 3.0),
            ("Python", 5.0),
            ("Feature Engineering", 4.0),
        ],
        "cv_text": (
            "Priya Nair is a Senior ML Engineer at Machine Learning Reply. "
            "Built fraud detection models in production using PyTorch and feature stores. "
            "Owns MLOps pipelines from experimentation to deployment on GCP. "
            "Five years of end-to-end ML delivery in regulated industries."
        ),
    },
    {
        "id": "emp_010",
        "name": "Carlos Santos",
        "reply_company": "Blue Reply",
        "location": "Madrid",
        "seniority": "mid",
        "availability_status": "on_project",
        "current_project_name": "Insurance Microservices Platform",
        "skills": [
            ("Python", 3.0),
            ("FastAPI", 2.0),
            ("PostgreSQL", 3.0),
            ("Docker", 3.0),
        ],
        "cv_text": (
            "Carlos Santos is a Mid-level Backend Developer at Blue Reply. "
            "Three years building FastAPI microservices for insurance platform clients. "
            "Expert in PostgreSQL schema design, Docker containerisation, and REST APIs. "
            "Collaborative team player with a strong focus on clean code and testing."
        ),
    },
]


def make_connection(db_path: str = "talent.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def seed_db(conn: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for emp in _SEED_EMPLOYEES:
        existing = conn.execute(
            "SELECT id FROM employees WHERE id = ?", (emp["id"],)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """INSERT INTO employees
               (id, name, reply_company, location, seniority, availability_status,
                current_project_name, last_updated, chroma_doc_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                emp["id"],
                emp["name"],
                emp["reply_company"],
                emp["location"],
                emp["seniority"],
                emp["availability_status"],
                emp["current_project_name"],
                now,
                emp["id"],
            ),
        )
        conn.executemany(
            "INSERT INTO employee_skills (employee_id, skill, years_experience) VALUES (?, ?, ?)",
            [(emp["id"], skill, years) for skill, years in emp["skills"]],
        )
    conn.commit()


def get_seed_employees() -> list[dict]:
    return _SEED_EMPLOYEES
