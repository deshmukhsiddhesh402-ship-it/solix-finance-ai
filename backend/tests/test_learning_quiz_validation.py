from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.routers.learning import QuizRequest, _validate_quiz_questions, generate_quiz


def _question():
    return {
        "question": "What does GST stand for?",
        "options": [
            "Goods and Services Tax",
            "General Sales Tariff",
            "Gross Service Total",
            "Government Sales Tax",
        ],
        "correct_index": 0,
        "explanation": "GST is India's indirect tax on the supply of goods and services.",
    }


def test_quiz_response_accepts_expected_shape_and_count():
    questions = [_question(), _question()]

    assert _validate_quiz_questions(questions, 2) == questions


@pytest.mark.parametrize(
    "payload,count",
    [
        ({"question": "not an array"}, 1),
        ([], 1),
        ([_question()], 2),
        ([{**_question(), "options": ["only", "three", "options"]}], 1),
        ([{**_question(), "correct_index": 4}], 1),
        ([{**_question(), "correct_index": True}], 1),
        ([{**_question(), "question": "   "}], 1),
        ([{**_question(), "explanation": None}], 1),
        ([{**_question(), "options": ["valid", 2, "valid", "valid"]}], 1),
    ],
)
def test_quiz_response_rejects_invalid_shapes(payload, count):
    with pytest.raises(HTTPException) as exc:
        _validate_quiz_questions(payload, count)

    assert exc.value.status_code == 502


def test_generate_quiz_rejects_malformed_json():
    with patch("app.routers.learning.ask_claude", return_value="not json"):
        with pytest.raises(HTTPException) as exc:
            generate_quiz(QuizRequest(topic="GST", num_questions=1))

    assert exc.value.status_code == 502
    assert exc.value.detail == "Could not parse quiz response. Try again."


def test_generate_quiz_returns_validated_questions():
    import json

    with patch("app.routers.learning.ask_claude", return_value=json.dumps([_question()])):
        result = generate_quiz(QuizRequest(topic="GST", num_questions=1))

    assert result["topic"] == "GST"
    assert len(result["questions"]) == 1
    assert result["questions"][0]["correct_index"] == 0


def test_generate_quiz_rejects_non_json_object_response():
    import json

    with patch("app.routers.learning.ask_claude", return_value=json.dumps({"questions": [_question()]})):
        with pytest.raises(HTTPException) as exc:
            generate_quiz(QuizRequest(topic="GST", num_questions=1))

    assert exc.value.status_code == 502
