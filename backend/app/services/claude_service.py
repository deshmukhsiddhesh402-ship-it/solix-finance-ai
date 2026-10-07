"""
Thin wrapper around the Anthropic Claude API used by every AI-powered
module (Excel Assistant, AI Chat, Financial Insights, etc).

Keeping all Claude calls behind one service means we can add:
- retry/backoff
- prompt-versioning
- response caching (Redis)
in exactly one place instead of scattering client calls across routers.
"""
import anthropic
import json

from app.core.config import settings

MAX_CLAUDE_INPUT_CHARS = 50_000
MAX_CLAUDE_SYSTEM_CHARS = 20_000
MAX_CLAUDE_OUTPUT_TOKENS = 4_000
MAX_CLAUDE_TOOL_COUNT = 32
MAX_CLAUDE_IMAGE_BASE64_CHARS = 15_000_000


def _validate_request(system_prompt: str, user_message: str, max_tokens: int) -> None:
    if not isinstance(system_prompt, str) or len(system_prompt) > MAX_CLAUDE_SYSTEM_CHARS:
        raise ValueError("System prompt exceeds the supported length limit.")
    if not isinstance(user_message, str) or len(user_message) > MAX_CLAUDE_INPUT_CHARS:
        raise ValueError("User input exceeds the supported length limit.")
    if max_tokens < 1 or max_tokens > MAX_CLAUDE_OUTPUT_TOKENS:
        raise ValueError("max_tokens must be between 1 and 4000.")

_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def ask_claude(system_prompt: str, user_message: str, max_tokens: int = 1500) -> str:
    """Send a single-turn request to Claude and return the text response."""
    _validate_request(system_prompt, user_message, max_tokens)
    response = _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    # Concatenate all text blocks (Claude can return multiple content blocks).
    return "".join(block.text for block in response.content if block.type == "text")


def ask_claude_with_image(
    system_prompt: str, user_text: str, image_base64: str, media_type: str, max_tokens: int = 1500
) -> str:
    """Send a single-turn request with an image attached (used by the
    Invoice/Receipt OCR module — Claude reads the document visually rather
    than relying on a separate OCR engine like Tesseract).
    """
    _validate_request(system_prompt, user_text, max_tokens)
    if not isinstance(image_base64, str) or not image_base64 or len(image_base64) > MAX_CLAUDE_IMAGE_BASE64_CHARS:
        raise ValueError("Image payload exceeds the supported size limit.")
    response = _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}},
                {"type": "text", "text": user_text},
            ],
        }],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def ask_claude_with_tools(
    system_prompt: str, user_message: str, tools: list[dict], max_tokens: int = 1500,
):
    """Single-turn tool-use call: Claude either replies directly or returns
    a tool_use block describing which function to call and with what
    arguments. Returns the raw response object so the caller can inspect
    stop_reason and content blocks (see app.routers.copilot for the full
    two-step orchestration: ask -> execute tool -> ask again with result).
    """
    _validate_request(system_prompt, user_message, max_tokens)
    if not isinstance(tools, list) or len(tools) > MAX_CLAUDE_TOOL_COUNT:
        raise ValueError("Tool count exceeds the supported limit.")
    return _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        tools=tools,
        messages=[{"role": "user", "content": user_message}],
    )


def continue_with_tool_result(
    system_prompt: str, user_message: str, tools: list[dict],
    assistant_content: list, tool_use_id: str, tool_result: dict, max_tokens: int = 1500,
) -> str:
    """Second turn of the tool-use loop: feed the executed tool's real
    result back to Claude so it can write the final natural-language answer
    grounded in actual computed numbers, not invented ones.
    """
    response = _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        tools=tools,
        messages=[
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_content},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": json.dumps(tool_result, default=str)},
            ]},
        ],
    )
    return "".join(block.text for block in response.content if block.type == "text")


# ---------------------------------------------------------------------------
# Prompt templates for each Excel AI Assistant capability.
# Keeping these as named functions (not inline strings in the router) makes
# them easy to test, version, and swap out per-feature.
# ---------------------------------------------------------------------------

def explain_formula_prompt(formula: str) -> tuple[str, str]:
    system = (
        "You are a senior Excel/Financial Modeling expert. Explain the given "
        "Excel formula in plain English: what it does, each function's role, "
        "and a worked example with sample numbers. Be concise and precise."
    )
    return system, f"Explain this Excel formula:\n{formula}"


def generate_formula_prompt(description: str) -> tuple[str, str]:
    system = (
        "You are a senior Excel formula expert. Given a plain-English "
        "description of what the user wants, return the exact Excel formula "
        "(prefer modern dynamic-array/XLOOKUP-era functions where they help), "
        "then a one-line explanation of how it works."
    )
    return system, f"Write an Excel formula for: {description}"


