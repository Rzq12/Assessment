from pathlib import Path

import pytest

from app.core import config


def test_design_alias_for_journal_limit(monkeypatch) -> None:
    monkeypatch.setenv("MAX_JOURNAL_CHARS", "500")
    assert config.get_max_journal_characters() == 500
    monkeypatch.setenv("MAX_JOURNAL_CHARACTERS", "700")
    assert config.get_max_journal_characters() == 700


def test_directory_defaults_and_overrides(monkeypatch) -> None:
    assert config.get_materials_dir() == Path("Docs Materi")
    assert config.get_processed_dir() == Path("material_cache")
    assert config.get_criteria_file() is None
    monkeypatch.setenv("MATERIALS_DIR", "materials")
    monkeypatch.setenv("PROCESSED_DIR", "cache")
    assert config.get_materials_dir() == Path("materials")
    assert config.get_processed_dir() == Path("cache")


def test_ocr_defaults_follow_engine(monkeypatch) -> None:
    assert config.get_ocr_settings() == config.OcrSettings(engine="auto", languages=["id", "en"])
    monkeypatch.setenv("OCR_ENGINE", "tesseract")
    assert config.get_ocr_settings().languages == ["ind", "eng"]
    monkeypatch.setenv("OCR_LANG", "ind")
    assert config.get_ocr_settings().languages == ["ind"]


def test_invalid_ocr_engine_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("OCR_ENGINE", "magic")
    with pytest.raises(ValueError, match="OCR_ENGINE"):
        config.get_ocr_settings()


@pytest.mark.parametrize(("value", "expected"), [(None, False), ("false", False), ("true", True), ("1", True)])
def test_vision_flag(monkeypatch, value, expected) -> None:
    if value is not None:
        monkeypatch.setenv("VISION_ENABLED", value)
    assert config.is_vision_enabled() is expected


def test_vision_model_defaults_to_text_model(monkeypatch) -> None:
    for name, value in {
        "LLM_PROVIDER": "openai-compatible",
        "LLM_BASE_URL": "https://llm.example.test/v1",
        "LLM_MODEL": "text-model",
        "LLM_API_KEY": "key",
    }.items():
        monkeypatch.setenv(name, value)
    settings = config.get_llm_settings()
    assert settings.vision_model == "text-model"
    assert settings.temperature == 0.0
