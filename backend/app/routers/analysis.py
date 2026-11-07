"""
Module 6: Financial Analysis — API layer over analysis_engine.py
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.analysis_engine import (
    npv, irr, cagr, break_even, dcf_valuation, Scenario, scenario_analysis,
)

router = APIRouter()


class NpvRequest(BaseModel):
    rate_pct: float
    cash_flows: list[float]


@router.post("/npv")
def npv_endpoint(req: NpvRequest):
    try:
        return {"npv": npv(req.rate_pct, req.cash_flows)}
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


class IrrRequest(BaseModel):
    cash_flows: list[float]


@router.post("/irr")
def irr_endpoint(req: IrrRequest):
    try:
        result = irr(req.cash_flows)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(422, detail="No real IRR found for these cash flows in the search range.")
    return {"irr_pct": result}


class CagrRequest(BaseModel):
    beginning_value: float
    ending_value: float
    years: float


@router.post("/cagr")
def cagr_endpoint(req: CagrRequest):
    try:
        return {"cagr_pct": cagr(req.beginning_value, req.ending_value, req.years)}
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


class BreakEvenRequest(BaseModel):
    fixed_costs: float
    price_per_unit: float
    variable_cost_per_unit: float


@router.post("/break-even")
def break_even_endpoint(req: BreakEvenRequest):
    try:
        return break_even(req.fixed_costs, req.price_per_unit, req.variable_cost_per_unit)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


class DcfRequest(BaseModel):
    projected_cash_flows: list[float]
    discount_rate_pct: float
    terminal_growth_rate_pct: float


@router.post("/dcf")
def dcf_endpoint(req: DcfRequest):
    try:
        return dcf_valuation(req.projected_cash_flows, req.discount_rate_pct, req.terminal_growth_rate_pct)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


class ScenarioIn(BaseModel):
    name: str
    revenue: float
    cost: float
    probability_pct: float = 0.0


class ScenarioAnalysisRequest(BaseModel):
    scenarios: list[ScenarioIn]


@router.post("/scenario-analysis")
def scenario_analysis_endpoint(req: ScenarioAnalysisRequest):
    scenarios = [Scenario(**s.dict()) for s in req.scenarios]
    try:
        return scenario_analysis(scenarios)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
