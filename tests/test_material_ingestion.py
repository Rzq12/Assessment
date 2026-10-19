import logging

from app.schemas.material import MaterialCache
from app.services import material_ingestion


def test_ingest_is_sorted_and_skips_failures(tmp_path, monkeypatch, caplog):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "z.pdf").write_text("SECRET TEXT", encoding="utf-8")
    (source_dir / "a.docx").write_text("", encoding="utf-8")
    calls = []

    def parse(path, material_id, cache_dir):
        calls.append(path.name)
        if path.name == "a.docx":
            raise ValueError("SECRET TEXT")
        return MaterialCache(
            source_sha256="a" * 64,
            material_id=material_id,
            document_name=path.name,
            chunks=[],
        )

    monkeypatch.setattr(material_ingestion, "parse_document", parse)
    with caplog.at_level(logging.WARNING):
        results = material_ingestion.ingest_materials(source_dir, tmp_path / "cache")
    assert calls == ["a.docx", "z.pdf"]
    assert [item.document_name for item in results] == ["z.pdf"]
    assert "SECRET TEXT" not in caplog.text
