import pytest

from app.core import config

_REAL_LOAD_ENVIRONMENT = config.load_environment
_ISOLATED_VARIABLES = (
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_TIMEOUT_SECONDS",
    "LLM_TEMPERATURE",
    "LLM_VISION_MODEL",
    "VISION_ENABLED",
    "OCR_ENGINE",
    "OCR_LANG",
    "CRITERIA_FILE",
    "PASSING_SCORE",
    "MAX_JOURNAL_CHARACTERS",
    "MAX_JOURNAL_CHARS",
    "MATERIALS_DIR",
    "PROCESSED_DIR",
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    """Keep the developer's real .env and shell settings out of every test."""
    monkeypatch.setattr(config, "load_environment", lambda: None)
    for name in _ISOLATED_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def real_load_environment(monkeypatch):
    monkeypatch.setattr(config, "load_environment", _REAL_LOAD_ENVIRONMENT)
