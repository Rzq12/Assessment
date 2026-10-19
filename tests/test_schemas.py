import json

import pytest
from pydantic import ValidationError

from app.schemas.request import AssessmentRequest
from app.schemas.response import AssessmentResponse, RawCriterionScore


def test_assessment_request_accepts_non_blank_journal() -> None:
    request = AssessmentRequest(journal_text=" Catatan belajar ")
    assert request.journal_text == " Catatan belajar "


@pytest.mark.parametrize("journal", ["", "  \n"])
def test_assessment_request_rejects_blank_journal(journal: str) -> None:
    with pytest.raises(ValidationError):
        AssessmentRequest(journal_text=journal)


def test_raw_criterion_score_rejects_out_of_range_and_extra_fields() -> None:
    base = {"criterion_id": "accuracy", "feedback": "OK", "evidence_sufficient": True}
    with pytest.raises(ValidationError):
        RawCriterionScore(**base, score=101)
    with pytest.raises(ValidationError):
        RawCriterionScore(**base, score=50, untrusted_status="pass")


def test_response_requires_review_reason_and_matching_flag() -> None:
    response = {
        "assessment_id": "ASM-1",
        "status": "needs_review",
        "score": 70,
        "passing_score": 75,
        "summary": "Review",
        "criteria": [],
        "evidence": [],
        "strengths": [],
        "improvements": [],
        "review_required": True,
        "review_reason": "Evidence missing",
    }
    assert AssessmentResponse.model_validate(response).review_required
    with pytest.raises(ValidationError):
        AssessmentResponse.model_validate({**response, "review_reason": None})
    with pytest.raises(ValidationError):
        AssessmentResponse.model_validate({**response, "review_required": False})


def test_response_round_trips_as_json() -> None:
    response = AssessmentResponse(
        assessment_id="ASM-1",
        status="pass",
        score=80,
        passing_score=75,
        summary="Complete",
        criteria=[],
        evidence=[],
        strengths=[],
        improvements=[],
        review_required=False,
        review_reason=None,
    )
    assert json.loads(response.model_dump_json())["schema_version"] == "1.0"
