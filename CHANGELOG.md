# Changelog

All notable changes to this project will be documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project intends to use
[Semantic Versioning](https://semver.org/) after its first approved release.

## [Unreleased]

## [0.1.0] - 2026-09-30

### Added

- Curated, installable Python package for the canonical CO reconstruction workflow.
- A single `co-pipeline` command and a Snakemake workflow backed by the same modules.
- Separate `report-reproduction` and `reviewed` scientific profiles.
- Strict CO unit conversion with `mol/cm2` as the internal unit.
- Run-level JSON provenance manifests with SHA-256 fingerprints.
- Synthetic unit and integration tests that do not require third-party scientific data.
- Security, data-governance and source-only publication checks.

### Changed

- The active MERRA-2 path uses a true daily mean of eight 3-hourly columns rather than the
  historical overpass-time experiment.
- Machine-specific paths are replaced by configuration-driven inputs and outputs.
- Version history is recorded here instead of in source-code comments.

### Security

- Credentials are no longer accepted through source constants or password command-line
  options. Any credential previously exposed in a local source tree must be revoked before the
  first commit or push.

## Release policy

Releases contain source code, documentation and synthetic tests only. Historical experimental
scripts, local research artifacts, scientific datasets, trained models and derived outputs are
not part of the public package history.
