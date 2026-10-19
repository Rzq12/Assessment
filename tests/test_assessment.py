import json
import logging

import pytest

from app.core.criteria import load_criteria
from app.schemas.request import AssessmentRequest
from app.schemas.response import RawEvaluation
from app.services.assessment import assess_journal
from app.services.llm_evaluator import EvaluatorNotConfigured, InvalidModelOutput
from app.services.llm_client import ProviderRequestError


def _cache(path, text):
    path.write_text(json.dumps({
        "schema_version": "1.0",
        "source_sha256": "a" * 64,
        "material_id": "modul",
        "document_name": "modul.pdf",
        "chunks": [{
            "material_id": "modul",
            "document_name": "modul.pdf",
            "page": 1,
            "content_type": "text",
            "text": text,
            "source_ref": "page 1",
            "needs_check": False,
        }],
    }), encoding="utf-8")


def _valid_raw():
    criteria = load_criteria()
    return RawEvaluation(
        summary="Baik",
        criteria=[{"criterion_id": c.criterion_id, "score": 90, "feedback": "Tepat", "evidence_sufficient": True} for c in criteria],
        evidence=[{"material_id": "modul", "chunk_id": "modul:modul.pdf:1", "page": 1, "reference_text": "prosedur keselamatan", "explanation": "Sumber mendukung"}],
        strengths=["Jelas"],
        improvements=[],
    )


def test_missing_material_returns_review_without_calling_evaluator(tmp_path):
    called = []
    response = assess_journal(AssessmentRequest(journal_text="prosedur evakuasi", material_id="missing"), tmp_path, load_criteria(), evaluator=lambda *a, **k: called.append(True))
    assert response.review_reason == "material_not_found"
    assert not called


def test_valid_mock_evaluation_flows_through_backend_scoring(tmp_path):
    _cache(tmp_path / "modul.json", "Prosedur keselamatan dan prosedur keselamatan")
    response = assess_journal(AssessmentRequest(journal_text="prosedur keselamatan"), tmp_path, load_criteria(), evaluator=lambda *a, **k: _valid_raw())
    assert response.score == 90
    assert response.evidence


def test_semantically_supported_answer_is_scored_without_lexical_match(tmp_path):
    _cache(tmp_path / "modul.json", "Prosedur keselamatan dan prosedur keselamatan")
    response = assess_journal(
        AssessmentRequest(journal_text="langkah menjaga keselamatan", material_id="modul"),
        tmp_path,
        load_criteria(),
        evaluator=lambda *a, **k: _valid_raw(),
    )
    assert response.status == "pass"
    assert response.score == 90


def test_no_relevant_material_skips_evaluator_and_is_non_scored_review(tmp_path):
    _cache(tmp_path / "modul.json", "Prosedur keselamatan")
    called = []
    response = assess_journal(
        AssessmentRequest(journal_text="teori musik klasik", material_id="modul"),
        tmp_path,
        load_criteria(),
        evaluator=lambda *a, **k: called.append(True),
    )
    assert response.status == "needs_review"
    assert response.score == 0
    assert not called


@pytest.mark.parametrize("error", [EvaluatorNotConfigured("missing"), ProviderRequestError("offline")])
def test_known_provider_failures_become_non_scored_review(tmp_path, error):
    _cache(tmp_path / "modul.json", "Prosedur keselamatan")
    response = assess_journal(
        AssessmentRequest(journal_text="prosedur keselamatan", material_id="modul"),
        tmp_path,
        load_criteria(),
        evaluator=lambda *a, **k: (_ for _ in ()).throw(error),
    )
    assert response.status == "needs_review"
    assert response.score == 0
    assert response.review_required


def test_unexpected_evaluator_error_propagates(tmp_path):
    _cache(tmp_path / "modul.json", "Prosedur keselamatan")
    with pytest.raises(RuntimeError, match="bug"):
        assess_journal(
            AssessmentRequest(journal_text="prosedur keselamatan", material_id="modul"),
            tmp_path,
            load_criteria(),
            evaluator=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bug")),
        )


def test_invalid_output_becomes_review_and_logs_never_include_journal(tmp_path, caplog):
    _cache(tmp_path / "modul.json", "Prosedur keselamatan")
    secret_journal = "PROTECTED JOURNAL CONTENT prosedur keselamatan"
    with caplog.at_level(logging.INFO):
        response = assess_journal(AssessmentRequest(journal_text=secret_journal), tmp_path, load_criteria(), evaluator=lambda *a, **k: (_ for _ in ()).throw(InvalidModelOutput("bad")))
    assert response.review_reason == "invalid_model_output"
    assert secret_journal not in caplog.text
