import pytest

from app.services.analysis_engine import MAX_IRR_PERIODS, irr


@pytest.mark.parametrize("cash_flows", [[], [100.0, 200.0], [-100.0, -50.0]])
def test_irr_returns_none_when_cash_flows_cannot_have_a_real_investment_return(cash_flows):
    assert irr(cash_flows) is None


def test_irr_calculates_a_valid_return_for_normal_investment_cash_flows():
    result = irr([-100.0, 110.0])

    assert result == pytest.approx(10.0, abs=0.0001)


@pytest.mark.parametrize(
    "cash_flows",
    [
        [float("nan"), 100.0],
        [float("inf"), -100.0],
        [True, -100.0],
        ["100", -100.0],
    ],
)
def test_irr_rejects_non_numeric_or_non_finite_cash_flows(cash_flows):
    with pytest.raises(ValueError, match=r"cash_flows\[0\] must be a finite number"):
        irr(cash_flows)


def test_irr_rejects_non_list_cash_flows():
    with pytest.raises(ValueError, match="cash_flows must be a list"):
        irr((-100.0, 110.0))  # type: ignore[arg-type]


def test_irr_bounds_cash_flow_period_count():
    with pytest.raises(ValueError, match="cannot contain more than"):
        irr([-1.0, 1.0] * (MAX_IRR_PERIODS // 2 + 1))
