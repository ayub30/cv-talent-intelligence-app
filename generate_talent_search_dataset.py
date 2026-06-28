"""
Generate ~600 training examples for the talent-search LoRA fine-tune.
Teacher model: Groq Llama 3.3 70B Versatile

Categories and target counts:
  find_talent        200
  filter_by_skills   150
  build_team         150
  check_availability 100

Each example: { instruction, response: { tool_calls, answer }, category }

Usage:
  python generate_talent_search_dataset.py
  python generate_talent_search_dataset.py --output data/talent_search_dataset.jsonl
  python generate_talent_search_dataset.py --dry-run   # smoke test, no API calls

Requires: GROQ_API_KEY env var
"""

import argparse
import json
import os
import random
import sys
import time
from typing import Any

from scripts.teacher_model import TeacherModel

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

CATEGORY_COUNTS: dict[str, int] = {
    "find_talent": 200,
    "filter_by_skills": 150,
    "build_team": 150,
    "check_availability": 100,
}

TOOL_DEFS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_cvs",
            "description": (
                "Semantic search across employee CVs. "
                "Use when the PM describes a role, skills, or experience in natural language."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language description of the desired candidate profile",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_candidates",
            "description": (
                "Structured SQL-style query against the employee database. "
                "Use when the PM specifies concrete filter criteria: a specific skill, "
                "minimum years of experience, seniority level, availability status, "
                "company division, or office location."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Key/value filters to apply",
                        "properties": {
                            "skill": {
                                "type": "string",
                                "description": "Skill name to filter by",
                            },
                            "min_years": {
                                "type": "integer",
                                "description": "Minimum years of experience for the given skill",
                            },
                            "seniority": {
                                "type": "string",
                                "enum": ["junior", "mid", "senior", "lead", "principal"],
                                "description": "Seniority level filter",
                            },
                            "availability": {
                                "type": "string",
                                "enum": ["available", "busy", "rolling_off"],
                                "description": "Availability status filter",
                            },
                            "company": {
                                "type": "string",
                                "description": "Reply company division name",
                            },
                            "location": {
                                "type": "string",
                                "description": "Office location",
                            },
                        },
                    }
                },
                "required": ["filters"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_profile_cv",
            "description": (
                "Fetch the full CV text for a specific employee by their ID. "
                "Use after search_cvs or query_candidates to get more detail on a candidate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "Unique employee ID returned by search_cvs or query_candidates",
                    }
                },
                "required": ["employee_id"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are a talent intelligence assistant helping programme managers find the right consultants. "
    "When a PM asks a question, use the available tools to search for matching candidates, "
    "then give a concise 2-3 sentence answer summarising the best options found."
)

