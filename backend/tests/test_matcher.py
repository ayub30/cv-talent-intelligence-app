from app.matcher import _extract_evidence, _infer_role, _keyword_score, rank_candidates


def test_keyword_score_positive_for_matching_words():
    score = _keyword_score("senior cloud architect with Azure experience", "cloud architect")
    assert score > 0


def test_keyword_score_zero_for_no_match():
    score = _keyword_score("experienced Java developer", "cloud architect")
    assert score == 0


def test_keyword_score_caps_at_75():
    score = _keyword_score(
        "azure cloud data python ml engineer architect senior leader devops",
        "azure cloud data python ml engineer architect senior leader devops",
    )
    assert score == 75


def test_keyword_score_ignores_stopwords():
    score_with = _keyword_score("the a an for who is in of", "cloud")
    score_without = _keyword_score("unrelated text", "cloud")
    assert score_with == score_without == 0


def test_extract_evidence_returns_matching_sentence():
    cv_text = "John is a cloud architect. He has Azure experience. He loves Python."
    evidence = _extract_evidence(cv_text, "Azure experience")
    assert "Azure" in evidence


def test_extract_evidence_truncates_long_result():
    long_sentence = "Azure " + "word " * 200
    evidence = _extract_evidence(long_sentence, "Azure")
    assert evidence.endswith("...")
    assert len(evidence) <= 163  # 160 + len("...")


def test_extract_evidence_handles_empty_cv():
    assert _extract_evidence("", "anything") == "See CV for details."


def test_infer_role_extracts_from_cv_text():
    cv_text = "Jane is a Senior Cloud Architect at TechCorp."
    assert _infer_role(cv_text, "senior", "TechCorp") == "Senior Cloud Architect"


def test_infer_role_falls_back_to_seniority_company():
    assert _infer_role("No pattern here.", "senior", "ACME") == "Senior at ACME"


def test_infer_role_returns_professional_when_no_seniority():
    assert _infer_role("No pattern here.", "", "") == "Professional"


def test_rank_candidates_uses_precomputed_score():
    candidates = [
        {
            "employee_id": "e1",
            "name": "Alice",
            "seniority": "senior",
            "company": "ACME",
            "chroma_doc_id": "e1",
            "score": 90,
        }
    ]
    cv_lookup = {"e1": "Alice is a senior cloud engineer."}
    ranked = rank_candidates("cloud engineer", candidates, cv_lookup)
    assert len(ranked) == 1
    assert ranked[0]["score"] == 90


def test_rank_candidates_uses_keyword_score_when_no_score_key():
    candidates = [
        {
            "employee_id": "e1",
            "name": "Alice",
            "seniority": "senior",
            "company": "ACME",
            "chroma_doc_id": "e1",
        }
    ]
    cv_lookup = {"e1": "Alice is a senior cloud engineer."}
    ranked = rank_candidates("cloud engineer", candidates, cv_lookup)
    assert len(ranked) == 1
    assert ranked[0]["score"] > 0


def test_rank_candidates_sorted_by_score_descending():
    candidates = [
        {"employee_id": "e1", "name": "Alice", "seniority": "", "company": "", "chroma_doc_id": "e1", "score": 50},
        {"employee_id": "e2", "name": "Bob", "seniority": "", "company": "", "chroma_doc_id": "e2", "score": 90},
    ]
    cv_lookup = {"e1": "cloud", "e2": "cloud"}
    ranked = rank_candidates("cloud", candidates, cv_lookup)
    assert ranked[0]["name"] == "Bob"
    assert ranked[1]["name"] == "Alice"


def test_rank_candidates_deduplicates_by_employee_id():
    candidates = [
        {"employee_id": "e1", "name": "Alice", "seniority": "", "company": "", "chroma_doc_id": "e1", "score": 90},
        {"employee_id": "e1", "name": "Alice", "seniority": "", "company": "", "chroma_doc_id": "e1", "score": 80},
    ]
    cv_lookup = {"e1": "cloud"}
    ranked = rank_candidates("cloud", candidates, cv_lookup)
    assert len(ranked) == 1


def test_rank_candidates_caps_at_five():
    candidates = [
        {"employee_id": f"e{i}", "name": f"Candidate {i}", "seniority": "", "company": "", "chroma_doc_id": f"e{i}", "score": i * 10}
        for i in range(10)
    ]
    cv_lookup = {f"e{i}": "cloud" for i in range(10)}
    ranked = rank_candidates("cloud", candidates, cv_lookup)
    assert len(ranked) == 5


def test_rank_candidates_includes_required_fields():
    candidates = [
        {"employee_id": "e1", "name": "Alice", "seniority": "senior", "company": "ACME", "chroma_doc_id": "e1", "score": 80}
    ]
    cv_lookup = {"e1": "Alice is a Senior Cloud Architect at ACME."}
    ranked = rank_candidates("cloud architect", candidates, cv_lookup)
    assert {"name", "role", "score", "evidence", "employee_id"} <= ranked[0].keys()


def test_rank_candidates_empty_input():
    assert rank_candidates("cloud", [], {}) == []


def test_rank_candidates_missing_cv_in_lookup():
    candidates = [
        {"employee_id": "e1", "name": "Alice", "seniority": "", "company": "", "chroma_doc_id": "e1"}
    ]
    ranked = rank_candidates("cloud", candidates, {})
    assert len(ranked) == 1
    assert ranked[0]["score"] == 0
