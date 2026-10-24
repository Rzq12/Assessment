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
    assert [chunk.page for chunk in first.chunks] == [2, 3]
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


def _use_items(monkeypatch, items, calls=None):
    def convert(path):
        if calls is not None:
            calls.append(path)
        return SimpleNamespace(document=SimpleNamespace(iterate_items=lambda: iter(items)))

    monkeypatch.setattr(document_parser, "_create_converter", lambda: SimpleNamespace(convert=convert))


PROV = [SimpleNamespace(page_no=1)]


def test_unreadable_picture_and_table_are_flagged_not_guessed(tmp_path, monkeypatch):
    source = tmp_path / "guide.pdf"
    source.write_bytes(b"pdf")
    _use_items(monkeypatch, [
        (SimpleNamespace(label="text", text="Isi utama", prov=PROV), 1),
        (SimpleNamespace(label="picture", prov=PROV, children=[]), 1),
        (SimpleNamespace(label="table", text="", prov=PROV, data=SimpleNamespace(num_rows=0, num_cols=0)), 1),
        (SimpleNamespace(label="table", text="| A |", prov=PROV, data=SimpleNamespace(num_rows=0, num_cols=1)), 1),
    ])
    chunks = document_parser.parse_document(source, "guide", tmp_path / "cache").chunks
    assert [chunk.needs_check for chunk in chunks] == [False, True, True, True]
    assert chunks[1].text == document_parser.UNREADABLE_PICTURE_TEXT
    assert chunks[2].text == document_parser.UNREADABLE_TABLE_TEXT
    assert chunks[3].text == "| A |"


def test_picture_with_text_children_is_not_duplicated(tmp_path, monkeypatch):
    source = tmp_path / "guide.pdf"
    source.write_bytes(b"pdf")
    _use_items(monkeypatch, [
        (SimpleNamespace(label="picture", prov=PROV, children=["#/texts/1"]), 1),
        (SimpleNamespace(label="text", text="Teks di dalam gambar", prov=PROV), 2),
    ])
    chunks = document_parser.parse_document(source, "guide", tmp_path / "cache").chunks
    assert [chunk.text for chunk in chunks] == ["Teks di dalam gambar"]


@pytest.mark.parametrize(
    ("answer", "expected_type", "expected_text"),
    [
        ("Diagram alur rekrutmen PPPK", "vision", "Diagram alur rekrutmen PPPK"),
        ("TIDAK_TERBACA", "text", document_parser.UNREADABLE_PICTURE_TEXT),
        (None, "text", document_parser.UNREADABLE_PICTURE_TEXT),
    ],
)
def test_vision_describes_pictures_only_when_readable(tmp_path, monkeypatch, answer, expected_type, expected_text):
    from PIL import Image

    source = tmp_path / "guide.pdf"
    source.write_bytes(b"pdf")
    picture = SimpleNamespace(label="picture", prov=PROV, children=[], get_image=lambda doc: Image.new("RGB", (4, 4)))
    _use_items(monkeypatch, [
        (SimpleNamespace(label="text", text="Isi utama", prov=PROV), 1),
        (picture, 1),
    ])
    images = []
    chunk = document_parser.parse_document(
        source, "guide", tmp_path / "cache", describe_image=lambda png: images.append(png) or answer
    ).chunks[1]
    assert images and images[0].startswith(b"\x89PNG")
    assert chunk.content_type == expected_type
    assert chunk.text == expected_text
    assert chunk.needs_check is True


def test_force_reprocesses_despite_valid_cache(tmp_path, monkeypatch):
    source = tmp_path / "guide.pdf"
    source.write_bytes(b"pdf")
    calls = []
    _use_items(monkeypatch, [(SimpleNamespace(label="text", text="Isi", prov=PROV), 1)], calls)
    document_parser.parse_document(source, "guide", tmp_path / "cache")
    document_parser.parse_document(source, "guide", tmp_path / "cache", force=True)
    assert len(calls) == 2


def test_document_with_only_unreadable_elements_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "guide.pdf"
    source.write_bytes(b"pdf")
    _use_items(monkeypatch, [(SimpleNamespace(label="picture", prov=PROV, children=[]), 1)])
    with pytest.raises(ValueError, match="no extractable text"):
        document_parser.parse_document(source, "guide", tmp_path / "cache")


def test_build_image_describer_is_disabled_by_default():
    assert document_parser.build_image_describer() is None


def test_build_image_describer_requires_llm_configuration(monkeypatch):
    from app.core.config import EvaluatorNotConfigured

    monkeypatch.setenv("VISION_ENABLED", "true")
    with pytest.raises(EvaluatorNotConfigured):
        document_parser.build_image_describer()


def test_docx_section_headers_become_source_refs_without_page_checks(tmp_path, monkeypatch):
    source = tmp_path / "hak.docx"
    source.write_bytes(b"docx")
    _use_items(monkeypatch, [
        (SimpleNamespace(label="section_header", text="Hak PPPK", prov=[]), 1),
        (SimpleNamespace(label="text", text="PPPK berhak atas gaji.", prov=[]), 1),
    ])
    chunks = document_parser.parse_document(source, "hak", tmp_path / "cache").chunks
    assert [chunk.text for chunk in chunks] == ["Hak PPPK", "PPPK berhak atas gaji."]
    assert all(chunk.page is None and not chunk.needs_check for chunk in chunks)
    assert chunks[1].source_ref == "Hak PPPK (element 2)"


def test_invalid_pdf_page_number_marks_check(tmp_path, monkeypatch):
    source = tmp_path / "guide.pdf"
    source.write_bytes(b"pdf")
    _use_items(monkeypatch, [(SimpleNamespace(label="text", text="Isi", prov=[SimpleNamespace(page_no=0)]), 1)])
    chunk = document_parser.parse_document(source, "guide", tmp_path / "cache").chunks[0]
    assert chunk.page is None
    assert chunk.needs_check is True
