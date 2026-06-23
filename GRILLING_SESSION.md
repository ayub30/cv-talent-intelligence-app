# TalentGraph — Grilling Session Doc
**Date:** 2026-06-22

---

## What It Is

An internal tool for **Reply group** — project managers and practice leads can search all Reply employee CVs across every group company to find the right person for a new project.

The existing internal comms platform is **TamTam**. TalentGraph is the intelligence layer that sits alongside it, not a replacement.

---

## Users

| Role | Count | Access |
|---|---|---|
| Project managers | ~50–100 | Full search, profiles, shortlist, AI match |
| Practice leads | ~50–100 | Full search, profiles, shortlist, AI match |
| Admins | Small team | All of the above + CV upload + profile editing |

**Not** 15,000 employees. This is a PM-facing tool. Employees do not log in — admins manage their profiles on their behalf (v1).

---

## Authentication

- **Now:** Username + password. Roles stored per user in SQLite.
- **Later:** Azure AD SSO (Reply already has Microsoft 365 company-wide).
- Auth sits behind a middleware layer so the SSO swap is a single change.

### Roles
Same interface for everyone. Roles exist in the DB for audit trail and future scoping only — no UI differences in v1.

---

## Data Layer

### SQLite — Structured fields

**`employees` table**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | |
| reply_company | TEXT | Which Reply subsidiary |
| location | TEXT | |
| seniority | TEXT | junior / mid / senior / principal |
| availability_status | TEXT | available / on_project / on_bench |
| current_project_name | TEXT | Nullable |
| last_updated | DATETIME | Warning badge if >6 months old |
| chroma_doc_id | TEXT | Link to full CV chunk in Chroma |

**`employee_skills` table**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| employee_id | INTEGER FK | → employees.id |
| skill | TEXT | e.g. "Azure", "Python", "RAG" |
| years_experience | INTEGER | Enables `WHERE skill='Azure' AND years >= 3` |

**`users` table** (for auth)

| Column | Type |
|---|---|
| id | INTEGER PK |
| email | TEXT UNIQUE |
| password_hash | TEXT |
| role | TEXT |
| created_at | DATETIME |

### ChromaDB — Semantic search

- One collection: `employee_cvs`
- One document per employee — **full CV as a single chunk** (not split)
- Metadata: `employee_id`, `reply_company`, `seniority`
- Local instance, no hosted Chroma needed at this scale (10–15k docs max)

---

## CV Ingestion Pipeline

### Trigger
Admin uploads a PDF via the admin panel in the app. No email automation in v1 — too risky for silent failures. Email-triggered ingestion is a v2 feature.

### Pipeline steps
```
Admin uploads PDF
      ↓
Unstructured.io  →  clean raw text
      ↓
Llama 3.2 3B (local, MLX) + extraction prompt  →  structured JSON
      ↓
Write structured fields  →  SQLite (employees + employee_skills)
      ↓
Embed full CV text  →  ChromaDB
```

### Extraction JSON schema (target output from Llama)
```json
{
  "name": "string",
  "reply_company": "string",
  "location": "string",
  "seniority": "junior | mid | senior | principal",
  "availability_status": "available | on_project | on_bench",
  "current_project_name": "string | null",
  "skills": [
    { "skill": "Azure", "years_experience": 4 },
    { "skill": "Python", "years_experience": 6 }
  ]
}
```

### CV updates
Two paths:
1. Admin re-uploads a new PDF → pipeline re-runs → replaces old SQLite row + Chroma chunk
2. Admin edits individual profile fields directly in the app (append/update without re-parsing)

---

## Agentic Loop

### 3 Tools — no more, no less

| Tool | Signature | What it does |
|---|---|---|
| `search_cvs` | `(query: str, filters: dict)` | Semantic search against ChromaDB |
| `query_candidates` | `(sql_filter: str)` | Structured filter against SQLite employees + skills |
| `get_profile` | `(employee_id: int)` | Fetch full CV chunk from Chroma by ID |

### Flow
```
PM asks: "Find me two Azure architects with SC clearance available now"
      ↓
Agent decides: call query_candidates(seniority=senior, skill=Azure, availability=available)
      ↓
Agent decides: call search_cvs("Azure architect SC clearance")
      ↓
Agent merges results, calls get_profile() for top candidates
      ↓
Returns: ranked answer + structured matches list
```

---

## LLM — Local Llama 3.2 3B (MLX)

### Model location
```
/Users/ayubmacalim/lora-finetune/models/llama-3.2-3B-instruct-mlx
```

### Existing LoRA adapters
| Adapter | Trained for | Usable for TalentGraph? |
|---|---|---|
| `adapters_cv/` | CV advice to individuals (how long CV, improve bullet, etc.) | No — different task |
| `adapters_v2/` | Unknown variant | No |
| `adapters/` | Invoice tool-calling | No — wrong domain |

### What we need: new `adapters_talent_search/`

