import csv
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import discount_curve_demo.pipeline as pipeline
from discount_curve_demo.model import FitResult
from discount_curve_demo.pipeline import (
    DemoConfig,
    _curve_rows,
    _load_points,
    _output_path,
    load_config,
    run_pipeline,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "data" / "synthetic_market_data.csv"


def make_config(tmp_path: Path, *, horizon_days: int = 10) -> DemoConfig:
    return DemoConfig(
        input_path=FIXTURE,
        output_dir=tmp_path / "output",
        currencies=("EUR", "USD"),
        horizon_days=horizon_days,
        day_count=365,
        liquidity_starts_after_days=3,
    )


def test_demo_config_resolves_paths():
    config = load_config(REPO_ROOT / "config" / "demo.toml")

    assert config.input_path == FIXTURE
    assert config.currencies == ("EUR", "GBP", "TRY", "USD")
    assert config.horizon_days == 10950
    assert config.zero_rate_compounding == "continuous"


def test_dry_run_is_default_and_creates_no_files(tmp_path):
    config = make_config(tmp_path)

    summary = run_pipeline(config)

    assert summary["mode"] == "dry-run"
    assert summary["synthetic_input"] is True
    assert summary["output_files"] == []
    assert not config.output_dir.exists()
    assert summary["currencies"]["EUR"]["generated_rows"] == 10


def test_explicit_write_creates_only_local_csv_outputs(tmp_path):
    config = make_config(tmp_path, horizon_days=7)

    summary = run_pipeline(config, write_output=True)

    assert summary["mode"] == "write-local-csv"
    assert len(summary["output_files"]) == 2
    assert sorted(path.name for path in config.output_dir.iterdir()) == [
        "eur_discount_curve.csv",
        "usd_discount_curve.csv",
    ]
    assert len((config.output_dir / "eur_discount_curve.csv").read_text().splitlines()) == 8

    with (config.output_dir / "eur_discount_curve.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        row = next(csv.DictReader(handle))
    maturity = float(row["maturity_years"])
    for suffix in ("base", "plus_25pct_liquidity", "plus_50pct_liquidity", "plus_100pct_liquidity"):
        zero_rate = float(row[f"zero_rate_{suffix}"])
        factor = float(row[f"discount_factor_{suffix}"])
        assert factor == pytest.approx(np.exp(-zero_rate * maturity), abs=2e-11)

    assert summary["curve_convention"] == {
        "rate_unit": "decimal",
        "zero_rate_compounding": "continuous",
        "discount_factor_formula": "exp(-zero_rate * maturity_years)",
        "day_count_denominator": 365,
    }


def test_existing_output_is_not_overwritten_without_second_opt_in(tmp_path):
    config = make_config(tmp_path)
    run_pipeline(config, write_output=True)

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run_pipeline(config, write_output=True)

    summary = run_pipeline(config, write_output=True, overwrite=True)
    assert summary["mode"] == "write-local-csv"


def test_overwrite_without_write_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="write_output"):
        run_pipeline(make_config(tmp_path), overwrite=True)


def test_later_output_collision_publishes_no_earlier_file(tmp_path):
    config = make_config(tmp_path)
    config.output_dir.mkdir(parents=True)
    existing = config.output_dir / "usd_discount_curve.csv"
    existing.write_text("preserve me\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run_pipeline(config, write_output=True)

    assert existing.read_text(encoding="utf-8") == "preserve me\n"
    assert not (config.output_dir / "eur_discount_curve.csv").exists()


@pytest.mark.parametrize("currency", ["../ESCAPE", "EU", "EURO", "E1R"])
def test_invalid_config_currency_is_rejected(tmp_path, currency):
    config = replace(make_config(tmp_path), currencies=(currency,))

    with pytest.raises(ValueError, match="three uppercase ASCII letters"):
        run_pipeline(config)

    assert not (tmp_path / "ESCAPE_discount_curve.csv").exists()


def test_invalid_compounding_is_rejected(tmp_path):
    config = replace(make_config(tmp_path), zero_rate_compounding="annual")

    with pytest.raises(ValueError, match="continuous"):
        run_pipeline(config)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"currencies": ()}, "non-empty and unique"),
        ({"currencies": ("EUR", "EUR")}, "non-empty and unique"),
        ({"horizon_days": 0}, "horizon_days"),
        ({"day_count": 364}, "day_count"),
        ({"liquidity_starts_after_days": 11}, "liquidity_starts"),
    ],
)
def test_invalid_config_ranges_are_rejected(tmp_path, changes, message):
    config = replace(make_config(tmp_path), **changes)

    with pytest.raises(ValueError, match=message):
        run_pipeline(config)