def fix_formula_prompt(formula: str, error_description: str) -> tuple[str, str]:
    system = (
        "You are a senior Excel troubleshooting expert. The user has a broken "
        "or erroring formula. Identify the root cause, provide the corrected "
        "formula, and explain what was wrong in 1-2 sentences."
    )
    return system, f"Formula: {formula}\nError/issue: {error_description}"


def vba_macro_prompt(task_description: str) -> tuple[str, str]:
    system = (
        "You are a senior Excel VBA developer. Write clean, commented VBA "
        "macro code that accomplishes the user's task. Include error handling "
        "and use Option Explicit. Return only the VBA code block plus a short "
        "usage note."
    )
    return system, f"Write a VBA macro that: {task_description}"


def office_script_prompt(task_description: str) -> tuple[str, str]:
    system = (
        "You are a senior Office Scripts (TypeScript for Excel Online) "
        "developer. Write a valid Office Script function `main(workbook: "
        "ExcelScript.Workbook)` that accomplishes the user's task, with "
        "comments explaining each step."
    )
    return system, f"Write an Office Script that: {task_description}"


def pivot_table_plan_prompt(data_description: str, goal: str) -> tuple[str, str]:
    system = (
        "You are a senior Excel Pivot Table / Power Pivot expert. Given a "
        "description of the source data and the user's analysis goal, "
        "specify exactly: which fields go in Rows, Columns, Values (with "
        "aggregation type), and Filters, plus any DAX measures needed if "
        "Power Pivot is warranted."
    )
    return system, f"Data: {data_description}\nGoal: {goal}"


def rag_chat_prompt(question: str, retrieved_chunks: list[str]) -> tuple[str, str]:
    """Build a grounded-answer prompt for the AI Chat / RAG module.
    Only uses the retrieved document excerpts as source material — instructs
    Claude not to fabricate figures beyond what's given.
    """
    system = (
        "You are a senior CA/CMA financial analyst assistant. Answer the "
        "user's question using ONLY the provided document excerpts. If the "
        "excerpts don't contain the answer, say so plainly rather than "
        "guessing. Cite which excerpt number supports each claim, e.g. [1]. "
        "Be concise and precise with figures."
    )
    context = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(retrieved_chunks))
    user_message = f"Document excerpts:\n{context}\n\nQuestion: {question}"
    return system, user_message


# ---------------------------------------------------------------------------
# Learning Mode prompts
# ---------------------------------------------------------------------------
def learning_tutor_prompt(topic: str, level: str, question: str) -> tuple[str, str]:
    """A patient tutor persona for teaching Excel, Tally, Power BI, GST/TDS/
    ITR, Accounting, Finance, or US CMA concepts."""
    system = (
        f"You are an expert tutor teaching {topic} to a {level}-level student "
        "preparing for real-world work or exams (e.g. US CMA, CA, or Excel "
        "proficiency). Explain clearly with a short worked example. Use "
        "plain language first, then precise technical terms. Keep answers "
        "focused — a few paragraphs or a short list, not an essay — and end "
        "with one practice question the student can try."
    )
    return system, question


def quiz_generation_prompt(topic: str, level: str, num_questions: int) -> tuple[str, str]:
    system = (
        f"You are an exam-question writer for {topic} at {level} level "
        "(contexts: Excel proficiency, Tally Prime, Power BI, Indian GST/TDS/"
        "ITR compliance, financial accounting, or US CMA). Return ONLY valid "
        "JSON (no markdown fences, no preamble): an array of objects each "
        'with keys "question", "options" (array of 4 strings), '
        '"correct_index" (0-3), and "explanation" (1-2 sentences).'
    )
    user_message = f"Generate {num_questions} multiple-choice questions on: {topic}"
    return system, user_message


# ---------------------------------------------------------------------------
# Invoice / Receipt OCR prompt
# ---------------------------------------------------------------------------
INVOICE_EXTRACTION_SYSTEM_PROMPT = (
    "You are an expert at reading Indian tax invoices and receipts. Look at "
    "the provided image and extract the following fields as strict JSON — "
    "no markdown fences, no preamble, just the JSON object:\n"
    "{\n"
    '  "vendor_name": string or null,\n'
    '  "vendor_gstin": string or null (15-character GSTIN if visible),\n'
    '  "invoice_number": string or null,\n'
    '  "invoice_date": string or null (format YYYY-MM-DD if determinable),\n'
    '  "taxable_value": number or null,\n'
    '  "cgst_amount": number or null,\n'
    '  "sgst_amount": number or null,\n'
    '  "igst_amount": number or null,\n'
    '  "total_amount": number or null,\n'
    '  "line_items": [{"description": string, "quantity": number or null, "amount": number}],\n'
    '  "confidence_notes": string (brief note on any field you are unsure about, or "none")\n'
    "}\n"
    "If a field isn't visible or legible, use null rather than guessing. "
    "Numbers must be plain numbers (no currency symbols or commas)."
)
