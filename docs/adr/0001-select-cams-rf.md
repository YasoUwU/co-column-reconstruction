# ADR-0001: Select CAMS-RF as the primary reconstructed product

- **Status:** Accepted for the report-reproduction profile
- **Date:** 2026-09-21

## Context

The study compared raw reanalysis fields, statistical bias corrections and machine-learning
models against IASI, followed by a multi-satellite assessment with IASI, TROPOMI and MOPITT.
The intended product must provide a spatially complete daily field while retaining regional and
intra-seasonal CO variability.

Sensitivity experiments selected the five-year training window W5 (2013-2017) and feature set
ABCD using HistGradientBoosting. Those choices were then transferred to the final Random
Forest. The experiment did not perform a joint Random-Forest-by-window-by-feature-set search.

## Decision

Use the CAMS-based Random Forest reconstruction, named CAMS-RF, as the primary final product.
Train on 2013-2017 with the ABCD features and evaluate internally on 2018-2024. Preserve the
log-ratio target, source-times-exponential reconstruction and ratio clipping `[0.2, 5.0]` in the
report-reproduction profile.

## Consequences

- CAMS-RF is the supported basis for regional and intra-seasonal interpretation.
- Selection evidence and transferred hyperparameter choices must be stated transparently.
- Comparisons against IASI are not independent because IASI is the training target.
- Comparisons against MOPITT are partly dependent because MOPITT is assimilated by CAMS.
- TROPOMI is the most independent satellite comparison in this workflow.
- Very localized daily extremes and areas of strong satellite disagreement remain limitations;
  the product must not be described as ground truth.
