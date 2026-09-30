# Security policy

## Supported versions

Security fixes are applied to the current default branch. This research code
is not a hosted service and does not process untrusted remote requests.

## Reporting a vulnerability

Do not open a public issue for a suspected credential exposure or another
security-sensitive problem. Contact the repository maintainers privately
through the security-advisory feature of the hosting platform. Include the
affected revision, file, impact, and a minimal reproduction. Do not include
working credentials or third-party scientific data in the report.

Maintainers should acknowledge a report within seven calendar days. A public
disclosure should wait until exposed credentials have been revoked and a fix
has been released.

## Credential handling

- Never commit credentials or pass a password on a command line.
- Earthdata credentials must be provided through the user's netrc file,
  environment variables, or an interactive masked prompt.
- CAMS/CDS credentials must remain in the provider's user-level configuration.
- If a credential is found in any revision, revoke it first, remove it from the
  complete history, and rerun both the repository audit and a dedicated secret
  scanner before sharing the repository.

## Data policy

The repository contains code and synthetic test fixtures only. Raw or derived
scientific data, trained models, generated figures, reports, logs, and local
run manifests must remain outside version control. Product access and
redistribution conditions are documented separately in `DATA_SOURCES.md`.