def test_liquidity_starts_strictly_after_configured_day(tmp_path):
    config = make_config(tmp_path, horizon_days=4)
    risk_free_fit = FitResult((0.03, 0.0, 0.0, 0.0, 1.0, 2.0), 0.0, 0.0, 8)
    liquidity_fit = FitResult((0.01, 0.0, 0.0, 0.0, 1.0, 2.0), 0.0, 0.0, 8)

    rows = _curve_rows(
        config, _load_points(FIXTURE)[0].as_of_date, "EUR", risk_free_fit, liquidity_fit
    )

    assert [float(row["liquidity_spread"]) for row in rows[:3]] == [0.0, 0.0, 0.0]
    assert float(rows[3]["liquidity_spread"]) > 0.0
    assert rows[2]["discount_factor_base"] == rows[2]["discount_factor_plus_100pct_liquidity"]
    assert (
        rows[3]["discount_factor_base"]
        > rows[3]["discount_factor_plus_25pct_liquidity"]
        > rows[3]["discount_factor_plus_50pct_liquidity"]
        > rows[3]["discount_factor_plus_100pct_liquidity"]
    )


def test_input_currency_and_duplicate_points_are_rejected(tmp_path):
    header = "as_of_date,currency,curve_type,tenor,value\n"
    invalid = tmp_path / "invalid.csv"
    invalid.write_text(header + "2026-01-02,../X,risk_free,1Y,0.01\n", encoding="utf-8")
    with pytest.raises(ValueError, match="currency"):
        _load_points(invalid)

    duplicate = tmp_path / "duplicate.csv"
    row = "2026-01-02,EUR,risk_free,1Y,0.01\n"
    duplicate.write_text(header + row + row, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        _load_points(duplicate)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("wrong,columns\n1,2\n", "columns"),
        (
            "as_of_date,currency,curve_type,tenor,value\n2026-01-02,EUR,unknown,1Y,0.01\n",
            "curve_type",
        ),
        (
            "as_of_date,currency,curve_type,tenor,value\n2026-01-02,EUR,risk_free,1Y,nan\n",
            "finite",
        ),
    ],
)
def test_invalid_input_contract_is_rejected(tmp_path, body, message):
    path = tmp_path / "invalid-contract.csv"
    path.write_text(body, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        _load_points(path)


def test_missing_input_file_is_rejected(tmp_path):
    with pytest.raises(FileNotFoundError, match="Input file not found"):
        _load_points(tmp_path / "missing.csv")


def test_empty_input_and_mixed_dates_are_rejected(tmp_path):
    header = "as_of_date,currency,curve_type,tenor,value\n"
    empty = tmp_path / "empty.csv"
    empty.write_text(header, encoding="utf-8")
    with pytest.raises(ValueError, match="no market points"):
        run_pipeline(replace(make_config(tmp_path), input_path=empty))

    mixed = tmp_path / "mixed.csv"
    fixture_text = FIXTURE.read_text(encoding="utf-8")
    mixed.write_text(fixture_text.replace("2026-01-02", "2026-01-03", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="one as_of_date"):
        run_pipeline(replace(make_config(tmp_path), input_path=mixed))


def test_load_config_normalizes_currency_and_defaults_compounding(tmp_path):
    config_path = tmp_path / "demo.toml"
    config_path.write_text(
        """[run]
input_path = "fixture.csv"
output_dir = "output"
currencies = [" eur "]
horizon_days = 10
day_count = 365
liquidity_starts_after_days = 3
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.currencies == ("EUR",)
    assert config.zero_rate_compounding == "continuous"


def test_output_path_has_defence_in_depth(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="three uppercase"):
        _output_path(tmp_path, "../X")

    monkeypatch.setattr(Path, "is_relative_to", lambda self, other: False)
    with pytest.raises(ValueError, match="inside"):
        _output_path(tmp_path, "EUR")


def test_missing_curve_pair_is_rejected(tmp_path):
    config = replace(make_config(tmp_path), currencies=("EUR", "ZZZ"))

    with pytest.raises(ValueError, match="ZZZ/liquidity"):
        run_pipeline(config)


def test_dry_run_is_deterministic(tmp_path):
    first = run_pipeline(make_config(tmp_path))
    second = run_pipeline(make_config(tmp_path))

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_publish_failure_rolls_back_existing_batch(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    run_pipeline(config, write_output=True)
    eur = config.output_dir / "eur_discount_curve.csv"
    usd = config.output_dir / "usd_discount_curve.csv"
    eur.write_text("original eur\n", encoding="utf-8")
    usd.write_text("original usd\n", encoding="utf-8")

    real_replace = pipeline.os.replace
    call_count = 0

    def fail_on_third_replace(source, target):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            raise OSError("simulated publish failure")
        real_replace(source, target)

    monkeypatch.setattr(pipeline.os, "replace", fail_on_third_replace)

    with pytest.raises(OSError, match="simulated"):
        run_pipeline(config, write_output=True, overwrite=True)

    assert eur.read_text(encoding="utf-8") == "original eur\n"
    assert usd.read_text(encoding="utf-8") == "original usd\n"
    assert sorted(path.name for path in config.output_dir.iterdir()) == [
        "eur_discount_curve.csv",
        "usd_discount_curve.csv",
    ]
