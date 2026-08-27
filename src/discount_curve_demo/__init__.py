"""Synthetic, side-effect-safe discount-curve demo."""

from .model import FitResult, continuous_discount_factors, fit_nss, nss_yield, tenor_to_years
from .pipeline import DemoConfig, load_config, run_pipeline

__all__ = [
    "DemoConfig",
    "FitResult",
    "continuous_discount_factors",
    "fit_nss",
    "load_config",
    "nss_yield",
    "run_pipeline",
    "tenor_to_years",
]
