"""
Module 6: Financial Analysis — API layer over analysis_engine.py
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator

from app.services.analysis_engine import (
    npv, irr, cagr, break_even, dcf_valuation, Scenario, scenario_analysis,
)

router = APIRouter()


def _reject_boolean_numeric_inputs(values, scalar_fields=(), sequence_fields=()):
    """Prevent Pydantic from coercing JSON booleans into financial numbers."""
    if isinstance(values, dict):
        for field_name in scalar_fields:
            if isinstance(values.get(field_name), bool):
                raise ValueError(f"{field_name} must be numeric, not boolean.")
        for field_name in sequence_fields:
            items = values.get(field_name)
            if isinstance(items, list):
                for index, item in enumerate(items):
                    if isinstance(item, bool):
                        raise ValueError(f"{field_name}[{index}] must be numeric, not boolean.")
    return values


class NpvRequest(BaseModel):
    rate_pct: float
    cash_flows: list[float]

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_inputs(cls, values):
        return _reject_boolean_numeric_inputs(values, ("rate_pct",), ("cash_flows",))


@router.post("/npv")
def npv_endpoint(req: NpvRequest):
    try:
        return {"npv": npv(req.rate_pct, req.cash_flows)}
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


class IrrRequest(BaseModel):
    cash_flows: list[float]

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_cash_flows(cls, values):
        return _reject_boolean_numeric_inputs(values, sequence_fields=("cash_flows",))


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

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_inputs(cls, values):
        return _reject_boolean_numeric_inputs(values, ("beginning_value", "ending_value", "years"))


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

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_inputs(cls, values):
        return _reject_boolean_numeric_inputs(values, ("fixed_costs", "price_per_unit", "variable_cost_per_unit"))


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

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_inputs(cls, values):
        return _reject_boolean_numeric_inputs(
            values,
            ("discount_rate_pct", "terminal_growth_rate_pct"),
            ("projected_cash_flows",),
        )


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

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_inputs(cls, values):
        return _reject_boolean_numeric_inputs(values, ("revenue", "cost", "probability_pct"))


class ScenarioAnalysisRequest(BaseModel):
    scenarios: list[ScenarioIn]


@router.post("/scenario-analysis")
def scenario_analysis_endpoint(req: ScenarioAnalysisRequest):
    scenarios = [Scenario(**s.dict()) for s in req.scenarios]
    try:
        return scenario_analysis(scenarios)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
