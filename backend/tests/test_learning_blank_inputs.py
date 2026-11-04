import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.learning import (
    AskTutorRequest,
    QuizRequest,
    _validate_quiz_questions,
)


@pytest.mark.parametrize(
    "payload",
    [
        {"topic": "   ", "question": "Explain GST"},
        {"topic": "GST", "question": " \n\t "},
    ],
)
def test_ask_tutor_rejects_blank_topic_or_question(payload):
    with pytest.raises(ValidationError):
        AskTutorRequest(**payload)


@pytest.mark.parametrize("topic", ["", "   ", "\n\t"])
def test_quiz_request_rejects_blank_topic(topic):
    with pytest.raises(ValidationError):
        QuizRequest(topic=topic)


def test_learning_requests_trim_surrounding_whitespace():
    ask_request = AskTutorRequest(
        topic="  GST  ",
        question="  Explain input tax credit.  ",
    )
    quiz_request = QuizRequest(topic="  Tally Prime  ")

    assert ask_request.topic == "GST"
    assert ask_request.question == "Explain input tax credit."
    assert quiz_request.topic == "Tally Prime"


def test_quiz_response_validator_accepts_expected_shape():
    questions = [{
        "question": "Which tax is levied on intra-state supply?",
        "options": ["CGST and SGST", "IGST", "Customs duty", "TDS"],
        "correct_index": 0,
        "explanation": "Intra-state supplies attract CGST and SGST.",
    }]

    assert _validate_quiz_questions(questions, 1) == questions


@pytest.mark.parametrize(
    "questions",
    [
        None,
        {},
        [],
        [{"question": "Q", "options": ["A", "B", "C"], "correct_index": 0, "explanation": "Why"}],
        [{"question": "Q", "options": ["A", "B", "C", "D"], "correct_index": True, "explanation": "Why"}],
        [{"question": "Q", "options": ["A", "B", "C", "D"], "correct_index": 4, "explanation": "Why"}],
        [{"question": " ", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "Why"}],
        [{"question": "Q", "options": ["A", " ", "C", "D"], "correct_index": 0, "explanation": "Why"}],
        [{"question": "Q", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": " "}],
    ],
)
def test_quiz_response_validator_rejects_malformed_model_output(questions):
    with pytest.raises(HTTPException) as exc:
        _validate_quiz_questions(questions, 1)

    assert exc.value.status_code == 502


def test_quiz_response_validator_requires_exact_question_count():
    with pytest.raises(HTTPException) as exc:
        _validate_quiz_questions(
            [{"question": "Q", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "Why"}],
            2,
        )

    assert exc.value.status_code == 502