Train fresh LoRA adapters for the **tool-calling** use case only.

---

## Fine-Tuning Plan

### Teacher model
**Groq — Llama 3.3 70B Versatile** (same as existing pipeline)

### Dataset categories (target ~600 examples)

| Category | Count | Description |
|---|---|---|
| `find_talent` | 200 | PM asks for people with specific skills/experience |
| `filter_by_skills` | 150 | PM narrows by technology, years, seniority |
| `build_team` | 150 | PM needs multiple complementary people for a project |
| `check_availability` | 100 | PM asks who is free, on bench, rolling off |

### Dataset format
Each example = one full agent turn: PM question → tool call(s) → final answer.

```json
{
  "instruction": "Find me a senior Python developer with at least 3 years of Azure experience who is available now",
  "response": {
    "tool_calls": [
      {
        "tool": "query_candidates",
        "args": { "sql_filter": "seniority='senior' AND availability_status='available'" }
      },
      {
        "tool": "search_cvs",
        "args": { "query": "senior Python Azure developer", "filters": {} }
      }
    ],
    "answer": "Based on the CV index, Daniel Hughes is your strongest match — SC-cleared, senior cloud architect with Azure Terraform experience, available now."
  },
  "category": "find_talent"
}
```

### Training config
Base model existing config from `adapters_cv/adapter_config.json` as template:
- LoRA rank: 8
- Learning rate: 0.0001
- Iterations: 1000
- Save every: 100 steps

### Script to create
`generate_talent_search_dataset.py` — same structure as `generate_dataset.py` but with talent search categories and tool-calling response format.

### SECURITY FIX REQUIRED
The Groq API key is **hardcoded** in `generate_dataset.py` line 5:
```python
client = Groq(api_key="gsk_snezHp...")  # ← move this to .env
```
Move to environment variable before sharing or committing:
```python
import os
client = Groq(api_key=os.environ["GROQ_API_KEY"])
```

---

## Prioritised Build List

### Phase 1 — Data layer *(nothing works without this)*
- [ ] SQLite schema — create `employees`, `employee_skills`, `users` tables
- [ ] Seed 10 mock employees + skills for development
- [ ] ChromaDB local setup — create `employee_cvs` collection
- [ ] Embed mock CV text into Chroma
- [ ] FastAPI: replace stub with real `/search`, `/candidates`, `/profile` endpoints

### Phase 2 — Tool-calling fine-tune
- [ ] Move Groq API key to `.env`
- [ ] Write `generate_talent_search_dataset.py`
- [ ] Generate ~600 examples
- [ ] Train `adapters_talent_search/` via MLX LoRA
- [ ] Evaluate: manually check 20 agent turns for tool selection accuracy

### Phase 3 — Agentic `/ask` endpoint
- [ ] Replace current `LLM_URL` proxy stub in `main.py`
- [ ] Load Llama 3.2 3B + `adapters_talent_search` locally
- [ ] Implement tool-calling loop in FastAPI
- [ ] Test: PM question → tool calls → ranked answer

### Phase 4 — Auth + admin panel
- [ ] Login page (JWT, bcrypt passwords)
- [ ] Admin: PDF upload → ingestion pipeline trigger
- [ ] Admin: edit individual employee profile fields
- [ ] `last_updated` badge warning on stale profiles (>6 months)

### Phase 5 — Frontend QA fixes *(from Playwright run)*
- [ ] Fix default query "Azure healthcare RAG" returning 0 results
- [ ] Empty state UI when no CVs are loaded
- [ ] Connect Talent Search to real `/candidates` endpoint
- [ ] Connect AI Match to real `/ask` endpoint
- [ ] Connect Profiles to real `/profile` endpoint
- [ ] Connect Analytics to real aggregated data
- [ ] Connect Ingestion page to real ingestion status
- [ ] Add page title tag (`<title>TalentGraph</title>`)
- [ ] TypeScript build error fix (already done — `CompanyDirectory` state type)

### Phase 6 — Polish for demo
- [ ] Add `last_updated` staleness warning on profile cards
- [ ] Loading states on all async operations
- [ ] Error states when backend is unreachable
- [ ] Mobile layout QA pass

---

## What This Is NOT (v1 scope boundaries)

- Not a self-service portal for 15,000 employees
- Not integrated with TamTam API
- Not deployed to Reply IT infrastructure
- Not using Azure AD SSO
- Not auto-ingesting CVs from email
- Not a permission-scoped system (everyone sees everything)
- Not fine-tuning on real user interactions (no data yet)

---

## Future / v2

- Azure AD SSO
- Employee self-service profile page
- Automated mailbox ingestion (`cvs@reply.com`)
- Drift detection + retraining loop on real interactions
- TamTam integration
- Deploy to Reply IT infrastructure (AWS EC2/ECS or Azure Container Apps)
- EC2/ECS hosting for fine-tuned model
