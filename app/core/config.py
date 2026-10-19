import os

DEFAULT_MAX_JOURNAL_CHARACTERS = 20_000
DEFAULT_LLM_PROVIDER = "openai-compatible"
DEFAULT_LLM_BASE_URL = "https://9router.riezqidr.my.id/v1"
DEFAULT_LLM_MODEL = "cx/gpt-6-luna"
DEFAULT_LLM_TIMEOUT_SECONDS = 60


def get_max_journal_characters() -> int:
    raw_value = os.getenv("MAX_JOURNAL_CHARACTERS")
    if raw_value is None:
        return DEFAULT_MAX_JOURNAL_CHARACTERS
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError("MAX_JOURNAL_CHARACTERS must be a positive integer") from exc
    if value <= 0:
        raise ValueError("MAX_JOURNAL_CHARACTERS must be a positive integer")
    return value
