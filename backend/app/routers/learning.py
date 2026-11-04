"""
Module 9: Learning Mode — AI tutor + quiz generator for Excel, Advanced
Excel, Tally Prime, Power BI, GST, TDS, ITR, Accounting, Finance, and US CMA.

AI usage controls: tutor prompts are limited to 2,000 characters, quiz requests
are limited to 20 questions, and Claude responses use explicit token ceilings.
For deployment-wide request-rate quotas, enforce a per-authenticated-user limit
at the API gateway/shared rate-limit service; application-local counters would
not be reliable across multiple backend workers.
"""
import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth_dependencies import require_user_permission
from app.services.claude_service import ask_claude, learning_tutor_prompt, quiz_generation_prompt

router = APIRouter()
TOPICS = [
    "Excel", "Advanced Excel", "Tally Prime", "Power BI", "GST", "TDS",
    "ITR Filing", "Accounting", "Finance", "US CMA",
]
LEARNING_AI_PERMISSION = require_user_permission("chat", "create")


@router.get("/topics")
def list_topics():
    return {"topics": TOPICS}


class AskTutorRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=100)
    level: str = Field(default="beginner", pattern=r"^(beginner|intermediate|advanced)$")
    question: str = Field(min_length=1, max_length=2000)


@router.post("/ask")
def ask_tutor(req: AskTutorRequest, _user: str = Depends(LEARNING_AI_PERMISSION)):
    system, message = learning_tutor_prompt(req.topic, req.level, req.question)
    return {"answer": ask_claude(system, message, max_tokens=1200)}


class QuizRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=100)
    level: str = Field(default="beginner", pattern=r"^(beginner|intermediate|advanced)$")
    num_questions: int = Field(default=5, ge=1, le=20)


def _strip_json_fences(text: str) -> str:
    """Claude sometimes wraps JSON in ```json fences despite instructions —
    strip them defensively before parsing."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


@router.post("/generate-quiz")
def generate_quiz(req: QuizRequest, _user: str = Depends(LEARNING_AI_PERMISSION)):
    system, message = quiz_generation_prompt(req.topic, req.level, req.num_questions)
    raw = ask_claude(system, message, max_tokens=2000)
    try:
        questions = json.loads(_strip_json_fences(raw))
    except json.JSONDecodeError as exc:
        raise HTTPException(502, detail="Could not parse quiz response. Try again.") from exc
    return {"topic": req.topic, "level": req.level, "questions": questions}