SEED_QUESTIONS: dict[str, list[str]] = {
    "find_talent": [
        "Find me someone with 5+ years of Python and machine learning experience.",
        "Who has deep expertise in cloud architecture on AWS?",
        "I need a consultant with experience in NLP and large language models.",
        "Find candidates with a background in financial risk modelling.",
        "Who has worked on digital transformation projects in healthcare?",
        "I'm looking for someone with React and TypeScript experience.",
        "Find me a data engineer with experience in Apache Spark and Kafka.",
        "Who has done DevOps work with Kubernetes and Terraform?",
        "I need someone with a background in cybersecurity and penetration testing.",
        "Find candidates with experience in SAP ERP implementations.",
        "Who has worked as a Scrum Master or Agile coach?",
        "I need a consultant with insurance industry domain knowledge.",
        "Find someone with expertise in graph databases like Neo4j.",
        "Who has experience building recommendation systems?",
        "I need a technical architect with microservices expertise.",
        "Find candidates with strong SQL and data warehousing skills.",
        "Who has worked on mobile app development for iOS and Android?",
        "I need someone with experience in regulatory compliance, specifically GDPR.",
        "Find a consultant with blockchain or Web3 development experience.",
        "Who has deep knowledge of machine learning operations (MLOps)?",
    ],
    "filter_by_skills": [
        "Narrow the list to senior engineers who know Kubernetes.",
        "Filter to mid-level developers with at least 3 years of Java experience.",
        "Show me only lead consultants who have fintech domain knowledge.",
        "Filter by seniority: I only want senior or above with Python skills.",
        "Narrow down to people with 5+ years in cloud and principal-level experience.",
        "Filter the results to consultants in the London office with DevOps skills.",
        "Show only available candidates who know React and have 2+ years experience.",
        "Narrow to senior architects with microservices and Docker experience.",
        "Filter to consultants with machine learning skills at the senior level.",
        "Show candidates with Salesforce experience at lead or above seniority.",
        "Filter to mid-level analysts with SQL and 3+ years experience.",
        "Narrow the list to data scientists who know Python and R.",
        "Show only available consultants with Agile/Scrum expertise.",
        "Filter to senior consultants specializing in digital transformation.",
        "Narrow results to consultants with cybersecurity at senior or lead level.",
        "Filter by skill: I need Java developers with Spring Boot experience.",
        "Show me only junior engineers in the Manchester office.",
        "Narrow to consultants with both frontend and backend full-stack skills.",
        "Filter to available senior consultants with Azure cloud expertise.",
        "Show mid-level consultants with at least 2 years of Terraform experience.",
    ],
    "build_team": [
        "I need a frontend engineer, a backend engineer, and a data scientist to form a project team.",
        "Build me a team for a mobile app project: iOS developer, backend API developer, and UX designer.",
        "I need a cloud architect, a DevOps engineer, and a security specialist.",
        "Assemble a data platform team: data engineer, ML engineer, and data analyst.",
        "I need a full-stack developer, a business analyst, and a project manager.",
        "Build a team for an AI product: ML researcher, backend engineer, and product manager.",
        "I need three senior engineers with complementary skills for a greenfield project.",
        "Assemble a team for digital transformation: change manager, solutions architect, and developer.",
        "I need a frontend specialist, a backend specialist, and a QA engineer.",
        "Build me a team for a data migration project: DBA, ETL developer, and data analyst.",
        "I need a team for a cybersecurity audit: penetration tester, security architect, and compliance analyst.",
        "Assemble a fintech team: financial domain expert, backend developer, and DevSecOps engineer.",
        "I need a team of three complementary consultants for a six-month engagement.",
        "Build a cloud migration team: cloud architect, application developer, and project manager.",
        "I need a Scrum team: product owner, tech lead, and two developers.",
        "Assemble a team for an API integration project: integration architect and two developers.",
        "I need a data science team: data scientist, data engineer, and ML ops engineer.",
        "Build a team for a SAP implementation: SAP consultant, change manager, and developer.",
        "I need a balanced team: junior developer mentored by a senior, plus a tech lead.",
        "Assemble a cross-functional team for an e-commerce platform rebuild.",
    ],
    "check_availability": [
        "Who on the bench is available to start within two weeks?",
        "Which consultants are rolling off projects in the next month?",
        "Show me everyone who is currently available.",
        "Who is free to take on a new engagement starting Monday?",
        "Which senior engineers are available right now?",
        "Show me available consultants in the London area.",
        "Who is on the bench and has Python skills?",
        "Which lead consultants are available immediately?",
        "Show me data scientists who are currently free.",
        "Who is available to start a short-term contract next week?",
        "Which project managers are on the bench right now?",
        "Show me all available junior developers.",
        "Who among the senior architects is currently unengaged?",
        "Which consultants have availability starting in the next two weeks?",
        "Show me everyone who is free, sorted by seniority.",
        "Who is available and has experience in machine learning?",
        "Which DevOps engineers are currently on the bench?",
        "Show available mid-level consultants in Manchester.",
        "Who is rolling off their current project soon?",
        "Which consultants are free for an immediate start?",
    ],
}

_FAKE_NAMES = [
    "Alice Chen", "Bob Smith", "Carol White", "David Brown", "Emma Johnson",
    "Frank Davis", "Grace Lee", "Henry Wilson", "Iris Taylor", "James Anderson",
    "Karen Martinez", "Leo Thompson", "Mia Garcia", "Noah Jackson", "Olivia Harris",
    "Paul Robinson", "Quinn Clark", "Rachel Lewis", "Sam Walker", "Tara Hall",
    "Uma Young", "Victor Allen", "Wendy King", "Xavier Wright", "Yara Scott",
    "Zach Adams", "Amy Nelson", "Brian Carter", "Clara Mitchell", "Derek Perez",
]

_FAKE_SKILLS = [
    "Python", "Java", "TypeScript", "React", "Kubernetes", "AWS", "Azure",
    "Machine Learning", "Data Engineering", "DevOps", "Terraform", "Docker",
    "SQL", "MongoDB", "PostgreSQL", "Spark", "Kafka", "MLOps", "NLP",
    "Cybersecurity", "SAP", "Salesforce", "Agile", "Scrum", "GraphQL",
]

