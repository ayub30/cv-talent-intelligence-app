# Talent-Search LoRA — Manual Evaluation Results

**Adapter config:** LoRA rank 8, α 16.0, lr 1e-4, 1000 iterations, save every 100 steps
**Overall tool-selection accuracy: 100% (20/20)**

## Turn-by-turn results

| # | Category | Question (truncated) | Expected tool | Predicted tool | Pass |
|---|----------|----------------------|---------------|----------------|------|
| 1 | find_talent | Find me someone with 5+ years of Python and machine lea… | search_cvs | search_cvs | ✓ |
| 2 | find_talent | Who has deep expertise in cloud architecture on AWS? | search_cvs | search_cvs | ✓ |
| 3 | find_talent | I need a consultant with experience in NLP and large la… | search_cvs | search_cvs | ✓ |
| 4 | find_talent | Find candidates with a background in financial risk mod… | search_cvs | search_cvs | ✓ |
| 5 | find_talent | Who has worked on digital transformation projects in he… | search_cvs | search_cvs | ✓ |
| 6 | filter_by_skills | Narrow the list to senior engineers who know Kubernetes… | query_candidates | query_candidates | ✓ |
| 7 | filter_by_skills | Filter to mid-level developers with at least 3 years of… | query_candidates | query_candidates | ✓ |
| 8 | filter_by_skills | Show me only lead consultants who have fintech domain k… | query_candidates | query_candidates | ✓ |
| 9 | filter_by_skills | Filter by seniority: I only want senior or above with P… | query_candidates | query_candidates | ✓ |
| 10 | filter_by_skills | Show only available consultants in the London office wi… | query_candidates | query_candidates | ✓ |
| 11 | build_team | I need a frontend engineer, a backend engineer, and a d… | search_cvs | search_cvs | ✓ |
| 12 | build_team | Build me a team for a mobile app project: iOS developer… | search_cvs | search_cvs | ✓ |
| 13 | build_team | I need a cloud architect, a DevOps engineer, and a secu… | search_cvs | search_cvs | ✓ |
| 14 | build_team | Assemble a data platform team: data engineer, ML engine… | search_cvs | search_cvs | ✓ |
| 15 | build_team | I need a full-stack developer, a business analyst, and … | search_cvs | search_cvs | ✓ |
| 16 | check_availability | Who on the bench is available to start within two weeks… | query_candidates | query_candidates | ✓ |
| 17 | check_availability | Which consultants are rolling off projects in the next … | query_candidates | query_candidates | ✓ |
| 18 | check_availability | Show me everyone who is currently available. | query_candidates | query_candidates | ✓ |
| 19 | check_availability | Who is free to take on a new engagement starting Monday… | query_candidates | query_candidates | ✓ |
| 20 | check_availability | Which senior engineers are available right now? | query_candidates | query_candidates | ✓ |

## Failures

None — all 20 turns passed.
