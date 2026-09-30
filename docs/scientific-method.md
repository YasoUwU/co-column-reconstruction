# Scientific method and invariants

## Domain and time

The canonical analysis covers the South America-Atlantic-southern Africa corridor on the
configured common grid during August, September and October. The report period is 2007-2024.
Training uses 2013-2017 and held-out internal evaluation uses 2018-2024.

The expected ASO archive comprises 1,642 IASI days. The only allowed missing dates are:

- 2007-08-03, 2007-09-09, 2007-09-18, 2007-09-19;
- 2008-10-27 and 2009-10-01;
- 2010-08-31, 2010-09-01, 2010-09-02, 2010-09-03;
- 2011-10-23 and 2011-10-24; and
- 2013-08-02 and 2013-08-09.

Any other gap is fatal unless a new, reviewed profile explicitly records a justified archive
change.

## Processing invariants

- IASI Level-2 observations are restricted to `retrieval_quality_flag == 2`. Their documented
  relative error is converted to an absolute uncertainty before inverse-variance aggregation;
  files without a total column use the historical partial-column fallback.
- The active MERRA-2 product is the mean of eight native three-hourly integrated columns. It is
  calculated from the CO molar mixing ratio, pressure thickness and dry-air molar mass. It is
  not the legacy field interpolated to an IASI overpass time.
- CAMS daily fields are means of exactly eight native three-hourly fields; nearest-day
  substitution is forbidden.
- The internal CO unit is `mol/cm²`; conversion is explicit and unknown units are rejected.
- The machine-learning target is `log(CO_IASI / CO_source)`.
- Reconstruction is `CO_source * exp(predicted_log_ratio)` and is therefore positive for a
  positive source field.
- The configured correction ratio is clipped to `[0.2, 5.0]`.
- Random sampling uses seed 42.
- LS, QM and QDM are calibrated cell by cell, with pooled global parameters only for cells that
  do not meet the configured minimum sample count.

## Features and model selection

`report-reproduction` uses monthly FRP aggregated over the entire study domain. It does not
silently replace this with pixel-level or regional FRP. Its final setup uses the five-year
training window W5 and feature set ABCD.

W5 and ABCD were selected from sensitivity experiments run with HistGradientBoosting, then
transferred to the final Random Forest. This is a staged selection, not a joint optimization of
Random Forest, training window and feature set. See
[ADR-0001](adr/0001-select-cams-rf.md).

## Validation interpretation

IASI, TROPOMI and MOPITT are not three fully independent references:

- IASI is the training target and is therefore an internal or target-product comparison;
- MOPITT observations are assimilated in CAMS EAC4, so the CAMS-based reconstruction and
  MOPITT are not fully independent; and
- TROPOMI is the most independent comparison used by this workflow.

The satellite median is a robust comparison construct, not ground truth. The reviewed profile
requires two available satellites for a mapped median and all three for strong-agreement days.
For the agreement classification, daily regional means are standardized separately by
instrument, year and region. The daily inter-satellite IQR is then compared with the 33rd
percentile of that region-year's daily IQR distribution. Strong agreement requires three
convergent non-neutral signs and an IQR at or below that threshold. Pixel-scale extremes and
regions with strong instrument disagreement require particular care.
