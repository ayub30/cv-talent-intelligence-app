"""
Dataset generation scaffold using Groq as the teacher model.

Run:  python generate_dataset.py
Requires: GROQ_API_KEY environment variable (see .env.example)
"""

import os
import json

GROQ_API_KEY = os.environ["GROQ_API_KEY"]  # raises KeyError if missing

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


def call_groq(messages: list[dict]) -> str:
    import urllib.request

    payload = json.dumps({"model": MODEL, "messages": messages}).encode()
    req = urllib.request.Request(
        GROQ_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def generate_example(category: str, question: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    raw = call_groq(messages)
    return {"instruction": question, "response": raw, "category": category}


def main() -> None:
    os.makedirs("data", exist_ok=True)
    out_path = "data/dataset.jsonl"

    with open(out_path, "w") as fh:
        for category in CATEGORIES:
            question = EXAMPLE_QUESTIONS[category]
            example = generate_example(category, question)
            fh.write(json.dumps(example) + "\n")
            print(f"[{category}] done")

    print(f"Dataset written to {out_path}")


if __name__ == "__main__":
    main()
