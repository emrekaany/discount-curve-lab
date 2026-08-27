"""Command-line entrypoint for the discount-curve demo."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .pipeline import load_config, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate NSS zero rates and continuously compounded discount factors "
            "from local synthetic data. Dry-run is the default."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/demo.toml"),
        help="Path to a local TOML config (default: config/demo.toml)",
    )
    parser.add_argument(
        "--write-output",
        action="store_true",
        help="Explicitly allow local CSV creation in the configured output directory",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing local CSV output; requires --write-output",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_pipeline(
        load_config(args.config),
        write_output=args.write_output,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
