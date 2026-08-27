"""Validated, dry-run-first pipeline for the synthetic discount-curve demo."""

from __future__ import annotations

import csv
import os
import re
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from .model import (
    FitResult,
    continuous_discount_factors,
    fit_nss,
    nss_yield,
    tenor_to_years,
)

_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class DemoConfig:
    input_path: Path
    output_dir: Path
    currencies: tuple[str, ...]
    horizon_days: int
    day_count: int
    liquidity_starts_after_days: int
    zero_rate_compounding: str = "continuous"


@dataclass(frozen=True)
class MarketPoint:
    as_of_date: date
    currency: str
    curve_type: str
    maturity_years: float
    value: float


def _validate_config(config: DemoConfig) -> None:
    if not config.currencies or len(set(config.currencies)) != len(config.currencies):
        raise ValueError("Config currencies must be non-empty and unique")
    if any(_CURRENCY_PATTERN.fullmatch(currency) is None for currency in config.currencies):
        raise ValueError("Config currencies must use three uppercase ASCII letters")
    if not 1 <= config.horizon_days <= 30 * 366:
        raise ValueError("horizon_days must be between 1 and 10980")
    if config.day_count not in {360, 365, 366}:
        raise ValueError("day_count must be 360, 365 or 366")
    if not 0 <= config.liquidity_starts_after_days <= config.horizon_days:
        raise ValueError("liquidity_starts_after_days must fall inside the horizon")
    if config.zero_rate_compounding != "continuous":
        raise ValueError("zero_rate_compounding must be continuous")


def load_config(path: str | Path) -> DemoConfig:
    """Load a local TOML configuration; connection settings are intentionally unsupported."""

    config_path = Path(path).expanduser().resolve()
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle).get("run", {})

    base = config_path.parent
    currencies = tuple(str(value).strip().upper() for value in raw.get("currencies", ()))
    config = DemoConfig(
        input_path=(base / str(raw["input_path"])).resolve(),
        output_dir=(base / str(raw["output_dir"])).resolve(),
        currencies=currencies,
        horizon_days=int(raw["horizon_days"]),
        day_count=int(raw["day_count"]),
        liquidity_starts_after_days=int(raw["liquidity_starts_after_days"]),
        zero_rate_compounding=str(raw.get("zero_rate_compounding", "continuous")).strip().lower(),
    )
    _validate_config(config)
    return config


