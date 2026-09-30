# ADR-0002: Separate historical reproduction from reviewed rules

- **Status:** Accepted
- **Date:** 2026-09-21

## Context

Some validation and consensus rules were tightened after the report workflow had been
established. Changing those rules in place would make historical reproduction ambiguous and
could lead to corrected outputs being presented as report results.

## Decision

Provide two explicit, mutually exclusive profiles:

- `report-reproduction` preserves the report's training periods, domain-wide monthly FRP,
  sampling limits, feature/model choices and historical validation/figure behavior.
- `reviewed` uses strict unit handling, centralized final regions, at least two satellites for a
  mapped median, all three satellites for strong agreement, neutral anomalies at `|z| < 0.25`
  and the regional IQR threshold at the 33rd percentile.

Profile identity is mandatory in configuration, output directories and provenance manifests.

## Consequences

- Historical and reviewed outputs cannot overwrite one another.
- A reviewed result must never be labelled as a direct reproduction of the report.
- Unknown units and unexpected temporal gaps fail closed.
- Scientific comparisons must state which profile generated every table, metric and figure.
- Future methodological changes require a new profile or a new ADR rather than silently
  changing either established profile.
