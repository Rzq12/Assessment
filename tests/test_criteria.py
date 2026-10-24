import json

import pytest
from pydantic import ValidationError

from app.core.criteria import get_passing_score, load_criteria


def test_loads_default_criteria() -> None:
    criteria = load_criteria()
    assert [criterion.weight for criterion in criteria] == [40, 30, 20, 10]


def test_loads_custom_criteria(tmp_path) -> None:
    path = tmp_path / "criteria.json"
    path.write_text(json.dumps([{"criterion_id": "one", "name": "One", "weight": 100}]))
    assert load_criteria(path)[0].criterion_id == "one"


@pytest.mark.parametrize(
    "data",
    [
        [{"criterion_id": "a", "name": "A", "weight": 99}],
        [
            {"criterion_id": "a", "name": "A", "weight": 50},
            {"criterion_id": "a", "name": "A again", "weight": 50},
        ],
        [],
    ],
)
def test_rejects_invalid_criteria(tmp_path, data) -> None:
    path = tmp_path / "criteria.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValidationError):
        load_criteria(path)


def test_passing_score_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PASSING_SCORE", "82")
    assert get_passing_score() == 82
    monkeypatch.setenv("PASSING_SCORE", "101")
    with pytest.raises(ValueError, match="0 to 100"):
        get_passing_score()


def test_criteria_file_can_be_configured(monkeypatch, tmp_path) -> None:
    path = tmp_path / "custom.json"
    path.write_text(json.dumps([{"criterion_id": "only", "name": "Only", "weight": 100, "minimum_score": 60}]))
    monkeypatch.setenv("CRITERIA_FILE", str(path))
    criteria = load_criteria()
    assert [item.criterion_id for item in criteria] == ["only"]
    assert criteria[0].minimum_score == 60
