# Model references

The implementation and public claims use these primary technical references:

- [ECB — Euro area yield curve technical notes](https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_area_yield_curves/shared/pdf/technical_notes.pdf): Nelson-Siegel-Svensson spot-rate specification and parameter interpretation.
- [QuantLib — Interest-rate curves](https://www.quantlib.org/slides/rate-curves.pdf): continuously compounded zero-rate relationship `DF(t) = exp(-z(t) × t)`.
- [OpenGamma Strata — ZeroRateDiscountFactors](https://strata.opengamma.io/apidocs/com/opengamma/strata/pricer/ZeroRateDiscountFactors.html): explicit distinction between zero-rate curves and discount factors.

This repository is an educational implementation, not a reproduction or endorsement of any
reference implementation.
