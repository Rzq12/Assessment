from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import document_parser


def test_parse_pdf_chunks_and_cache_hit(tmp_path, monkeypatch):
    source = tmp_path / "guide.pdf"
    source.write_bytes(b"pdf")
    items = [
        (SimpleNamespace(label="text", text="Guidance", prov=[SimpleNamespace(page_no=2)]), "body"),
        (SimpleNamespace(label="table", text="| A | B |", prov=[SimpleNamespace(page_no=3)]), "body"),
    ]
    calls = []
    monkeypatch.setattr(document_parser, "_create_converter", lambda: SimpleNamespace(
        convert=lambda path: calls.append(path) or SimpleNamespace(document=SimpleNamespace(iterate_items=lambda: iter(items)))
    ))
    first = document_parser.parse_document(source, "guide", tmp_path / "cache")
    second = document_parser.parse_document(source, "guide", tmp_path / "cache")
    assert [chunk.page for chunk in first.chunks] == [3, 4]
    assert [chunk.content_type for chunk in first.chunks] == ["text", "table"]
    assert second == first
    assert len(calls) == 1


def test_missing_pdf_provenance_marks_check(tmp_path, monkeypatch):
    source = tmp_path / "guide.pdf"
    source.write_bytes(b"pdf")
    item = SimpleNamespace(label="text", text="Unlocated", prov=[])
    monkeypatch.setattr(document_parser, "_create_converter", lambda: SimpleNamespace(
        convert=lambda _: SimpleNamespace(document=SimpleNamespace(iterate_items=lambda: iter([(item, "body")])))
    ))
    chunk = document_parser.parse_document(source, "guide", tmp_path / "cache").chunks[0]
    assert chunk.page is None
    assert chunk.needs_check is True


def test_unsupported_extension_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        document_parser.parse_document(tmp_path / "notes.txt", "notes", tmp_path / "cache")
