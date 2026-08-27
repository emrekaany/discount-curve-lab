# Contributing

Small, test-backed improvements are welcome.

1. Use only synthetic or clearly redistributable data.
2. Install the development dependencies with `python -m pip install -e '.[dev]'`.
3. Run `ruff format --check .`, `ruff check .`, `mypy src`, and
   `pytest --cov=discount_curve_demo --cov-branch`.
4. Keep dry-run as the default and place every write behind explicit CLI opt-in.
5. Document modeling assumptions and never describe demo output as financial advice.
