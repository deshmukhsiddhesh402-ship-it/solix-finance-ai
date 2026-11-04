import pytest
from pydantic import ValidationError

from app.routers.learning import AskTutorRequest, QuizRequest


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
