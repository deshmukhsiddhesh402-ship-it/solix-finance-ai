"""
Module 9: Learning Mode — AI tutor + quiz generator for Excel, Advanced
Excel, Tally Prime, Power BI, GST, TDS, ITR, Accounting, Finance, and US CMA.
"""
import json
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.claude_service import ask_claude, learning_tutor_prompt, quiz_generation_prompt

router = APIRouter()

TOPICS = [
    "Excel", "Advanced Excel", "Tally Prime", "Power BI", "GST", "TDS",
    "ITR Filing", "Accounting", "Finance", "US CMA",
]


@router.get("/topics")
def list_topics():
    return {"topics": TOPICS}


class AskTutorRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=100)
    level: str = Field(default="beginner", pattern=r"^(beginner|intermediate|advanced)$")
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("topic", "question")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


@router.post("/ask")
def ask_tutor(req: AskTutorRequest):
    system, message = learning_tutor_prompt(req.topic, req.level, req.question)
    return {"answer": ask_claude(system, message, max_tokens=1200)}


class QuizRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=100)
    level: str = Field(default="beginner", pattern=r"^(beginner|intermediate|advanced)$")
    num_questions: int = Field(default=5, ge=1, le=20)

    @field_validator("topic")
    @classmethod
    def reject_blank_topic(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


def _strip_json_fences(text: str) -> str:
    """Claude sometimes wraps JSON in ```json fences despite instructions —
    strip them defensively before parsing."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _validate_quiz_questions(questions: object, expected_count: int) -> list[dict]:
    """Validate model output against the exact shape consumed by the quiz UI."""
    if not isinstance(questions, list) or len(questions) != expected_count:
        raise HTTPException(502, detail="Quiz generator returned an invalid response. Try again.")

    for question in questions:
        if not isinstance(question, dict):
            raise HTTPException(502, detail="Quiz generator returned an invalid response. Try again.")
        prompt = question.get("question")
        options = question.get("options")
        correct_index = question.get("correct_index")
        explanation = question.get("explanation")
        if (
            not isinstance(prompt, str) or not prompt.strip()
            or not isinstance(options, list) or len(options) != 4
            or any(not isinstance(option, str) or not option.strip() for option in options)
            or isinstance(correct_index, bool) or not isinstance(correct_index, int)
            or not 0 <= correct_index < 4
            or not isinstance(explanation, str) or not explanation.strip()
        ):
            raise HTTPException(502, detail="Quiz generator returned an invalid response. Try again.")

    return questions


@router.post("/generate-quiz")
def generate_quiz(req: QuizRequest):
    system, message = quiz_generation_prompt(req.topic, req.level, req.num_questions)
    raw = ask_claude(system, message, max_tokens=2000)
    try:
        questions = json.loads(_strip_json_fences(raw))
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(502, detail="Could not parse quiz response. Try again.") from None
    questions = _validate_quiz_questions(questions, req.num_questions)
    return {"topic": req.topic, "level": req.level, "questions": questions}
