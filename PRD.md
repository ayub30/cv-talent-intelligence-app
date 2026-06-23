# TalentGraph — Product Requirements Document

**Project:** TalentGraph  
**Date:** 2026-06-23  
**Status:** Ready for implementation

---

## Problem Statement

Reply group project managers and practice leads have no way to search across all Reply employee CVs in one place. When a new client project lands, a PM has to manually email or message contacts across dozens of Reply subsidiaries to find people with the right skills, availability, and clearance. This takes days and relies on who you know — not what's actually in the employee base. Good candidates get missed; the same familiar names get recycled.

---

## Solution

TalentGraph is an internal CV intelligence tool. Admins upload employee CVs as PDFs. The system extracts structured data (skills, seniority, availability, years of experience per technology) and stores them in a searchable index. PMs and practice leads can then:

- Filter candidates by skill, years of experience, seniority, availability, and Reply subsidiary
- Ask a plain-English question ("find me two Azure architects with SC clearance available now") and get a ranked answer backed by CV evidence
- Build a shortlist and export a proposal pack

The frontend shell already exists. The job is to build the real data layer, ingestion pipeline, agentic loop, and auth behind it.

---

## User Stories

### Authentication & Access

1. As a project manager, I want to log in with a username and password, so that only authorised Reply staff can access employee CVs.
2. As a practice lead, I want my session to persist across page refreshes, so that I don't have to log in repeatedly during a working session.
3. As an admin, I want to be assigned a role stored in the system, so that the system can distinguish who uploaded a CV and who just searched.
4. As a project manager, I want to be logged out automatically after inactivity, so that CVs are not exposed on unattended machines.

### CV Ingestion

5. As an admin, I want to upload a PDF CV via the admin panel, so that the employee's data enters the system without manual data entry.
6. As an admin, I want the system to extract the employee's name, Reply subsidiary, location, seniority, availability status, current project, and skills with years of experience automatically from the uploaded PDF, so that structured search works without me filling in forms.
7. As an admin, I want to see a confirmation that ingestion succeeded (or a clear error if it failed), so that I know the CV is in the index.
8. As an admin, I want to re-upload a new PDF for an existing employee, so that their record is updated when their CV changes.
9. As an admin, I want to edit individual profile fields directly in the app without re-uploading a PDF, so that I can make small corrections quickly.
10. As an admin, I want to see a staleness warning on any profile that has not been updated in more than six months, so that I know which records are likely out of date.
11. As an admin, I want the ingestion panel to show which CVs have been indexed successfully and which have failed, so that I can identify and fix problem uploads.

### Talent Search

12. As a project manager, I want to filter candidates by skill and minimum years of experience in that skill, so that I only see people with the depth I actually need.
13. As a project manager, I want to filter by seniority level (junior / mid / senior / principal), so that I can match the project's grade requirements.
14. As a project manager, I want to filter by availability status (available now / on bench / on project), so that I don't shortlist people who can't start.
15. As a project manager, I want to filter by Reply subsidiary, so that I can prioritise people from a specific company when the client relationship requires it.
16. As a project manager, I want to filter by location, so that I can find people who can work on-site for a client.
17. As a project manager, I want to see the number of search results update as I adjust filters, so that I can tell immediately whether my criteria are too narrow.
18. As a project manager, I want to see an empty state message when no CVs match my filters, so that I don't think the system is broken.
19. As a project manager, I want to open a candidate's full profile from the search results, so that I can read the CV evidence before shortlisting them.

### Candidate Profiles

20. As a project manager, I want to see a candidate's match score, confidence score, and profile completeness on their profile page, so that I can quickly assess how well they fit the requirement.
21. As a project manager, I want to see a staleness warning if a profile has not been updated in over six months, so that I know to verify the information before making a decision.
22. As a project manager, I want to read the original CV evidence (bullet-point excerpts) that backs up each skill claim, so that I can assess quality rather than just labels.
23. As a project manager, I want to see identified gaps (missing skills, missing clearance, etc.) flagged on the profile, so that I can plan around them before proposing the person.

### AI Match (Agentic `/ask`)

