"""
Dataset generation scaffold using Groq as the teacher model.

Run:  python generate_dataset.py
Requires: GROQ_API_KEY environment variable (see .env.example)
"""

import os
import json
from scripts.teacher_model import TeacherModel

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are a talent intelligence assistant. "
    "Given a recruiter or PM question, respond with the correct tool call(s) and a final answer."
)

CATEGORIES = [
    "find_talent",
    "filter_by_skills",
    "build_team",
    "check_availability",
]

EXAMPLE_QUESTIONS = {
    "find_talent": "Find me someone with five or more years of Python and machine learning experience.",
    "filter_by_skills": "Narrow the list to senior engineers who know Kubernetes and have worked in fintech.",
    "build_team": "I need a frontend engineer, a backend engineer, and a data scientist who can work together.",
    "check_availability": "Who on the bench is available to start within two weeks?",
}


def generate_example(category: str, question: str, teacher: TeacherModel) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    raw = teacher.complete(messages)
    return {"instruction": question, "response": raw, "category": category}


def main() -> None:
    teacher = TeacherModel(os.environ["GROQ_API_KEY"], MODEL, GROQ_API_URL)

    os.makedirs("data", exist_ok=True)
    out_path = "data/dataset.jsonl"

    with open(out_path, "w") as fh:
        for category in CATEGORIES:
            question = EXAMPLE_QUESTIONS[category]
            example = generate_example(category, question, teacher)
            fh.write(json.dumps(example) + "\n")
            print(f"[{category}] done")

    print(f"Dataset written to {out_path}")


if __name__ == "__main__":
    main()
