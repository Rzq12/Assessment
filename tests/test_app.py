from streamlit.testing.v1 import AppTest


APP = "app.py"


def test_initial_state() -> None:
    app = AppTest.from_file(APP).run()
    assert app.title[0].value == "Penilaian Jurnal SIBangkom"
    assert app.text_area[0].label == "Jurnal atau Rangkuman Pembelajaran"
    assert app.button[0].label == "Nilai Jurnal"
    assert "20,000" in app.caption[0].value


def test_blank_submit_shows_validation() -> None:
    app = AppTest.from_file(APP).run()
    app.button[0].click().run()
    assert app.error[0].value == "Tuliskan jurnal sebelum menilai."


def test_valid_submit_without_consent_does_not_call_assessment(monkeypatch) -> None:
    import app.services.assessment as assessment_module
    import app.services.llm_evaluator as evaluator_module

    calls = []
    monkeypatch.setattr(evaluator_module, "has_live_evaluator", lambda: True)
    monkeypatch.setattr(assessment_module, "assess_journal", lambda *args, **kwargs: calls.append(args))

    app = AppTest.from_file(APP).run()
    app.text_area[0].input("Refleksi pembelajaran yang bermakna.").run()
    app.button[0].click().run()

    assert "Penilaian tidak dimulai" in app.info[0].value
    assert not calls
    assert not app.metric
    assert not app.json
    assert not app.get("download_button")


def test_valid_submit_shows_unavailable_message_without_result() -> None:
    app = AppTest.from_file(APP).run()
    app.text_area[0].input("Refleksi pembelajaran yang bermakna.").run()
    app.checkbox[0].check().run()
    app.button[0].click().run()
    assert "Mesin penilaian belum tersedia" in app.info[0].value
    assert not app.metric
    assert not app.json


def test_consent_allows_assessment_and_valid_result_download(monkeypatch) -> None:
    from types import SimpleNamespace

    import app.services.assessment as assessment_module
    import app.services.llm_evaluator as evaluator_module

    evidence = [{"material_id": "M1", "chunk_id": "C1", "reference_text": "Materi terkait"}]
    result = SimpleNamespace(
        summary="Hasil sesuai materi.",
        status=SimpleNamespace(value="pass"),
        review_required=False,
        score=82.5,
        assessment_id="ASM-TEST",
        model_dump=lambda **kwargs: {"status": "pass", "evidence": evidence},
    )
    calls = []
    monkeypatch.setattr(evaluator_module, "has_live_evaluator", lambda: True)
    monkeypatch.setattr(
        assessment_module, "assess_journal", lambda *args, **kwargs: calls.append(args) or result
    )

    app = AppTest.from_file(APP).run()
    app.text_area[0].input("Refleksi pembelajaran yang bermakna.").run()
    app.checkbox[0].check().run()
    app.button[0].click().run()

    assert calls
    assert app.metric[0].value == "82.50 / 100"
    assert any("Status: **pass**" in item.value for item in app.markdown)
    import json

    assert json.loads(app.json[0].value)["evidence"] == evidence
    assert app.get("download_button")


def test_review_result_does_not_show_placeholder_score(monkeypatch) -> None:
    from types import SimpleNamespace

    import app.services.assessment as assessment_module
    import app.services.llm_evaluator as evaluator_module

    result = SimpleNamespace(
        summary="Penilaian otomatis belum dapat diselesaikan.",
        status=SimpleNamespace(value="needs_review"),
        review_required=True,
        review_reason="material_not_found",
        score=0,
        assessment_id="ASM-TEST",
        model_dump=lambda **kwargs: {},
    )
    monkeypatch.setattr(evaluator_module, "has_live_evaluator", lambda: True)
    monkeypatch.setattr(assessment_module, "assess_journal", lambda *args, **kwargs: result)

    app = AppTest.from_file(APP).run()
    app.text_area[0].input("Refleksi pembelajaran yang bermakna.").run()
    app.checkbox[0].check().run()
    app.button[0].click().run()

    assert not app.metric
    assert not app.json
    assert not app.get("download_button")
    assert any("belum menghasilkan skor" in item.value for item in app.warning)
