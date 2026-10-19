import json
import re
from pathlib import Path
from typing import TypedDict

from pydantic import ValidationError

from app.schemas.material import MaterialCache

_TOKEN_PATTERN = re.compile(r"[\w-]+", re.UNICODE)
_STOP_WORDS = {"dan", "yang", "di", "ke", "dari", "untuk", "dengan", "the", "and", "of", "to", "in", "a", "is"}


class RetrievedChunk(TypedDict):
    material_id: str
    chunk_id: str
    document_name: str
    page: int | None
    content_type: str
    text: str
    content_text: str
    source_ref: str
    needs_check: bool


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_PATTERN.findall(text) if len(token) > 1 and token.casefold() not in _STOP_WORDS}


def _load_caches(cache_dir: Path) -> list[MaterialCache]:
    caches: list[MaterialCache] = []
    if not cache_dir.exists():
        return caches
    for path in sorted(cache_dir.glob("*.json")):
        try:
            cache = MaterialCache.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, ValidationError):
            continue
        caches.append(cache)
    return caches


def retrieve_materials(
    journal_text: str,
    material_id: str | None,
    cache_dir: Path,
    *,
    limit: int = 8,
    minimum_score: float = 0.08,
) -> list[RetrievedChunk]:
    if limit < 1 or not 0 <= minimum_score <= 1:
        raise ValueError("limit must be positive and minimum_score must be from 0 to 1")
    query_tokens = _tokens(journal_text)
    if not query_tokens:
        return []
    caches = _load_caches(cache_dir)
    if material_id is not None:
        caches = [cache for cache in caches if cache.material_id == material_id]
    if not caches:
        return []

    ranked_by_material: dict[str, list[tuple[float, str, int, RetrievedChunk]]] = {}
    for cache in caches:
        for index, chunk in enumerate(cache.chunks):
            chunk_tokens = _tokens(chunk.text)
            if not chunk_tokens:
                continue
            score = len(query_tokens & chunk_tokens) / len(query_tokens | chunk_tokens)
            if score < minimum_score:
                continue
            chunk_id = f"{cache.material_id}:{cache.document_name}:{index + 1}"
            record: RetrievedChunk = {
                "material_id": cache.material_id,
                "chunk_id": chunk_id,
                "document_name": cache.document_name,
                "page": chunk.page,
                "content_type": chunk.content_type,
                "text": chunk.text,
                "content_text": chunk.text,
                "source_ref": chunk.source_ref,
                "needs_check": chunk.needs_check,
            }
            ranked_by_material.setdefault(cache.material_id, []).append((score, cache.document_name, index, record))

    if material_id is None:
        material_scores = sorted(
            ((max(item[0] for item in items), key) for key, items in ranked_by_material.items()),
            reverse=True,
        )
        if not material_scores:
            return []
        best_score = material_scores[0][0]
        if len(material_scores) > 1 and best_score - material_scores[1][0] < 0.05:
            return []
        if best_score < max(minimum_score, 0.15):
            return []
        ranked = ranked_by_material[material_scores[0][1]]
    else:
        ranked = [item for values in ranked_by_material.values() for item in values]

    ranked.sort(key=lambda item: (-item[0], item[1].casefold(), item[2]))
    return [item[3] for item in ranked[:limit]]
