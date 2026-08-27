from types import SimpleNamespace

import numpy as np
import pytest

import discount_curve_demo.model as model
from discount_curve_demo.model import (
    continuous_discount_factors,
    fit_nss,
    nss_yield,
    tenor_to_years,
)


@pytest.mark.parametrize(
    ("tenor", "expected"),
    [("2W", 2 / 52), ("6M", 0.5), ("10Y", 10.0), (" 3m ", 0.25)],
)
def test_tenor_to_years(tenor, expected):
    assert tenor_to_years(tenor) == pytest.approx(expected)


@pytest.mark.parametrize("tenor", ["0Y", "1D", "M6", "", "1.5Y"])
def test_tenor_to_years_rejects_unsupported_values(tenor):
    with pytest.raises(ValueError):
        tenor_to_years(tenor)


def test_fit_nss_recovers_a_synthetic_curve():
    maturities = np.array([1 / 12, 0.25, 0.5, 1, 2, 5, 10, 20, 30])
    known_parameters = (0.035, 0.012, -0.020, 0.010, 1.2, 4.5)
    observed = nss_yield(known_parameters, maturities)

    fit = fit_nss(maturities, observed)

    assert fit.observations == len(maturities)
    assert fit.rmse_bps < 0.01
    assert fit.max_abs_error_bps < 0.02


def test_fit_nss_requires_enough_observations():
    with pytest.raises(ValueError, match="At least six"):
        fit_nss([1, 2, 3], [0.01, 0.02, 0.03])


def test_continuous_discount_factors_uses_documented_formula():
    factors = continuous_discount_factors([0.10, 0.05, -0.01], [0.0, 2.0, 1.0])

    assert factors == pytest.approx([1.0, np.exp(-0.10), np.exp(0.01)])


@pytest.mark.parametrize(
    ("rates", "maturities", "message"),
    [
        ([0.01], [1.0, 2.0], "equal length"),
        ([np.nan], [1.0], "finite"),
        ([0.01], [np.inf], "finite"),
        ([0.01], [-1.0], "non-negative"),
    ],
)
def test_continuous_discount_factors_rejects_invalid_inputs(rates, maturities, message):
    with pytest.raises(ValueError, match=message):
        continuous_discount_factors(rates, maturities)


@pytest.mark.parametrize(
    ("parameters", "maturities", "message"),
    [
        ((0.01,) * 5, [1.0], "six finite"),
        ((0.01, 0.01, 0.01, 0.01, np.nan, 2.0), [1.0], "six finite"),
        ((0.01, 0.01, 0.01, 0.01, 0.0, 2.0), [1.0], "positive"),
        ((0.01, 0.01, 0.01, 0.01, 1.0, 2.0), [np.inf], "finite positive"),
    ],
)
def test_nss_yield_rejects_invalid_inputs(parameters, maturities, message):
    with pytest.raises(ValueError, match=message):
        nss_yield(parameters, maturities)


@pytest.mark.parametrize(
    ("maturities", "rates", "message"),
    [
        ([1, 2, 3, 4, 5, 6], [0.01] * 5, "equal length"),
        ([1, 2, 3, 4, 5, 6], [0.01, 0.02, 0.03, 0.04, 0.05, np.inf], "finite"),
        ([0, 1, 2, 3, 4, 5], [0.01] * 6, "positive maturities"),
        ([1, 1, 2, 3, 4, 5], [0.01] * 6, "unique"),
    ],
)
def test_fit_nss_rejects_invalid_inputs(maturities, rates, message):
    with pytest.raises(ValueError, match=message):
        fit_nss(maturities, rates)


def test_fit_nss_reports_non_convergence(monkeypatch):
    monkeypatch.setattr(
        model,
        "least_squares",
        lambda *args, **kwargs: SimpleNamespace(success=False),
    )

    with pytest.raises(RuntimeError, match="did not converge"):
        fit_nss([1, 2, 3, 4, 5, 6], [0.01, 0.012, 0.014, 0.016, 0.018, 0.02])
