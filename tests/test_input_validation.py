import pytest

from app.core.config import get_max_journal_characters
from app.services.input_validation import validate_journal


def test_blank_journal_is_rejected() -> None:
    assert validate_journal(" \n\t", 20_000) == "Tuliskan jurnal sebelum menilai."


def test_exact_limit_is_accepted() -> None:
    assert validate_journal("x" * 20_000, 20_000) is None


def test_over_limit_is_rejected() -> None:
    assert "20,000" in validate_journal("x" * 20_001, 20_000)

@pytest.mark.parametrize("value", ["invalid", "0", "-1"])
def test_invalid_configuration_raises(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("MAX_JOURNAL_CHARACTERS", value)
    with pytest.raises(ValueError, match="positive integer"):
        get_max_journal_characters()
