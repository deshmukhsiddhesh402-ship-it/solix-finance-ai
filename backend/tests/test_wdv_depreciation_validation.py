import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.accounting_engine import wdv_depreciation_schedule


def test_wdv_valid_schedule_remains_compatible():
    schedule = wdv_depreciation_schedule(100000, 20, 2)
    assert schedule == [
        {"year": 1, "depreciation": 20000.0, "closing_wdv": 80000.0},
        {"year": 2, "depreciation": 16000.0, "closing_wdv": 64000.0},
    ]


def test_wdv_rejects_non_numeric_or_boolean_cost_and_rate():
    for value in (True, False, None, "100000", object(), math.nan, math.inf, -math.inf):
        try:
            wdv_depreciation_schedule(value, 20, 2)
        except ValueError:
            pass
        else:
            raise AssertionError(f"cost accepted invalid value: {value!r}")
        try:
            wdv_depreciation_schedule(100000, value, 2)
        except ValueError:
            pass
        else:
            raise AssertionError(f"rate accepted invalid value: {value!r}")


def test_wdv_rejects_non_integer_years():
    for years in (True, False, 0, -1, 1.5, "2", None):
        try:
            wdv_depreciation_schedule(100000, 20, years)
        except ValueError:
            pass
        else:
            raise AssertionError(f"years accepted invalid value: {years!r}")
