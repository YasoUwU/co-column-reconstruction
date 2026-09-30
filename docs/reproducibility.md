# Reproducibility guide

## Clean-room execution

1. Clone the private repository into an empty directory.
2. Create Python 3.11 environment from `environment.yml` or install `.[workflow,dev]`.
3. Obtain inputs directly from the providers in [DATA_SOURCES.md](../DATA_SOURCES.md).
4. Copy `configs/example.yaml` to an ignored local configuration and set local paths.
5. Run the synthetic tests before processing external data.
6. Execute one profile with either `co-pipeline run` or Snakemake.
7. Retain the generated provenance manifest beside the outputs.

Do not copy a local research directory wholesale into the repository. The curated repository is
built from an allowlist; temporary files, legacy stages, reports, applications and unrelated
projects are out of scope.

## Expected checks

- unit conversion for all four supported input units;
- uncertainty-weighted IASI gridding;
- MERRA-2 integration across eight time steps;
- expected common-grid coordinates and dimensions;
- log-ratio target and positive reconstruction;
- deterministic sampling with seed 42;
- no temporal leakage between training and evaluation;
- QM and QDM serialization/round-trip behavior;
- coverage and satellite-consensus rules; and
- a network-free two-day, 3 x 4 synthetic workflow.

## Historical parity

Local parity checks may read the protected historical archive but must never copy it into Git.
Use the following tolerances:

| Comparison | Tolerance |
| --- | --- |
| Preprocessing arrays | `rtol=1e-10` |
| Predictions | `rtol=1e-6` |
| Correlation and R-squared | absolute tolerance `1e-6` |
| Bias and RMSE | relative tolerance `0.1%` |

Compare figure source tables and reported metrics, not rendered PNG pixels. A complete report
reproduction must produce 1,642 ASO days and report exactly the 14 documented IASI gaps.

## Provenance manifest

Every stage manifest identifies the profile and contains a path-redacted normalized
configuration, code revision when available, creation time, Python and package versions,
SHA-256 checksums for inputs and outputs, expected gaps and model metadata. Manifests must not
include credentials or machine-specific paths or secrets.
