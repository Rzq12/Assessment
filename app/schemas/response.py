from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


Score = float


class AssessmentStatus(StrEnum):
    PASS = "pass"
    NOT_PASS = "not_pass"
    NEEDS_REVIEW = "needs_review"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    reference_text: str = Field(min_length=1)
    explanation: str = Field(min_length=1)


class RawCriterionScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_id: str = Field(min_length=1)
    score: Score = Field(ge=0, le=100, allow_inf_nan=False)
    feedback: str
    evidence_sufficient: bool


class RawEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    criteria: list[RawCriterionScore]
    evidence: list[Evidence]
    strengths: list[str]
    improvements: list[str]


class CriterionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    weight: int = Field(ge=0, le=100)
    score: Score = Field(ge=0, le=100, allow_inf_nan=False)
    weighted_score: Score = Field(ge=0, le=100, allow_inf_nan=False)
    feedback: str


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    assessment_id: str = Field(min_length=1)
    status: AssessmentStatus
    score: Score = Field(ge=0, le=100, allow_inf_nan=False)
    passing_score: Score = Field(ge=0, le=100, allow_inf_nan=False)
    summary: str
    criteria: list[CriterionResult]
    evidence: list[Evidence]
    strengths: list[str]
    improvements: list[str]
    review_required: bool
    review_reason: str | None

    @model_validator(mode="after")
    def validate_review_fields(self) -> Self:
        requires_review = self.status == AssessmentStatus.NEEDS_REVIEW
        if self.review_required != requires_review:
            raise ValueError("review_required must agree with assessment status")
        if requires_review and not (self.review_reason and self.review_reason.strip()):
            raise ValueError("review_reason is required when status is needs_review")
        if not requires_review and self.review_reason is not None:
            raise ValueError("review_reason must be empty unless status is needs_review")
        return self
