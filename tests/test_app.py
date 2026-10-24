from pathlib import Path

import pytest

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


def _submit(app) -> None:
    app.text_area[0].input("Refleksi untuk materi uji").run()
    app.button[0].click().run()
    app.button[1].click().run()
    next(item for item in app.checkbox if "Saya menyetujui" in item.label).check().run()
    app.button[-1].click().run()


def _live_evaluator(monkeypatch, endpoint="https://llm.example.test/v1") -> None:
    import app.services.llm_evaluator as evaluator_module

    monkeypatch.setattr(evaluator_module, "has_live_evaluator", lambda: True)
    monkeypatch.setattr(evaluator_module, "get_evaluator_endpoint", lambda: endpoint)


def _response(**overrides):
    from app.schemas.response import AssessmentResponse, CriterionResult, Evidence

    data = dict(
        assessment_id="ASM-TEST",
        status="pass",
        score=82.5,
        passing_score=75,
        summary="Hasil sesuai materi.",
        criteria=[CriterionResult(
            criterion_id="accuracy", name="Ketepatan konsep", weight=100,
            score=82.5, weighted_score=82.5, feedback="Konsep dijelaskan dengan tepat.",
        )],
        evidence=[Evidence(
            material_id="Materi Uji", chunk_id="Materi Uji:materi.pdf:1", page=1,
            reference_text="Kutipan asli", explanation="Mendukung jawaban.",
        )],
        strengths=["Penjelasan runtut"],
        improvements=["Tambahkan contoh penerapan"],
        review_required=False,
        review_reason=None,
    )
    data.update(overrides)
    return AssessmentResponse(**data)


def test_assessment_requires_save_then_explicit_consent(monkeypatch, tmp_path) -> None:
    import app.services.assessment as assessment_module

    _write_material(tmp_path)
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path))
    _live_evaluator(monkeypatch)
    calls = []
    monkeypatch.setattr(assessment_module, "assess_journal", lambda *args, **kwargs: calls.append((args, kwargs)))

    app = AppTest.from_file(APP).run()
    app.text_area[0].input("Refleksi untuk materi uji").run()
    app.button[1].click().run()
    assert any("Simpan jawaban terlebih dahulu" in item.value for item in app.info)
    assert not calls

    app.button[0].click().run()
    app.button[1].click().run()
    assert any("https://llm.example.test/v1" in item.value for item in app.warning)
    assert not any("9router" in item.value.casefold() for item in app.warning)
    assert not calls

    consent = next(item for item in app.checkbox if "Saya menyetujui" in item.label)
    consent.check().run()
    app.button[-1].click().run()

    assert calls
    request = calls[0][0][0]
    assert request.journal_text == "Refleksi untuk materi uji"
    assert request.material_id == "Materi Uji"


def test_unconfigured_evaluator_is_reported_before_consent(monkeypatch, tmp_path) -> None:
    import app.services.llm_evaluator as evaluator_module

    _write_material(tmp_path)
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path))
    monkeypatch.setattr(evaluator_module, "has_live_evaluator", lambda: False)

    app = AppTest.from_file(APP).run()
    app.text_area[0].input("Refleksi untuk materi uji").run()
    app.button[0].click().run()
    app.button[1].click().run()

    assert any("Mesin penilaian belum tersedia" in item.value for item in app.info)
    assert not app.checkbox


@pytest.mark.parametrize(("status", "score", "label"), [("pass", 82.5, "PASS"), ("not_pass", 61.25, "NOT PASS")])
def test_material_results_show_only_pass_status_without_score(monkeypatch, tmp_path, status, score, label) -> None:
    import app.services.assessment as assessment_module

    _write_material(tmp_path)
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path))
    _live_evaluator(monkeypatch)
    response = _response(status=status, score=score)
    monkeypatch.setattr(assessment_module, "assess_journal", lambda *args, **kwargs: response)

    app = AppTest.from_file(APP).run()
    _submit(app)

    shown = [item.value for item in (*app.success, *app.error)]
    assert shown == [label]
    assert not app.metric
    assert not app.json
    assert not app.get("download_button")
    rendered = " ".join(item.value for item in (*app.markdown, *app.caption))
    for hidden in (f"{score:g}", "Ketepatan konsep", "Mendukung jawaban", "Penjelasan runtut", "Tambahkan contoh"):
        assert hidden not in rendered


def test_review_result_shows_reason_without_score(monkeypatch, tmp_path) -> None:
    import app.services.assessment as assessment_module

    _write_material(tmp_path)
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path))
    _live_evaluator(monkeypatch)
    review = _response(
        status="needs_review", score=0, evidence=[], strengths=[], improvements=[],
        review_required=True, review_reason="insufficient_evidence",
    )
    monkeypatch.setattr(assessment_module, "assess_journal", lambda *args, **kwargs: review)

    app = AppTest.from_file(APP).run()
    _submit(app)

    assert any("belum dapat ditetapkan" in item.value for item in app.warning)
    assert any("Bukti dari materi tidak cukup" in item.value for item in app.caption)
    assert not app.metric
    assert not app.success


def test_provider_failure_shows_error_without_result(monkeypatch, tmp_path) -> None:
    import app.services.assessment as assessment_module
    from app.services.llm_client import ProviderRequestError

    _write_material(tmp_path)
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path))
    _live_evaluator(monkeypatch)

    def fail(*args, **kwargs):
        raise ProviderRequestError("offline")

    monkeypatch.setattr(assessment_module, "assess_journal", fail)

    app = AppTest.from_file(APP).run()
    _submit(app)

    assert any("Layanan penilaian tidak merespons" in item.value for item in app.error)
    assert not app.get("download_button")