def _load_points(path: Path) -> list[MarketPoint]:
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    required = {"as_of_date", "currency", "curve_type", "tenor", "value"}
    points: list[MarketPoint] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != required:
            raise ValueError(f"Input columns must be exactly: {', '.join(sorted(required))}")
        for row_number, row in enumerate(reader, start=2):
            try:
                curve_type = row["curve_type"].strip().lower()
                if curve_type not in {"risk_free", "liquidity"}:
                    raise ValueError("curve_type must be risk_free or liquidity")
                value = float(row["value"])
                if not np.isfinite(value):
                    raise ValueError("value must be finite")
                currency = row["currency"].strip().upper()
                if _CURRENCY_PATTERN.fullmatch(currency) is None:
                    raise ValueError("currency must use three uppercase ASCII letters")
                points.append(
                    MarketPoint(
                        as_of_date=date.fromisoformat(row["as_of_date"]),
                        currency=currency,
                        curve_type=curve_type,
                        maturity_years=tenor_to_years(row["tenor"]),
                        value=value,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid input row {row_number}: {exc}") from exc

    point_keys = [
        (point.as_of_date, point.currency, point.curve_type, point.maturity_years)
        for point in points
    ]
    if len(point_keys) != len(set(point_keys)):
        raise ValueError("Input contains duplicate date, currency, curve type and maturity points")
    return points


def _fit(points: list[MarketPoint], currency: str, curve_type: str) -> FitResult:
    selected = [
        point for point in points if point.currency == currency and point.curve_type == curve_type
    ]
    return fit_nss(
        (point.maturity_years for point in selected),
        (point.value for point in selected),
    )


def _curve_rows(
    config: DemoConfig,
    as_of_date: date,
    currency: str,
    risk_free_fit: FitResult,
    liquidity_fit: FitResult,
) -> list[dict[str, str | int | float]]:
    days = np.arange(1, config.horizon_days + 1, dtype=float)
    maturities = days / config.day_count
    risk_free = nss_yield(risk_free_fit.parameters, maturities)
    liquidity = np.maximum(nss_yield(liquidity_fit.parameters, maturities), 0.0)
    liquidity[days <= config.liquidity_starts_after_days] = 0.0

    published_maturities = np.round(maturities, 10)
    zero_rate_base = np.round(risk_free, 10)
    zero_rate_plus_25 = np.round(risk_free + 0.25 * liquidity, 10)
    zero_rate_plus_50 = np.round(risk_free + 0.50 * liquidity, 10)
    zero_rate_plus_100 = np.round(risk_free + liquidity, 10)
    discount_factor_base = continuous_discount_factors(zero_rate_base, published_maturities)
    discount_factor_plus_25 = continuous_discount_factors(zero_rate_plus_25, published_maturities)
    discount_factor_plus_50 = continuous_discount_factors(zero_rate_plus_50, published_maturities)
    discount_factor_plus_100 = continuous_discount_factors(zero_rate_plus_100, published_maturities)

    rows: list[dict[str, str | int | float]] = []
    for index, maturity_days in enumerate(days.astype(int)):
        base = float(zero_rate_base[index])
        premium = float(liquidity[index])
        rows.append(
            {
                "as_of_date": as_of_date.isoformat(),
                "currency": currency,
                "maturity_days": maturity_days,
                "maturity_years": float(published_maturities[index]),
                "risk_free_zero_rate": round(base, 10),
                "liquidity_spread": round(premium, 10),
                "zero_rate_base": round(base, 10),
                "zero_rate_plus_25pct_liquidity": round(float(zero_rate_plus_25[index]), 10),
                "zero_rate_plus_50pct_liquidity": round(float(zero_rate_plus_50[index]), 10),
                "zero_rate_plus_100pct_liquidity": round(float(zero_rate_plus_100[index]), 10),
                "discount_factor_base": round(float(discount_factor_base[index]), 12),
                "discount_factor_plus_25pct_liquidity": round(
                    float(discount_factor_plus_25[index]), 12
                ),
                "discount_factor_plus_50pct_liquidity": round(
                    float(discount_factor_plus_50[index]), 12
                ),
                "discount_factor_plus_100pct_liquidity": round(
                    float(discount_factor_plus_100[index]), 12
                ),
            }
        )
    return rows


def _output_path(output_dir: Path, currency: str) -> Path:
    if _CURRENCY_PATTERN.fullmatch(currency) is None:
        raise ValueError("currency must use three uppercase ASCII letters")
    output_root = output_dir.expanduser().resolve()
    path = (output_root / f"{currency.lower()}_discount_curve.csv").resolve()
    if not path.is_relative_to(output_root):
        raise ValueError("Output path must stay inside the configured output directory")
    return path


def _stage_rows(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return temporary_path


def _publish_rows(plans: list[tuple[Path, list[dict[str, Any]]]], *, overwrite: bool) -> None:
    existing = [path for path, _ in plans if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing output: {existing[0]}")

    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        for path, rows in plans:
            staged[path] = _stage_rows(path, rows)

        for path, _ in plans:
            if path.exists():
                with tempfile.NamedTemporaryFile(
                    dir=path.parent,
                    prefix=f".{path.name}.",
                    suffix=".backup",
                    delete=False,
                ) as handle:
                    backup = Path(handle.name)
                backup.unlink()
                os.replace(path, backup)
                backups[path] = backup
            os.replace(staged[path], path)
            published.append(path)
    except Exception:
        for path in reversed(published):
            path.unlink(missing_ok=True)
        for path, backup in backups.items():
            os.replace(backup, path)
        raise
    finally:
        for temporary_path in staged.values():
            temporary_path.unlink(missing_ok=True)
        for backup in backups.values():
            backup.unlink(missing_ok=True)


def run_pipeline(
    config: DemoConfig,
    *,
    write_output: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Fit and evaluate curves; write local CSV files only with explicit opt-in."""

    if overwrite and not write_output:
        raise ValueError("overwrite is valid only when write_output is enabled")
    _validate_config(config)

    points = _load_points(config.input_path)
    if not points:
        raise ValueError("Input contains no market points")
    as_of_dates = {point.as_of_date for point in points}
    if len(as_of_dates) != 1:
        raise ValueError("All synthetic points must share one as_of_date")
    as_of_date = as_of_dates.pop()

    available_curves = {(point.currency, point.curve_type) for point in points}
    required_curves = {
        (currency, curve_type)
        for currency in config.currencies
        for curve_type in ("risk_free", "liquidity")
    }
    missing_curves = sorted(required_curves - available_curves)
    if missing_curves:
        formatted = ", ".join(f"{currency}/{curve_type}" for currency, curve_type in missing_curves)
        raise ValueError(f"Input is missing configured curve samples: {formatted}")

    summaries: dict[str, Any] = {}
    plans: list[tuple[Path, list[dict[str, Any]]]] = []
    for currency in config.currencies:
        risk_free_fit = _fit(points, currency, "risk_free")
        liquidity_fit = _fit(points, currency, "liquidity")
        rows = _curve_rows(config, as_of_date, currency, risk_free_fit, liquidity_fit)
        output_path = _output_path(config.output_dir, currency)
        if write_output:
            plans.append((output_path, rows))
        summaries[currency] = {
            "generated_rows": len(rows),
            "risk_free_fit": asdict(risk_free_fit),
            "liquidity_fit": asdict(liquidity_fit),
        }

    if write_output:
        _publish_rows(plans, overwrite=overwrite)

    return {
        "mode": "write-local-csv" if write_output else "dry-run",
        "synthetic_input": True,
        "as_of_date": as_of_date.isoformat(),
        "input_rows": len(points),
        "curve_convention": {
            "rate_unit": "decimal",
            "zero_rate_compounding": config.zero_rate_compounding,
            "discount_factor_formula": "exp(-zero_rate * maturity_years)",
            "day_count_denominator": config.day_count,
        },
        "currencies": summaries,
        "output_files": [str(path) for path, _ in plans] if write_output else [],
    }
