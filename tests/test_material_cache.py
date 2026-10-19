import json

import pytest
from pydantic import ValidationError

from app.core.material_cache import CACHE_SCHEMA_VERSION, file_sha256, read_cache, write_cache
from app.schemas.material import MaterialCache, MaterialChunk


def make_chunk(**overrides) -> MaterialChunk:
    data = {
        "material_id": "MAT-1",
        "document_name": "module.pdf",
        "page": 1,
        "content_type": "text",
        "text": "Source content",
        "source_ref": "page 1, element 0",
    }
    data.update(overrides)
    return MaterialChunk(**data)


def make_cache(source_path, **overrides) -> MaterialCache:
    return MaterialCache(
        schema_version=CACHE_SCHEMA_VERSION,
        source_sha256=file_sha256(source_path),
        material_id="MAT-1",
        document_name=source_path.name,
        chunks=[make_chunk()],
        **overrides,
    )


def test_material_chunk_requires_source_trace_and_text() -> None:
    with pytest.raises(ValidationError):
        make_chunk(text="")
    with pytest.raises(ValidationError):
        make_chunk(extra_field="not allowed")


def test_sha256_is_stable_and_changes_with_source(tmp_path) -> None:
    source = tmp_path / "module.pdf"
    source.write_bytes(b"first")
    first_hash = file_sha256(source)
    assert first_hash == file_sha256(source)
    source.write_bytes(b"second")
    assert first_hash != file_sha256(source)


def test_cache_round_trip(tmp_path) -> None:
    source = tmp_path / "module.pdf"
    source.write_bytes(b"pdf bytes")
    cache_path = tmp_path / "cache" / "module.json"
    expected = make_cache(source)
    write_cache(cache_path, expected)
    assert read_cache(cache_path, source, "MAT-1") == expected


def test_changed_source_invalidates_cache(tmp_path) -> None:
    source = tmp_path / "module.pdf"
    source.write_bytes(b"old")
    cache_path = tmp_path / "module.json"
    write_cache(cache_path, make_cache(source))
    source.write_bytes(b"new")
    assert read_cache(cache_path, source, "MAT-1") is None


@pytest.mark.parametrize("contents", ["{invalid", json.dumps({"schema_version": "9.0"})])
def test_malformed_or_unsupported_cache_is_ignored(tmp_path, contents) -> None:
    source = tmp_path / "module.pdf"
    source.write_bytes(b"pdf")
    cache_path = tmp_path / "module.json"
    cache_path.write_text(contents, encoding="utf-8")
    assert read_cache(cache_path, source, "MAT-1") is None


def test_different_material_id_invalidates_cache(tmp_path) -> None:
    source = tmp_path / "module.pdf"
    source.write_bytes(b"pdf")
    cache_path = tmp_path / "module.json"
    write_cache(cache_path, make_cache(source))
    assert read_cache(cache_path, source, "OTHER") is None
