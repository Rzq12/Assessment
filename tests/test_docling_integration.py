"""Docling integration tests (T-04, T-06, T-07, T-08).

These load Docling and its models, so they are excluded from the default run.
Run them with: python -m pytest -m integration
"""
import logging

import pytest

from app.services.document_parser import parse_document
from app.services.material_ingestion import ingest_materials

pytestmark = pytest.mark.integration

TEXT = "Prinsip merit dalam manajemen ASN menjamin kesetaraan kesempatan."


@pytest.fixture(scope="module", autouse=True)
def docling():
    try:
        import docling.document_converter  # noqa: F401
    except Exception as exc:  # Docling can fail on import with binary/NumPy mismatches.
        pytest.skip(f"Docling tidak dapat dimuat: {type(exc).__name__}")


def _text_pdf(path, pages):
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 100), text, fontsize=14)
    document.save(path)


def test_text_pdf_keeps_page_numbers(tmp_path):
    source = tmp_path / "materi.pdf"
    _text_pdf(source, ["Halaman pembuka materi pelatihan.", TEXT])
    cache = parse_document(source, "materi", tmp_path / "cache")
    matching = [chunk for chunk in cache.chunks if "merit" in chunk.text]
    assert matching
    assert matching[0].page == 2
    assert matching[0].content_type == "text"


def test_scanned_pdf_text_is_read_through_ocr(tmp_path):
    fitz = pytest.importorskip("fitz")
    if not any(_has_module(name) for name in ("rapidocr", "easyocr", "tesserocr")):
        pytest.skip("Tidak ada mesin OCR terpasang")
    text_pdf = tmp_path / "text.pdf"
    _text_pdf(text_pdf, [TEXT])
    pixmap = fitz.open(text_pdf)[0].get_pixmap(dpi=200)
    scanned = fitz.open()
    page = scanned.new_page()
    page.insert_image(page.rect, pixmap=pixmap)
    source = tmp_path / "scan.pdf"
    scanned.save(source)

    cache = parse_document(source, "scan", tmp_path / "cache")
    assert any("merit" in chunk.text.casefold() for chunk in cache.chunks)


def test_docx_keeps_headings_tables_and_order_without_pages(tmp_path):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_heading("Hak PPPK", level=1)
    document.add_paragraph("PPPK berhak memperoleh gaji dan tunjangan.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Hak"
    table.cell(0, 1).text = "Keterangan"
    table.cell(1, 0).text = "Cuti"
    table.cell(1, 1).text = "Cuti tahunan"
    source = tmp_path / "hak.docx"
    document.save(source)

    chunks = parse_document(source, "hak", tmp_path / "cache").chunks
    assert all(chunk.page is None for chunk in chunks)
    texts = [chunk.text for chunk in chunks]
    paragraph = next(i for i, text in enumerate(texts) if "gaji" in text)
    table_index = next(i for i, chunk in enumerate(chunks) if chunk.content_type == "table")
    assert paragraph < table_index
    assert "Cuti tahunan" in texts[table_index]
    assert "Hak PPPK" in chunks[paragraph].source_ref


def test_unreadable_document_is_skipped_and_logged(tmp_path, caplog):
    source_dir = tmp_path / "materi"
    source_dir.mkdir()
    (source_dir / "rusak.pdf").write_bytes(b"bukan pdf")
    with caplog.at_level(logging.WARNING):
        assert ingest_materials(source_dir, tmp_path / "cache") == []
    assert "rusak.pdf" in caplog.text


def _has_module(name):
    import importlib.util

    return importlib.util.find_spec(name) is not None
