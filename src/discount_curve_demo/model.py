"""Nelson-Siegel-Svensson curve functions and deterministic fitting."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

_TENOR_PATTERN = re.compile(r"^(?P<value>[1-9][0-9]*)(?P<unit>[WMY])$")


@dataclass(frozen=True)
class FitResult:
    """A fitted NSS model with transparent, comparable error metrics."""

    parameters: tuple[float, float, float, float, float, float]
    rmse_bps: float
    max_abs_error_bps: float
    observations: int


def tenor_to_years(tenor: str) -> float:
    """Convert tenors such as ``2W``, ``6M`` and ``10Y`` into years."""

    match = _TENOR_PATTERN.fullmatch(tenor.strip().upper())
    if not match:
        raise ValueError(f"Unsupported tenor {tenor!r}; expected a positive integer plus W, M or Y")

    value = int(match.group("value"))
    unit = match.group("unit")
    divisors = {"W": 52.0, "M": 12.0, "Y": 1.0}
    return value / divisors[unit]


def _loading(maturities: np.ndarray, tau: float) -> tuple[np.ndarray, np.ndarray]:
    scaled = maturities / tau
    level_slope = -np.expm1(-scaled) / scaled
    curvature = level_slope - np.exp(-scaled)
    return level_slope, curvature


def nss_yield(parameters: Iterable[float], maturities_years: Iterable[float]) -> np.ndarray:
    """Evaluate the standard six-parameter NSS model.

    Rates are represented as decimals: ``0.04`` means four percent.
    """

    values = tuple(float(x) for x in parameters)
    if len(values) != 6 or not np.all(np.isfinite(values)):
        raise ValueError("NSS parameters must contain six finite values")
    beta0, beta1, beta2, beta3, tau1, tau2 = values
    if tau1 <= 0 or tau2 <= 0:
        raise ValueError("NSS decay parameters tau1 and tau2 must be positive")

    maturities = np.asarray(tuple(maturities_years), dtype=float)
    if (
        maturities.ndim != 1
        or len(maturities) == 0
        or not np.all(np.isfinite(maturities))
        or np.any(maturities <= 0)
    ):
        raise ValueError("Maturities must be a non-empty sequence of finite positive values")

    slope1, curvature1 = _loading(maturities, tau1)
    _, curvature2 = _loading(maturities, tau2)
    return beta0 + beta1 * slope1 + beta2 * curvature1 + beta3 * curvature2


def continuous_discount_factors(
    zero_rates: Iterable[float], maturities_years: Iterable[float]
) -> np.ndarray:
    """Convert continuously compounded zero rates into discount factors.

    The public demo uses ``DF(t) = exp(-z(t) * t)``. Rates are decimals and
    maturities are year fractions under the configured day-count denominator.
    """

    rates = np.asarray(tuple(zero_rates), dtype=float)
    maturities = np.asarray(tuple(maturities_years), dtype=float)
    if rates.shape != maturities.shape or rates.ndim != 1:
        raise ValueError("Rates and maturities must be one-dimensional sequences of equal length")
    if not np.all(np.isfinite(rates)) or not np.all(np.isfinite(maturities)):
        raise ValueError("Rates and maturities must be finite")
    if np.any(maturities < 0):
        raise ValueError("Maturities must be non-negative")
    return np.exp(-rates * maturities)


def fit_nss(maturities_years: Iterable[float], observed_rates: Iterable[float]) -> FitResult:
    """Fit NSS with bounded deterministic multi-start least squares."""

    maturities = np.asarray(tuple(maturities_years), dtype=float)
    rates = np.asarray(tuple(observed_rates), dtype=float)
    if maturities.shape != rates.shape or maturities.ndim != 1:
        raise ValueError("Maturities and rates must be one-dimensional sequences of equal length")
    if len(rates) < 6:
        raise ValueError("At least six observations are required for a six-parameter NSS fit")
    if not np.all(np.isfinite(rates)) or not np.all(np.isfinite(maturities)):
        raise ValueError("Inputs must contain finite rates and maturities")
    if np.any(maturities <= 0):
        raise ValueError("Inputs must contain finite rates and positive maturities")
    if len(np.unique(maturities)) != len(maturities):
        raise ValueError("Maturities must be unique within one fitted curve")

    order = np.argsort(maturities)
    maturities = maturities[order]
    rates = rates[order]
    long_rate = float(rates[-1])
    short_spread = float(rates[0] - long_rate)
    starts = (
        (long_rate, short_spread, 0.0, 0.0, 1.0, 3.0),
        (long_rate, short_spread, 0.01, -0.01, 0.5, 5.0),
        (float(np.mean(rates)), short_spread, -0.02, 0.02, 2.0, 10.0),
    )
    lower = np.array((-0.50, -0.75, -0.75, -0.75, 0.02, 0.02))
    upper = np.array((0.75, 0.75, 0.75, 0.75, 40.0, 40.0))

    def residuals(parameters: np.ndarray) -> np.ndarray:
        return (nss_yield(parameters, maturities) - rates) * 10_000.0

    candidates = [
        least_squares(
            residuals,
            np.clip(np.asarray(start, dtype=float), lower, upper),
            bounds=(lower, upper),
            max_nfev=20_000,
        )
        for start in starts
    ]
    successful = [candidate for candidate in candidates if candidate.success]
    if not successful:
        raise RuntimeError("NSS fitting did not converge for any deterministic starting point")

    best = min(successful, key=lambda candidate: float(np.dot(candidate.fun, candidate.fun)))
    errors_bps = residuals(best.x)
    return FitResult(
        parameters=(
            float(best.x[0]),
            float(best.x[1]),
            float(best.x[2]),
            float(best.x[3]),
            float(best.x[4]),
            float(best.x[5]),
        ),
        rmse_bps=float(np.sqrt(np.mean(np.square(errors_bps)))),
        max_abs_error_bps=float(np.max(np.abs(errors_bps))),
        observations=len(rates),
    )