24. As a project manager, I want to type a plain-English question ("find me two Azure architects with SC clearance available now") and get a ranked list of candidates with CV evidence, so that I can find the right people without knowing exact filter values.
25. As a project manager, I want the AI answer to reference actual CV evidence, not just names and scores, so that I can trust the recommendation.
26. As a project manager, I want the system to combine structured filter results (SQLite) with semantic CV search (ChromaDB) in a single answer, so that it catches both exact-match and experience-described-differently candidates.
27. As a project manager, I want to send follow-up questions in the same AI session ("now show me only the ones in London"), so that I can narrow down without starting over.
28. As a project manager, I want the AI workspace to show a loading state while the backend is processing, so that I know the request is in flight.

### Shortlist & Export

29. As a project manager, I want to add candidates to a shortlist during my search session, so that I can compare them at the end.
30. As a project manager, I want to remove candidates from my shortlist, so that I can change my mind without starting over.
31. As a project manager, I want to add a rationale note to each shortlisted candidate, so that the proposal pack explains why each person was chosen.
32. As a project manager, I want to export the shortlist as a proposal pack (CV summaries, AI evidence, gaps, approval notes), so that I can send it to the client or programme director.

### Analytics

33. As a practice lead, I want to see demand vs supply for key skills (e.g. Azure, RAG, Data migration), so that I can spot capability gaps before they become a delivery problem.
34. As a practice lead, I want to see a gap register showing which capabilities are at risk, so that I can plan hiring or training.

### Company Directory

35. As a project manager, I want to browse Reply subsidiaries and see how many indexed employees each has, so that I understand the talent pool per company.
36. As a project manager, I want to see a completeness score per subsidiary, so that I know which companies have reliable CV data.

---

## Implementation Decisions

### Data Layer

- **SQLite** stores structured employee fields: `employees` table (id, name, reply_company, location, seniority, availability_status, current_project_name, last_updated, chroma_doc_id) and `employee_skills` table (employee_id, skill, years_experience). A `users` table stores auth credentials.
- **ChromaDB** (local instance) stores one document per employee — the full CV text as a single chunk — in a collection called `employee_cvs`. Metadata per document: employee_id, reply_company, seniority.
- Both databases are initialised at app startup if they don't exist. A seed script populates 10 mock employees for development.

### CV Ingestion Pipeline

- Triggered by admin PDF upload to a new `/ingest` endpoint (POST, multipart/form-data).
- Pipeline steps: Unstructured.io → clean text → Llama 3.2 3B (local MLX) with extraction prompt → structured JSON → write to SQLite → embed full CV text into ChromaDB.
- The Llama extraction target schema: name, reply_company, location, seniority (enum), availability_status (enum), current_project_name (nullable), skills array (skill + years_experience per entry).
- Re-upload replaces the existing SQLite row and ChromaDB chunk for that employee.
- The `/ingest` endpoint returns a status object with success flag, extracted fields preview, and any parse errors.

### New FastAPI Endpoints

The existing `/ask` endpoint is extended; three new endpoints are added:

- `GET /candidates` — accepts query params: skill, min_years, seniority, availability, company, location. Queries SQLite `employees` + `employee_skills`. Returns paginated list with `total`.
- `GET /search` — accepts query param `q`. Runs semantic search against ChromaDB `employee_cvs`. Returns top-N results with score and employee_id.
- `GET /profile/{employee_id}` — fetches full CV chunk from ChromaDB by employee_id plus structured fields from SQLite. Returns combined profile object.
- `POST /ingest` — multipart PDF upload. Runs ingestion pipeline. Returns extraction result.
- `POST /auth/login` — username + password → JWT.
- `POST /auth/logout` — invalidates session.

### Agentic Loop

- The `/ask` endpoint is upgraded from a proxy stub to a real tool-calling loop.
- Three tools: `search_cvs(query, filters)`, `query_candidates(sql_filter)`, `get_profile(employee_id)`.
- The agent (Llama 3.2 3B + `adapters_talent_search/` LoRA) decides which tools to call, merges results, and returns a ranked answer with CV evidence.
- The LoRA adapter is trained separately (see GRILLING_SESSION.md Phase 2). The `/ask` endpoint falls back to the mock response until the adapter is available.

