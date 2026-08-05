"""
Module 9: Learning Mode — AI tutor + quiz generator for Excel, Advanced
Excel, Tally Prime, Power BI, GST, TDS, ITR, Accounting, Finance, and US CMA.
"""
import json
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
    topic: str
    level: str = "beginner"  # beginner, intermediate, advanced
    question: str


@router.post("/ask")
def ask_tutor(req: AskTutorRequest):
    system, message = learning_tutor_prompt(req.topic, req.level, req.question)
    return {"answer": ask_claude(system, message, max_tokens=1200)}


class QuizRequest(BaseModel):
    topic: str
    level: str = "beginner"
    num_questions: int = 5


def _strip_json_fences(text: str) -> str:
    """Claude sometimes wraps JSON in ```json fences despite instructions —
    strip them defensively before parsing."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


@router.post("/generate-quiz")
def generate_quiz(req: QuizRequest):
    system, message = quiz_generation_prompt(req.topic, req.level, req.num_questions)
    raw = ask_claude(system, message, max_tokens=2000)
    try:
        questions = json.loads(_strip_json_fences(raw))
    except json.JSONDecodeError:
        raise HTTPException(502, detail="Could not parse quiz response. Try again.")
    return {"topic": req.topic, "level": req.level, "questions": questions}
