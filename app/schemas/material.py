from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MaterialChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str = Field(min_length=1)
    document_name: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    content_type: Literal["text", "table", "ocr", "vision"]
    text: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    needs_check: bool = False
    chunk_id: str | None = None

class MaterialCache(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    material_id: str = Field(min_length=1)
    document_name: str = Field(min_length=1)
    chunks: list[MaterialChunk]