### Authentication

- JWT-based. Tokens stored in httpOnly cookies.
- Middleware validates the JWT on every protected route.
- The auth provider is swappable: username/password now, Azure AD SSO later. The middleware interface is the single change point.
- Roles (pm, practice_lead, admin) stored in SQLite `users` table. No UI differences between roles in v1 — roles exist for audit trail only.

### Fine-Tuning (Phase 2, separate workstream)

- Teacher model: Groq Llama 3.3 70B Versatile.
- Target: ~600 examples across four categories (find_talent, filter_by_skills, build_team, check_availability).
- Script: `generate_talent_search_dataset.py`. Same structure as `generate_dataset.py` but talent search categories and tool-calling response format.
- Output adapter: `adapters_talent_search/`. LoRA rank 8, lr 0.0001, 1000 iterations.
- **Security fix required before any dataset work:** move the hardcoded Groq API key in `generate_dataset.py` line 5 to an environment variable.

### Frontend Wiring

All pages currently render hardcoded mock data. Each page is wired to the real API in Phase 5:
- Talent Search → `GET /candidates`
- AI Match → `POST /ask`
- Profiles → `GET /profile/{id}`
- Ingestion → `POST /ingest` + ingestion status
- Analytics → aggregated data from SQLite
- Company Directory → aggregated from SQLite

---

## Testing Decisions

**What makes a good test here:** test through the HTTP API surface, not individual functions. A test should send a real HTTP request and assert on the real response shape and data. The SQLite database used in tests is an in-memory instance (`:memory:`); ChromaDB uses a real local instance pointing at a temp directory. No mocks of the storage layer.

**Single seam:** `httpx.AsyncClient` against the FastAPI `app` instance via `pytest-asyncio`. All test assertions happen at the HTTP boundary.

**Modules to test:**

- `POST /ingest` — upload a real test PDF, assert the extracted fields match expected values and the employee appears in subsequent `/candidates` and `/profile` queries.
- `GET /candidates` — seed known employees, assert filter combinations return correct subsets (skill + min_years, seniority, availability, company).
- `GET /search` — seed ChromaDB with known CV text, assert semantic search returns the expected employee for a known query.
- `GET /profile/{id}` — assert the combined SQLite + ChromaDB response has the correct shape and values.
- `POST /ask` — with the mock fallback active (no LLM loaded), assert the response has `answer`, `matches`, and `source` fields with correct types.
- `POST /auth/login` — assert valid credentials return a JWT; assert invalid credentials return 401.
- Protected endpoints — assert requests without a valid JWT return 401.

**Prior art:** The existing `backend/app/main.py` uses Pydantic models for request/response validation — the test fixture should assert the full response model, not just status codes.

---

## Out of Scope (v1)

- Employee self-service portal (employees do not log in)
- Azure AD SSO (username/password only in v1)
- TamTam API integration
- Automated email-triggered CV ingestion (`cvs@reply.com` mailbox)
- Deployment to Reply IT infrastructure
- Permission-scoped search (all authenticated users see all profiles)
- Fine-tuning on real interaction data (no production data yet)
- Mobile-optimised layout (desktop-first for v1)

---

## Further Notes

- The local Llama 3.2 3B model lives at `/Users/ayubmacalim/lora-finetune/models/llama-3.2-3B-instruct-mlx`. The three existing LoRA adapters (`adapters_cv/`, `adapters_v2/`, `adapters/`) are for different tasks and must not be loaded for TalentGraph.
- The Groq API key security fix in `generate_dataset.py` must be done before the dataset generation script is shared or committed anywhere.
- ChromaDB runs locally — no hosted instance needed at the scale of 10–15k documents.
- AWS is the preferred deployment target for future hosting (not Reply IT infrastructure in v1).
- The build phases from GRILLING_SESSION.md remain the authoritative ordering: Data layer → Fine-tune → Agentic loop → Auth + admin → Frontend wiring → Polish.
