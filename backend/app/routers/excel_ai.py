"""
Module 1: AI Excel Assistant — fully working.

Endpoints:
- POST /api/excel-ai/explain-formula
- POST /api/excel-ai/generate-formula
- POST /api/excel-ai/fix-formula
- POST /api/excel-ai/generate-vba
- POST /api/excel-ai/generate-office-script
- POST /api/excel-ai/plan-pivot-table
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.routers.enterprise import require_permission
from app.services.claude_service import (
    ask_claude,
    explain_formula_prompt,
    generate_formula_prompt,
    fix_formula_prompt,
    vba_macro_prompt,
    office_script_prompt,
    pivot_table_plan_prompt,
)

router = APIRouter()


class FormulaRequest(BaseModel):
    formula: str


class GenerateFormulaRequest(BaseModel):
    description: str


class FixFormulaRequest(BaseModel):
    formula: str
    error_description: str


class TaskRequest(BaseModel):
    task_description: str


class PivotPlanRequest(BaseModel):
    data_description: str
    goal: str


@router.post("/explain-formula")
def explain_formula(req: FormulaRequest, org_id: str = Query(...), _user: str = Depends(require_permission("chat", "create"))):
    system, message = explain_formula_prompt(req.formula)
    return {"explanation": ask_claude(system, message)}


@router.post("/generate-formula")
def generate_formula(req: GenerateFormulaRequest, org_id: str = Query(...), _user: str = Depends(require_permission("chat", "create"))):
    system, message = generate_formula_prompt(req.description)
    return {"formula": ask_claude(system, message)}


@router.post("/fix-formula")
def fix_formula(req: FixFormulaRequest, org_id: str = Query(...), _user: str = Depends(require_permission("chat", "create"))):
    system, message = fix_formula_prompt(req.formula, req.error_description)
    return {"fix": ask_claude(system, message)}


@router.post("/generate-vba")
def generate_vba(req: TaskRequest, org_id: str = Query(...), _user: str = Depends(require_permission("chat", "create"))):
    system, message = vba_macro_prompt(req.task_description)
    return {"vba_code": ask_claude(system, message, max_tokens=2000)}


@router.post("/generate-office-script")
def generate_office_script(req: TaskRequest, org_id: str = Query(...), _user: str = Depends(require_permission("chat", "create"))):
    system, message = office_script_prompt(req.task_description)
    return {"office_script": ask_claude(system, message, max_tokens=2000)}


@router.post("/plan-pivot-table")
def plan_pivot_table(req: PivotPlanRequest, org_id: str = Query(...), _user: str = Depends(require_permission("chat", "create"))):
    system, message = pivot_table_plan_prompt(req.data_description, req.goal)
    return {"plan": ask_claude(system, message)}