_SENIORITY = ["junior", "mid", "senior", "lead", "principal"]
_AVAILABILITY = ["available", "busy", "rolling_off"]
_DIVISIONS = ["Reply Digital", "Reply Data", "Reply Cloud", "Reply Cyber", "Reply AI"]


class _DryRunTeacher:
    """No-op teacher for --dry-run mode: returns deterministic fake completions."""

    def complete(self, messages: list[dict]) -> str:
        return "[dry-run] Matching candidates found."

    def call(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_retries: int = 4,
    ) -> dict:
        if tools:
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": "dry_00",
                        "type": "function",
                        "function": {
                            "name": "search_cvs",
                            "arguments": '{"query": "dry-run candidate", "n_results": 5}',
                        },
                    }
                ],
            }
        return {"content": "[dry-run] Matching candidates found.", "tool_calls": []}


def _simulate_tool_result(tool_name: str, args: dict[str, Any]) -> str:
    rng = random.Random(hash(json.dumps(args, sort_keys=True)) & 0xFFFFFFFF)

    if tool_name == "search_cvs":
        n = min(args.get("n_results", 5), 5)
        names = rng.sample(_FAKE_NAMES, min(n, len(_FAKE_NAMES)))
        results = []
        for name in names:
            skills = rng.sample(_FAKE_SKILLS, 3)
            results.append({
                "employee_id": f"emp_{abs(hash(name)) % 10000:04d}",
                "name": name,
                "score": rng.randint(65, 95),
                "cv_text": (
                    f"{name}: {', '.join(skills)} with "
                    f"{rng.randint(3, 12)} years experience."
                ),
            })
        return json.dumps(results)

    if tool_name == "query_candidates":
        filters = args.get("filters", {})
        names = rng.sample(_FAKE_NAMES, rng.randint(3, 7))
        results = []
        for name in names:
            results.append({
                "employee_id": f"emp_{abs(hash(name)) % 10000:04d}",
                "name": name,
                "seniority": filters.get("seniority", rng.choice(_SENIORITY)),
                "availability": filters.get("availability", rng.choice(_AVAILABILITY)),
                "company": rng.choice(_DIVISIONS),
            })
        return json.dumps(results)

    if tool_name == "get_profile_cv":
        name = rng.choice(_FAKE_NAMES)
        skills = rng.sample(_FAKE_SKILLS, 5)
        return json.dumps({
            "employee_id": args.get("employee_id", "emp_0001"),
            "name": name,
            "cv": (
                f"{name} is a {rng.choice(_SENIORITY)}-level consultant with "
                f"{rng.randint(4, 15)} years experience. "
                f"Core skills: {', '.join(skills)}. "
                "Recent projects include cloud migration, data platform build, "
                "and digital transformation engagements."
            ),
        })

    return json.dumps({"error": "unknown tool"})


def _parse_tool_calls(raw: list[dict]) -> list[dict]:
    result = []
    for tc in raw:
        if tc.get("type") == "function":
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                args = {}
            result.append({"name": tc["function"]["name"], "args": args})
    return result


def _generate_questions_batch(category: str, n: int, teacher) -> list[str]:
    desc = {
        "find_talent": "open-ended talent discovery by skills, domain, or experience",
        "filter_by_skills": "narrowing a list by specific criteria: skill, seniority, years, location, availability",
        "build_team": "assembling a complete team with complementary roles",
        "check_availability": "checking who is available, on the bench, or rolling off a project",
    }
    prompt = (
        f"Generate {n} diverse, realistic programme manager questions for the '{category}' "
        f"category ({desc[category]}). "
        "Vary: technology stacks, seniority levels, domains, and phrasing. "
        "Return ONLY a JSON array of strings. No other text."
    )
    content = teacher.complete([
        {
            "role": "system",
            "content": "You generate training data for a talent intelligence system. Output valid JSON only.",
        },
        {"role": "user", "content": prompt},
    ]).strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    try:
        questions = json.loads(content)
        if isinstance(questions, list):
            return [str(q) for q in questions if q][:n]
    except json.JSONDecodeError:
        pass
    return []


