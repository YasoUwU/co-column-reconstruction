# Public source release checklist

A release is blocked until every item is explicitly reviewed.

## Credentials and personal information

- [x] Revoke every credential that appeared in any local source file, even if the file will not
  be committed.
- [x] Confirm that no password, token, cookie, `.netrc`, `.env`, CDS configuration or private
  key is tracked.
- [x] Confirm that no command accepts or records a plaintext password argument.
- [x] Scan the working tree and full new Git history with a maintained secret scanner.
- [x] Confirm that no personal filesystem path, account name or private address remains.

## Scientific data and artifacts

- [x] Confirm that raw data, subsets, derived NetCDF/HDF files, models, figures, logs and caches
  are absent.
- [x] Confirm that no file prohibited by `.gitignore` was force-added.
- [x] Review every tracked file larger than 10 MB; the expected count is zero.
- [x] Recheck provider terms for every source in `DATA_SOURCES.md`.
- [x] Keep Git LFS disabled; a large scientific artifact belongs in an approved data repository,
  not in this source repository.

## Scientific and software quality

- [x] Run lint, format check, tests, coverage and package build on Python 3.10 and 3.11.
- [x] Run the network-free synthetic workflow on Windows and Ubuntu.
- [x] Confirm the 1,642-day/14-gap archive invariant through automated validation. Numerical
  parity against restricted historical outputs remains a local scientific verification and is
  not claimed by this source-only release.
- [x] Confirm that profile names are attached to all output paths and manifests.
- [x] Review the documented difference between historical and reviewed validation rules.
- [x] Confirm that the README, CLI help, example configurations and Snakemake workflow agree.

## Attribution and governance

- [x] Record contributor names, order, affiliations and ORCID identifiers in `CITATION.cff`.
- [x] Add the final private repository URL to `CITATION.cff` after the GitHub repository exists.
- [x] Record the repository owner's explicit authorization for the BSD 3-Clause source release.
- [x] Add the BSD 3-Clause licence text and SPDX identifier.
- [x] Push to a private GitHub repository first and review the rendered repository.
- [x] Record the repository owner's final instruction before changing visibility to public.

The repository owner authorized the BSD 3-Clause source release and public visibility on
2026-09-30. This record does not claim separate institutional endorsement of the scientific
results. The release includes no scientific data or derived results.
