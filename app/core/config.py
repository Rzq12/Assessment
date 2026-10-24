import math
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MAX_JOURNAL_CHARACTERS = 20_000
SUPPORTED_LLM_PROVIDERS = {"openai-compatible"}
DEFAULT_LLM_TIMEOUT_SECONDS = 60
DEFAULT_LLM_TEMPERATURE = 0.0
DEFAULT_MATERIALS_DIR = "Docs Materi"
DEFAULT_PROCESSED_DIR = "material_cache"
SUPPORTED_OCR_ENGINES = {"auto", "easyocr", "tesseract", "rapidocr", "none"}
DEFAULT_OCR_ENGINE = "auto"


class EvaluatorNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    base_url: str
    model: str
    api_key: str
    timeout: float
    temperature: float
    vision_model: str


@dataclass(frozen=True)
class OcrSettings:
    engine: str
    languages: list[str]


def load_environment() -> None:
    """Load the project .env without overriding variables that are already set."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def get_max_journal_characters() -> int:
    # MAX_JOURNAL_CHARS is the name used in the technical design; both are accepted.
    if os.getenv("MAX_JOURNAL_CHARACTERS") is None and os.getenv("MAX_JOURNAL_CHARS") is not None:
        return _positive_int("MAX_JOURNAL_CHARS", DEFAULT_MAX_JOURNAL_CHARACTERS)
    return _positive_int("MAX_JOURNAL_CHARACTERS", DEFAULT_MAX_JOURNAL_CHARACTERS)


def get_materials_dir() -> Path:
    return Path(os.getenv("MATERIALS_DIR", DEFAULT_MATERIALS_DIR))


def get_processed_dir() -> Path:
    return Path(os.getenv("PROCESSED_DIR", DEFAULT_PROCESSED_DIR))


def get_criteria_file() -> Path | None:
    raw_value = os.getenv("CRITERIA_FILE", "").strip()
    return Path(raw_value) if raw_value else None


def is_vision_enabled() -> bool:
    return os.getenv("VISION_ENABLED", "false").strip().casefold() in {"1", "true", "yes", "on"}


def get_ocr_settings() -> OcrSettings:
    engine = os.getenv("OCR_ENGINE", DEFAULT_OCR_ENGINE).strip().casefold() or DEFAULT_OCR_ENGINE
    if engine not in SUPPORTED_OCR_ENGINES:
        raise ValueError(f"OCR_ENGINE must be one of: {', '.join(sorted(SUPPORTED_OCR_ENGINES))}")
    raw_languages = os.getenv("OCR_LANG", "").strip()
    if raw_languages:
        languages = [item.strip() for item in raw_languages.split(",") if item.strip()]
    elif engine == "tesseract":
        languages = ["ind", "eng"]
    else:
        languages = ["id", "en"]
    return OcrSettings(engine=engine, languages=languages)


def get_llm_settings() -> LLMSettings:
    load_environment()
    provider = os.getenv("LLM_PROVIDER", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    vision_model = os.getenv("LLM_VISION_MODEL", "").strip() or model
    try:
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", str(DEFAULT_LLM_TIMEOUT_SECONDS)))
        temperature = float(os.getenv("LLM_TEMPERATURE", str(DEFAULT_LLM_TEMPERATURE)))
    except ValueError as exc:
        raise EvaluatorNotConfigured("LLM_TIMEOUT_SECONDS or LLM_TEMPERATURE is invalid") from exc
    if not provider or not base_url or not model or not api_key:
        raise EvaluatorNotConfigured("LLM provider is not configured")
    if provider not in SUPPORTED_LLM_PROVIDERS:
        raise EvaluatorNotConfigured(f"LLM_PROVIDER must be one of: {', '.join(sorted(SUPPORTED_LLM_PROVIDERS))}")
    if not math.isfinite(timeout) or timeout <= 0:
        raise EvaluatorNotConfigured("LLM_TIMEOUT_SECONDS must be positive")
    if not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise EvaluatorNotConfigured("LLM_TEMPERATURE must be from 0 to 2")
    return LLMSettings(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout=timeout,
        temperature=temperature,
        vision_model=vision_model,
    )
