import re
import uuid
from pathlib import Path

try:
    from pypdf import PdfReader
    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False

_SENIORITY_KEYWORDS = {
    "principal": ["principal", "chief", "head of", "vp ", "vice president", "director"],
    "senior": ["senior", "sr.", "lead ", "staff "],
    "junior": ["junior", "jr.", "graduate", "intern", "entry-level"],
}

_KNOWN_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "React", "Node.js", "FastAPI",
    "Azure", "AWS", "GCP", "Kubernetes", "Docker", "Terraform", "CI/CD", "Helm",
    "Machine Learning", "Deep Learning", "PyTorch", "TensorFlow", "Scikit-learn",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis",
    "Apache Spark", "Databricks", "Kafka", "MLOps", "RAG", "LLM", "NLP",
    "Microservices", "System Design", "Power BI", "Excel",
    "Event-Driven Architecture", "Security Architecture", "Feature Engineering",
]

_CITIES = [
    "London", "Manchester", "Birmingham", "Leeds", "Bristol", "Edinburgh",
    "Berlin", "Madrid", "Milan", "Paris", "Amsterdam",
]


def extract_text_from_pdf(pdf_path: str) -> str:
    """Return text from all PDF pages, or empty string on any failure."""
    if not _HAS_PYPDF:
        return ""
    try:
        reader = PdfReader(pdf_path)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except Exception:
        return ""


def parse_cv_fields(cv_text: str, filename: str = "cv.pdf") -> dict:
    """Extract structured employee fields from raw CV text using keyword heuristics."""
    text_lower = cv_text.lower()
    lines = [line.strip() for line in cv_text.split("\n") if line.strip()]

    name = lines[0][:80] if lines else Path(filename).stem.replace("_", " ").title()

    seniority = "mid"
    for level, keywords in _SENIORITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            seniority = level
            break

    location = "Unknown"
    for city in _CITIES:
        if city.lower() in text_lower:
            location = city
            break

    skills = []
    years_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years?|yrs?)")
    for skill in _KNOWN_SKILLS:
        if skill.lower() in text_lower:
            idx = text_lower.find(skill.lower())
            context = text_lower[max(0, idx - 50) : idx + 100]
            match = years_pattern.search(context)
            years = float(match.group(1)) if match else 1.0
            skills.append({"skill": skill, "years_experience": years})

    if not skills:
        skills = [{"skill": "General IT", "years_experience": 1.0}]

    return {
        "name": name,
        "reply_company": "Reply Group",
        "location": location,
        "seniority": seniority,
        "availability_status": "available",
        "current_project_name": None,
        "skills": skills,
    }


def generate_employee_id() -> str:
    return f"emp_{uuid.uuid4().hex[:8]}"
