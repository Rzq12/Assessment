import hashlib
import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from app.schemas.material import MaterialCache

CACHE_SCHEMA_VERSION = "1.0"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_cache(cache_path: Path, source_path: Path, material_id: str) -> MaterialCache | None:
    if not cache_path.exists():
        return None
    try:
        cache = MaterialCache.model_validate_json(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValidationError):
        return None
    if cache.schema_version != CACHE_SCHEMA_VERSION or cache.material_id != material_id:
        return None
    if cache.document_name != source_path.name or cache.source_sha256 != file_sha256(source_path):
        return None
    return cache


def write_cache(cache_path: Path, cache: MaterialCache) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=cache_path.parent, delete=False
        ) as temporary:
            temp_path = Path(temporary.name)
            temporary.write(cache.model_dump_json(indent=2))
            temporary.flush()
            os.fsync(temporary.fileno())
        temp_path.replace(cache_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
