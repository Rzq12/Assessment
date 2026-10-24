from app import ingest
from app.schemas.material import MaterialCache, MaterialChunk


def _cache() -> MaterialCache:
    chunk = MaterialChunk(
        material_id="a",
        document_name="a.pdf",
        page=1,
        content_type="text",
        text="Isi",
        source_ref="page 1",
        needs_check=True,
    )
    return MaterialCache(source_sha256="a" * 64, material_id="a", document_name="a.pdf", chunks=[chunk])


def test_cli_processes_directory_and_reports_counts(tmp_path, monkeypatch, capsys):
    source = tmp_path / "materi"
    source.mkdir()
    (source / "a.pdf").write_bytes(b"pdf")
    (source / "catatan.txt").write_text("x", encoding="utf-8")
    seen = {}

    def fake_ingest(source_dir, cache_dir, *, describe_image, force):
        seen.update(source_dir=source_dir, cache_dir=cache_dir, describe_image=describe_image, force=force)
        return [_cache()]

    monkeypatch.setattr(ingest, "ingest_materials", fake_ingest)
    assert ingest.main(["--source", str(source), "--cache", str(tmp_path / "cache"), "--force"]) == 0

    output = capsys.readouterr().out
    assert "a.pdf: 1 potongan, 1 perlu pemeriksaan" in output
    assert "1 materi tersimpan" in output
    assert "1 berkas dilewati" in output
    assert seen["source_dir"] == source
    assert seen["force"] is True
    assert seen["describe_image"] is None


def test_cli_uses_configured_directories(tmp_path, monkeypatch):
    source = tmp_path / "materi"
    source.mkdir()
    monkeypatch.setenv("MATERIALS_DIR", str(source))
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path / "cache"))
    seen = {}
    monkeypatch.setattr(ingest, "ingest_materials", lambda s, c, **k: seen.update(source=s, cache=c) or [])
    assert ingest.main([]) == 1
    assert seen == {"source": source, "cache": tmp_path / "cache"}


def test_cli_rejects_missing_source(tmp_path, capsys):
    assert ingest.main(["--source", str(tmp_path / "tidak-ada")]) == 1
    assert "tidak ditemukan" in capsys.readouterr().err


def test_cli_requires_llm_when_vision_enabled(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VISION_ENABLED", "true")
    assert ingest.main(["--source", str(tmp_path)]) == 1
    assert "VISION_ENABLED" in capsys.readouterr().err


def test_cli_rejects_invalid_ocr_engine(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OCR_ENGINE", "magic")
    assert ingest.main(["--source", str(tmp_path)]) == 1
    assert "OCR" in capsys.readouterr().err
