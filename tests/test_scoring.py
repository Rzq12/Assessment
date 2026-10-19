import pytest

from app.core.criteria import CriterionConfig
from app.schemas.response import Evidence, RawCriterionScore, RawEvaluation
from app.services.scoring import MaterialChunk, score_assessment


CRITERIA = [
    CriterionConfig(criterion_id="a", name="A", weight=40),
    CriterionConfig(criterion_id="b", name="B", weight=30),
    CriterionConfig(criterion_id="c", name="C", weight=20),
    CriterionConfig(criterion_id="d", name="D", weight=10),
]
CHUNK: MaterialChunk = {
    "material_id": "MAT-1",
    "chunk_id": "CH-1",
    "page": 3,
    "content_text": "Source supports this claim.",
}
EVIDENCE = Evidence(
    material_id="MAT-1",
    chunk_id="CH-1",
    page=3,
    reference_text="supports this claim",
    explanation="Matches the source.",
)


def make_evaluation(scores=(90, 80, 70, 60), *, sufficient=True, evidence=None) -> RawEvaluation:
    return RawEvaluation(
        summary="Summary",
        criteria=[
            RawCriterionScore(
                criterion_id=criterion.criterion_id,
                score=score,
                feedback="Feedback",
                evidence_sufficient=sufficient,
            )
            for criterion, score in zip(CRITERIA, scores, strict=True)
        ],
        evidence=[EVIDENCE] if evidence is None else evidence,
        strengths=[],
        improvements=[],
    )


def test_weighted_score_is_calculated_by_backend() -> None:
    result = score_assessment(make_evaluation(), [CHUNK], CRITERIA, assessment_id="ASM-1")
    assert result.score == 80
    assert [item.weighted_score for item in result.criteria] == [36, 24, 14, 6]
    assert result.status == "pass"


@pytest.mark.parametrize(("scores", "expected"), [((75, 75, 75, 75), "pass"), ((74.99, 74.99, 74.99, 74.99), "not_pass")])
def test_status_threshold(scores, expected) -> None:
    result = score_assessment(make_evaluation(scores), [CHUNK], CRITERIA, passing_score=75)
    assert result.status == expected


def test_rounds_score_before_threshold_comparison() -> None:
    criteria = [CriterionConfig(criterion_id="a", name="A", weight=100)]
    raw = RawEvaluation(
        summary="S",
        criteria=[RawCriterionScore(criterion_id="a", score=74.996, feedback="F", evidence_sufficient=True)],
        evidence=[EVIDENCE], strengths=[], improvements=[],
    )
    result = score_assessment(raw, [CHUNK], criteria, passing_score=75)
    assert result.score == 75
    assert result.status == "pass"


def test_raw_criterion_ids_must_match_exactly() -> None:
    raw = make_evaluation()
    with pytest.raises(ValueError, match="IDs must match"):
        score_assessment(raw, [CHUNK], CRITERIA[:3])
    duplicate = raw.model_copy(update={"criteria": [*raw.criteria[:-1], raw.criteria[0]]})
    with pytest.raises(ValueError, match="IDs must match"):
        score_assessment(duplicate, [CHUNK], CRITERIA)


@pytest.mark.parametrize(
    "evidence",
    [
        Evidence(material_id="MAT-1", chunk_id="UNKNOWN", page=3, reference_text="supports this claim", explanation="x"),
        Evidence(material_id="OTHER", chunk_id="CH-1", page=3, reference_text="supports this claim", explanation="x"),
        Evidence(material_id="MAT-1", chunk_id="CH-1", page=2, reference_text="supports this claim", explanation="x"),
        Evidence(material_id="MAT-1", chunk_id="CH-1", page=3, reference_text="invented quote", explanation="x"),
    ],
)
def test_unverifiable_evidence_is_discarded_and_requires_review(evidence) -> None:
    result = score_assessment(make_evaluation(evidence=[evidence]), [CHUNK], CRITERIA)
    assert result.evidence == []
    assert result.status == "needs_review"
    assert result.score == 0
    assert result.review_reason


def test_valid_evidence_and_page_less_docx_chunk_are_accepted() -> None:
    docx_chunk: MaterialChunk = {**CHUNK, "page": None}
    docx_evidence = EVIDENCE.model_copy(update={"page": None})
    result = score_assessment(make_evaluation(evidence=[docx_evidence]), [docx_chunk], CRITERIA)
    assert result.evidence == [docx_evidence]


def test_insufficient_criterion_evidence_requires_review() -> None:
    result = score_assessment(make_evaluation(sufficient=False), [CHUNK], CRITERIA)
    assert result.status == "needs_review"
    assert "tidak cukup" in result.review_reason
