from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    journal_text: str = Field(min_length=1)
    material_id: str | None = None

    @field_validator("journal_text")
    @classmethod
    def journal_must_contain_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("journal_text must not be blank")
        return value