def _build_question_pool(category: str, target: int, delay: float, teacher) -> list[str]:
    pool = SEED_QUESTIONS[category][:]
    if len(pool) >= target:
        random.shuffle(pool)
        return pool[:target]

    needed = target - len(pool)
    print(f"  Generating {needed} extra questions for '{category}'...", file=sys.stderr)
    batch_size = 20
    while len(pool) - len(SEED_QUESTIONS[category]) < needed:
        remaining = needed - (len(pool) - len(SEED_QUESTIONS[category]))
        n = min(batch_size, remaining)
        batch = _generate_questions_batch(category, n, teacher)
        pool.extend(batch)
        if not batch:
            print(f"  Warning: question generation returned empty batch", file=sys.stderr)
            break
        time.sleep(delay)

    random.shuffle(pool)
    return pool[:target]


def _generate_example(category: str, question: str, teacher) -> dict | None:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    try:
        msg1 = teacher.call(messages, tools=TOOL_DEFS)
    except Exception as exc:
        print(f"  [error] tool call failed: {exc}", file=sys.stderr)
        return None

    raw_tool_calls: list[dict] = msg1.get("tool_calls") or []
    tool_calls = _parse_tool_calls(raw_tool_calls)

    if not tool_calls:
        return None

    messages.append({
        "role": "assistant",
        "content": msg1.get("content"),
        "tool_calls": raw_tool_calls,
    })
    for raw_tc, tc in zip(raw_tool_calls, tool_calls):
        messages.append({
            "role": "tool",
            "tool_call_id": raw_tc["id"],
            "content": _simulate_tool_result(tc["name"], tc["args"]),
        })

    try:
        answer = teacher.complete(messages).strip()
    except Exception as exc:
        print(f"  [error] answer call failed: {exc}", file=sys.stderr)
        return None

    if not answer:
        return None

    return {
        "instruction": question,
        "response": {"tool_calls": tool_calls, "answer": answer},
        "category": category,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate talent-search fine-tune dataset")
    parser.add_argument(
        "--output", default="data/talent_search_dataset.jsonl",
        help="Output JSONL file path (default: data/talent_search_dataset.jsonl)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Seconds to sleep between API calls (default: 0.5)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate a tiny sample using stub results (no API calls)",
    )
    args_ns = parser.parse_args()

    out_dir = os.path.dirname(args_ns.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if args_ns.dry_run:
        teacher: TeacherModel | _DryRunTeacher = _DryRunTeacher()
    else:
        teacher = TeacherModel(os.environ["GROQ_API_KEY"], MODEL, GROQ_API_URL)

    total_target = sum(CATEGORY_COUNTS.values())
    print(f"Target: {total_target} examples → {args_ns.output}")
    if args_ns.dry_run:
        print("DRY-RUN mode: using stub results, no API calls made.")

    examples: list[dict] = []

    for category, target in CATEGORY_COUNTS.items():
        dry_target = 2 if args_ns.dry_run else target
        print(f"\n[{category}] target={dry_target}", flush=True)

        questions = _build_question_pool(category, dry_target, args_ns.delay, teacher)

        category_examples: list[dict] = []
        q_idx = 0
        skips = 0
        max_skips = max(1, dry_target // 2)

        while len(category_examples) < dry_target:
            if q_idx >= len(questions):
                print(
                    f"  Warning: ran out of questions after {len(category_examples)}/{dry_target}",
                    file=sys.stderr,
                )
                break

            q = questions[q_idx]
            q_idx += 1
            n = len(category_examples) + 1
            print(f"  [{n}/{dry_target}] {q[:72]}{'...' if len(q) > 72 else ''}", flush=True)

            example = _generate_example(category, q, teacher)
            if example:
                category_examples.append(example)
            else:
                skips += 1
                if skips >= max_skips:
                    print(
                        f"  Warning: {skips} skips — stopping early for '{category}'",
                        file=sys.stderr,
                    )
                    break

            time.sleep(args_ns.delay)

        print(f"  done: {len(category_examples)} generated, {skips} skipped")
        examples.extend(category_examples)

    random.shuffle(examples)

    with open(args_ns.output, "w") as fh:
        for ex in examples:
            fh.write(json.dumps(ex) + "\n")

    from collections import Counter
    counts = Counter(ex["category"] for ex in examples)
    print(f"\nWrote {len(examples)} examples to {args_ns.output}")
    for cat, cnt in sorted(counts.items()):
        print(f"  {cat}: {cnt}")


if __name__ == "__main__":
    main()
