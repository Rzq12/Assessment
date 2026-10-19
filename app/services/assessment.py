import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.core.criteria import CriterionConfig
from app.schemas.material import MaterialChunk
from app.schemas.request import AssessmentRequest
from app.schemas.response import (
    AssessmentResponse,
    AssessmentStatus,
    CriterionResult,
    RawEvaluation,
)
from app.services.llm_evaluator import EvaluatorClient, InvalidModelOutput, evaluate
from app.services.material_retriever import RetrievedChunk, retrieve_materials
from app.services.scoring import score_assessment

logger = logging.getLogger(__name__)
Evaluator = Callable[..., RawEvaluation]


def _review_response(
    assessment_id: str,
    criteria: Sequence[CriterionConfig],
    passing_score: float,
    reason: str,
) -> AssessmentResponse:
    return AssessmentResponse(
        assessment_id=assessment_id,
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
        evidence=[],
        strengths=[],
        improvements=[],
        review_required=True,
        review_reason=reason,
    )


def assess_journal(
    request: AssessmentRequest,
    cache_dir: Path,
    criteria: Sequence[CriterionConfig],
    *,
    passing_score: float = 75.0,
    evaluator: Evaluator | None = None,
    client: EvaluatorClient | None = None,
) -> AssessmentResponse:
    assessment_id = f"ASM-{uuid4().hex[:12].upper()}"
    started = perf_counter()
    selected_evaluator = evaluator or evaluate
    try:
        chunks: list[RetrievedChunk] = retrieve_materials(
            request.journal_text, request.material_id, cache_dir
        )
        if not chunks:
            response = _review_response(assessment_id, criteria, passing_score, "material_not_found")
            logger.info("assessment_id=%s status=%s duration_ms=%d", assessment_id, response.status, int((perf_counter() - started) * 1000))
            return response
        evaluator_chunks = [
            MaterialChunk(
                material_id=chunk["material_id"],
                document_name=chunk["document_name"],
                page=chunk["page"],
                content_type=chunk["content_type"],
                text=chunk["text"],
                source_ref=chunk["source_ref"],
                needs_check=chunk["needs_check"],
                chunk_id=chunk["chunk_id"],
            )
            for chunk in chunks
        ]
        try:
            raw = selected_evaluator(
                request.journal_text,
                evaluator_chunks,
                criteria,
                client=client,
            )
        except InvalidModelOutput:
            response = _review_response(assessment_id, criteria, passing_score, "invalid_model_output")
            logger.info("assessment_id=%s status=%s error=invalid_model_output duration_ms=%d", assessment_id, response.status, int((perf_counter() - started) * 1000))
            return response
        scoring_chunks = [
            {
                "material_id": chunk["material_id"],
                "chunk_id": chunk["chunk_id"],
                "page": chunk["page"],
                "content_text": chunk["text"],
            }
            for chunk in chunks
        ]
        response = score_assessment(raw, scoring_chunks, criteria, passing_score, assessment_id)
        logger.info("assessment_id=%s status=%s duration_ms=%d", assessment_id, response.status, int((perf_counter() - started) * 1000))
        return response
    except Exception as exc:
        logger.warning("assessment_id=%s error=%s duration_ms=%d", assessment_id, type(exc).__name__, int((perf_counter() - started) * 1000))
        raise
