# CO Column Reconstruction

Reproducible reconstruction of daily total-column carbon monoxide (CO) across the South
America-Atlantic-southern Africa transport corridor. The pipeline grids IASI observations,
derives daily MERRA-2 columns, prepares CAMS EAC4 fields, trains bias-correction models and
evaluates the selected CAMS-RF product against IASI, TROPOMI and MOPITT.

> **Release status:** public source-code release under the BSD 3-Clause License. Scientific
> datasets, trained models, derived products and report figures are not distributed.

## What is in this repository

The canonical workflow is:

1. uncertainty-weighted gridding of IASI Level-2 CO;
2. daily MERRA-2 total-column integration from eight 3-hourly fields;
3. acquisition and normalization of CAMS EAC4 total-column CO;
4. construction of a common IASI-CAMS-MERRA-2 grid;
5. statistical and machine-learning benchmark;
6. final Random Forest training and application;
7. multi-satellite validation for 2023 and 2024; and
8. generation of the scientific figures used by the report workflow.

The repository contains code, configuration templates, tests and documentation only. It does
**not** redistribute source observations, reanalysis fields, trained models, generated NetCDF
files or figures. See [DATA_SOURCES.md](DATA_SOURCES.md) before obtaining any input data.

## Scientific profiles

Every run must select one of two named profiles. Outputs, caches and provenance manifests are
automatically written below a profile-named directory and must never be presented as
interchangeable.

### `report-reproduction`

This profile preserves the historical choices used for the internship report:

- August-September-October (ASO), 2007-2024;
- domain-wide monthly fire radiative power (FRP);
- final training period 2013-2017 and evaluation period 2018-2024;
- feature set `ABCD`, log-ratio target and reconstruction from the source field;
- ratio clipping to `[0.2, 5.0]`;
- 1,000 sampled pixels per day and at most 600,000 training observations; and
- the historical figure and validation rules.

The five-year window (`W5`) and feature set `ABCD` were selected in experiments using
HistGradientBoosting and then transferred to the final Random Forest. They were **not** chosen
through a joint Random-Forest-by-window-by-feature-set search. This distinction is part of the
scientific provenance and must remain visible in derived publications.

### `reviewed`

This profile keeps the same scientific objective while applying stricter review rules:

- only explicit, supported CO units are accepted;
- final region definitions are centralized in configuration;
- a mapped satellite median requires at least two available satellites;
- strong agreement requires all three satellites;
- a standardized anomaly is neutral when `|z| < 0.25`; and
- the regional IQR threshold is the 33rd percentile.

Results from this profile are reviewed results, not historical report reproductions.

## Installation

Python 3.11 is the reference runtime; Python 3.10 is also tested.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[workflow,dev]"
```

An equivalent Conda environment is provided in `environment.yml`.

## Configuration and credentials

Start from a tracked configuration and keep machine-specific paths in an ignored local file:

```bash
cp configs/example.yaml configs/local.yaml
```

Do not put credentials in YAML, command-line arguments, source code or notebooks. CAMS access
uses the standard CDS/ADS client configuration. NASA Earthdata access must use a protected
`.netrc`, environment variables supported by the relevant command, or an interactive masked
prompt. Password command-line options are intentionally unsupported.

MERRA-2 and MOPITT downloads require a free, personal NASA Earthdata Login account. Each user
must create and activate their own account; credentials are never supplied by this repository.
Follow [the Earthdata access setup](docs/earthdata-access.md) before downloading either product.

The internal CO unit is `mol/cm²`. Input conversion accepts exactly `mol/m²`, `mol/cm²`,
`kg/m²` and `molecules/cm²`; unknown units and informal aliases fail closed rather than being
guessed.

## Running the workflow

Inspect the installed command and any stage before execution:

```bash
co-pipeline --help
co-pipeline run --help
```

Run the full selected profile with a local configuration:

```bash
co-pipeline run --config configs/local.yaml
```

The same modules are orchestrated by `Snakefile`; Snakemake does not contain a separate
scientific implementation.

```bash
snakemake -s workflows/Snakefile --configfile configs/local.yaml --cores 4
```

Available CLI stages are `grid-iasi`, `merra2-daily`, `download-cams`, `common-grid`,
`benchmark`, `train`, `apply`, `download-validation`, `validation-grid`, `validate`,
`figures` and `run`.

Each execution writes a JSON provenance manifest with the normalized configuration,
SHA-256 file fingerprints, code and environment information, inputs, outputs, expected missing
dates and selected model metadata.

## Expected IASI gaps

There are 1,656 calendar days in ASO 2007-2024. The archive used for the report contains 1,642
daily IASI products. Exactly these 14 missing dates are accepted:

```text
2007-08-03  2007-09-09  2007-09-18  2007-09-19
2008-10-27  2009-10-01
2010-08-31  2010-09-01  2010-09-02  2010-09-03
2011-10-23  2011-10-24
2013-08-02  2013-08-09
```

Any additional missing day is an error, not a silent skip.

## Validation limits

The multi-instrument assessment is only partially independent. IASI is the training target,
and MOPITT observations are assimilated by CAMS EAC4. TROPOMI is the most independent of the
three satellite comparisons used here. Agreement with the satellite median should therefore
not be interpreted as validation against three fully independent references.

## Quality checks

```bash
ruff check .
ruff format --check .
pytest
python -m build
```

Continuous integration runs without downloading scientific data. Tests use small synthetic
arrays, including a two-day 3 x 4 end-to-end fixture. Reproduction comparisons use numerical
tables and metrics rather than PNG pixel equality.

## Citation, contribution and release

Use [CITATION.cff](CITATION.cff) to cite this software. The code is distributed under the
[BSD 3-Clause License](LICENSE). Scientific decisions are recorded under
[docs/adr](docs/adr), and release safeguards are listed in
[docs/release-checklist.md](docs/release-checklist.md).
