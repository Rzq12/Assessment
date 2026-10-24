from collections.abc import Sequence
from typing import TypedDict
from uuid import uuid4

from app.core.criteria import CriterionConfig
from app.schemas.response import (
    AssessmentResponse,
    AssessmentStatus,
    CriterionResult,
    RawEvaluation,
)


class MaterialChunk(TypedDict):
    material_id: str
    chunk_id: str
    page: int | None
    content_text: str

def score_assessment(
    raw: RawEvaluation,
    chunks: Sequence[MaterialChunk],
    criteria: Sequence[CriterionConfig],
    passing_score: float = 75.0,
    assessment_id: str | None = None,
) -> AssessmentResponse:
    configured = {criterion.criterion_id: criterion for criterion in criteria}
    raw_by_id = {criterion.criterion_id: criterion for criterion in raw.criteria}
    if len(raw_by_id) != len(raw.criteria) or raw_by_id.keys() != configured.keys():
        raise ValueError("raw criterion IDs must match configured criterion IDs exactly")
    if sum(criterion.weight for criterion in criteria) != 100:
        raise ValueError("criterion weights must total 100")
    if not 0 <= passing_score <= 100:
        raise ValueError("passing_score must be from 0 to 100")

    chunks_by_id = {(chunk["material_id"], chunk["chunk_id"]): chunk for chunk in chunks}
    verified_evidence = []
    for evidence in raw.evidence:
        chunk = chunks_by_id.get((evidence.material_id, evidence.chunk_id))
        if (
            chunk is not None
            and evidence.page == chunk["page"]
            and evidence.reference_text in chunk["content_text"]
        ):
            verified_evidence.append(evidence)

    # Unverifiable evidence and criteria the model marked as unsupported share one reason code.
    if not verified_evidence or any(not criterion.evidence_sufficient for criterion in raw.criteria):
        return AssessmentResponse(
            assessment_id=assessment_id or f"ASM-{uuid4().hex[:12].upper()}",
            status=AssessmentStatus.NEEDS_REVIEW,
            score=0,
            passing_score=passing_score,
            summary="Penilaian otomatis belum dapat diselesaikan.",
            criteria=[
                CriterionResult(
                    criterion_id=criterion.criterion_id,
                    name=criterion.name,
                    weight=criterion.weight,
                    score=0,
                    weighted_score=0,
                    feedback="Belum dinilai.",
                )
                for criterion in criteria
            ],
            evidence=verified_evidence,
            strengths=[],
            improvements=[],
            review_required=True,
            review_reason="insufficient_evidence",
        )

    results = [
        CriterionResult(
            criterion_id=criterion.criterion_id,
            name=configured[criterion.criterion_id].name,
            weight=configured[criterion.criterion_id].weight,
            score=criterion.score,
            weighted_score=criterion.score * configured[criterion.criterion_id].weight / 100,
            feedback=criterion.feedback,
        )
        for criterion in raw.criteria
    ]
    final_score = round(sum(result.weighted_score for result in results), 2)
    mandatory_met = all(
        configured[result.criterion_id].minimum_score is None
        or result.score >= configured[result.criterion_id].minimum_score
        for result in results
    )
    if final_score >= passing_score and mandatory_met:
        status = AssessmentStatus.PASS
    else:
        status = AssessmentStatus.NOT_PASS
    review_reason = None

    return AssessmentResponse(
        assessment_id=assessment_id or f"ASM-{uuid4().hex[:12].upper()}",
        status=status,
        score=final_score,
        passing_score=passing_score,
        summary=raw.summary,
        criteria=results,
        evidence=verified_evidence,
        strengths=raw.strengths,
        improvements=raw.improvements,
        review_required=status == AssessmentStatus.NEEDS_REVIEW,
        review_reason=review_reason,
    )
