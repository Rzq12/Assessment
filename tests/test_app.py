import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _write_material(path: Path) -> None:
    from app.schemas.material import MaterialCache, MaterialChunk

    chunk = MaterialChunk(
        material_id="Materi Uji",
        document_name="materi.pdf",
        page=1,
        content_type="text",
        text="Kutipan asli tentang pembelajaran dan penerapan.",
        source_ref="page 1",
    )
    cache = MaterialCache(
        source_sha256="a" * 64,
        material_id="Materi Uji",
        document_name="materi.pdf",
        chunks=[chunk],
    )
    path.mkdir(parents=True, exist_ok=True)
    (path / "materi.json").write_text(cache.model_dump_json(), encoding="utf-8")


def test_initial_state_shows_each_material(monkeypatch, tmp_path) -> None:
    _write_material(tmp_path)
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path))

    app = AppTest.from_file(APP).run()

    assert app.title[0].value == "Jurnal Pembelajaran"
    assert any(item.label == "Materi Uji" for item in app.expander)
    assert any(item.value == "Kutipan asli tentang pembelajaran dan penerapan." for item in app.caption)
    assert app.text_area[0].label == "Rangkuman pembelajaran"
    assert any(item.label == "Simpan" for item in app.button)
    assert any(item.label == "Nilai materi ini" for item in app.button)


def test_empty_cache_shows_actionable_state(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path / "empty"))
    app = AppTest.from_file(APP).run()
    assert any("Belum ada materi" in item.value for item in app.info)


def test_answer_save_is_session_scoped(monkeypatch, tmp_path) -> None:
    _write_material(tmp_path)
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path))

    app = AppTest.from_file(APP).run()
    app.text_area[0].input("Refleksi untuk materi uji").run()
    app.button[0].click().run()

    assert app.session_state["material_answers"]["Materi Uji"] == "Refleksi untuk materi uji"
    assert any("Tersimpan di sesi ini" in item.value for item in app.markdown)


def test_assessment_requires_save_then_explicit_consent(monkeypatch, tmp_path) -> None:
    import app.services.assessment as assessment_module
    import app.services.llm_evaluator as evaluator_module

    _write_material(tmp_path)
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path))
    monkeypatch.setattr(evaluator_module, "has_live_evaluator", lambda: True)
    calls = []
    monkeypatch.setattr(assessment_module, "assess_journal", lambda *args, **kwargs: calls.append((args, kwargs)))

    app = AppTest.from_file(APP).run()
    app.text_area[0].input("Refleksi untuk materi uji").run()
    app.button[1].click().run()
    assert any("Simpan jawaban terlebih dahulu" in item.value for item in app.info)
    assert not calls

    app.button[0].click().run()
    app.button[1].click().run()
    assert any("akan dikirim ke 9Router" in item.value for item in app.warning)
    assert not calls

    consent = next(item for item in app.checkbox if "Saya menyetujui" in item.label)
    consent.check().run()
    app.button[-1].click().run()

    assert calls
    request = calls[0][0][0]
    assert request.journal_text == "Refleksi untuk materi uji"
    assert request.material_id == "Materi Uji"


def test_material_results_render_score_and_hide_missing_score(monkeypatch, tmp_path) -> None:
    from types import SimpleNamespace

    import app.services.assessment as assessment_module
    import app.services.llm_evaluator as evaluator_module

    _write_material(tmp_path)
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path))
    monkeypatch.setattr(evaluator_module, "has_live_evaluator", lambda: True)
    result = SimpleNamespace(
        summary="Hasil sesuai materi.",
        status=SimpleNamespace(value="pass"),
        review_required=False,
        score=82.5,
        model_dump=lambda **kwargs: {"summary": "Hasil sesuai materi.", "status": "pass", "review_required": False, "score": 82.5},
    )
    monkeypatch.setattr(assessment_module, "assess_journal", lambda *args, **kwargs: result)

    app = AppTest.from_file(APP).run()
    app.text_area[0].input("Refleksi untuk materi uji").run()
    app.button[0].click().run()
    app.button[1].click().run()
    next(item for item in app.checkbox if "Saya menyetujui" in item.label).check().run()
    app.button[-1].click().run()

    assert app.metric[0].value == "82.50 / 100"
    assert any("Status: **pass**" in item.value for item in app.markdown)
    assert json.loads(app.json[0].value)["score"] == 82.5
