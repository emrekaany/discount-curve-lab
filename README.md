# Synthetic Discount Curve Lab

<p align="center">
  <strong>64 fictional observations → 8 NSS fits → 43,800 daily zero-rate + discount-factor rows.</strong>
</p>

![Synthetic discount-curve generation with zero rates, discount factors, fit evidence and explicit output controls](assets/hero.png)

<p align="center">
  <a href="https://github.com/emrekaany/discount-curve-lab/actions/workflows/ci.yml"><img src="https://github.com/emrekaany/discount-curve-lab/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB" alt="Python 3.11 or newer">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-64748b" alt="MIT license"></a>
  <a href="docs/PROVENANCE.md"><img src="https://img.shields.io/badge/data-100%25%20synthetic-7c3aed" alt="100 percent synthetic data"></a>
</p>

<p align="center">
  <strong>Synthetic · Local only · Dry-run first · No credentials · No network</strong><br>
  <a href="#run-it"><strong>Run the free demo</strong></a> ·
  <a href="https://www.linkedin.com/in/emrekaany/"><strong>Discuss production engineering</strong></a>
</p>

## Run it

From the repository root (Python 3.11+):

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install .
discount-curve-demo --config config/demo.toml
```

The default command prints JSON fit evidence and writes nothing. Local CSV creation requires `--write-output`; replacing existing files also requires `--overwrite`.

![Verified evidence from the checked-in synthetic fixture](assets/evidence-strip.png)

## What you get

For base, +25%, +50% and +100% liquidity-spread scenarios:

`NSS zero rate z(t)` → `discount factor DF(t) = exp(-z(t) × t)`

Rates are decimals, compounding is continuous and year fractions use the configured 365-day denominator.

## From demo to governed production

![The free local demo leading to separately scoped production data engineering](assets/production-path.png)

Need a controlled market-data or curve pipeline?

**Data contracts · approved source adapters · approval gates · reconciliation · lineage · observability · deployment**

<p align="center">
  <a href="https://www.linkedin.com/in/emrekaany/"><img src="https://img.shields.io/badge/Discuss-a%20non--sensitive%20use%20case-f59e0b?style=for-the-badge" alt="Discuss a non-sensitive production use case on LinkedIn"></a>
</p>

> Educational synthetic demo—not valuation, trading or regulatory software. It does not bootstrap instruments or claim arbitrage-free calibration. Liquidity beyond 10 years is NSS extrapolation.

[Architecture](docs/ARCHITECTURE.md) · [Model references](docs/MODEL_REFERENCES.md) · [Provenance](docs/PROVENANCE.md) · [Public trust](docs/PUBLICATION_SAFETY.md) · [Security](SECURITY.md) · [MIT License](LICENSE)
