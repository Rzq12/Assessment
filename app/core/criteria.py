import json
import os
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CriterionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    weight: int = Field(gt=0, le=100)


class CriteriaFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criteria: list[CriterionConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_criteria(self) -> Self:
        ids = [item.criterion_id for item in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion_id values must be unique")
        if sum(item.weight for item in self.criteria) != 100:
            raise ValueError("criterion weights must total 100")
        return self


def load_criteria(path: Path | None = None) -> list[CriterionConfig]:
    criteria_path = path or Path(__file__).with_name("criteria.json")
    data = json.loads(criteria_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        data = {"criteria": data}
    return CriteriaFile.model_validate(data).criteria


def get_passing_score() -> float:
    raw_value = os.getenv("PASSING_SCORE", "75")
    try:
        score = float(raw_value)
    except ValueError as exc:
        raise ValueError("PASSING_SCORE must be a number from 0 to 100") from exc
    if not 0 <= score <= 100:
        raise ValueError("PASSING_SCORE must be a number from 0 to 100")
    return score
