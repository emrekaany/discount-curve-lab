import json
import runpy
import sys
from pathlib import Path

import pytest

from discount_curve_demo.cli import build_parser, main

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "config" / "demo.toml"


def test_parser_defaults_to_dry_run():
    args = build_parser().parse_args([])

    assert args.config == Path("config/demo.toml")
    assert args.write_output is False
    assert args.overwrite is False


def test_main_prints_machine_readable_summary(capsys):
    assert main(["--config", str(CONFIG)]) == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["mode"] == "dry-run"
    assert summary["curve_convention"]["rate_unit"] == "decimal"
    assert summary["curve_convention"]["zero_rate_compounding"] == "continuous"


@pytest.mark.parametrize("module_name", ["discount_curve_demo.cli", "discount_curve_demo.__main__"])
def test_module_entrypoints(module_name, monkeypatch):
    monkeypatch.setattr(sys, "argv", [module_name, "--config", str(CONFIG)])
    monkeypatch.delitem(sys.modules, module_name, raising=False)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module(module_name, run_name="__main__")

    assert exc_info.value.code == 0
