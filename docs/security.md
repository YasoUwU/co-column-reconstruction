# Security and data-release checklist

This repository is prepared by copying reviewed source code through an explicit
allowlist. It must never be populated by copying an entire working directory.

## Before the first commit

1. Revoke every credential previously written into a script, notebook, shell
   history, log, or configuration file.
2. Confirm that local authentication uses a user-owned netrc file, provider
   configuration, environment variables, or a masked prompt. Command-line
   password options are prohibited because process arguments may be recorded.
3. Run `python tools/security_audit.py .` from the repository root. Resolve all
   findings; do not create blanket exceptions.
4. Run a dedicated secret scanner over the working tree.
5. Confirm that only code, documentation, configuration templates, and small
   synthetic test inputs are present.

## Before every release

1. Run the security audit, unit tests, lint checks, and package build in a clean
   environment.
2. Scan the complete Git history with a dedicated secret scanner.
3. Inspect the staged file list and verify that no scientific input, derived
   product, trained model, figure, report, archive, log, or local manifest is
   included.
4. Verify that no file exceeds 10 MiB. This project does not use Git LFS.
5. Keep the repository private until authorship, institutional permission, the
   citation metadata, and the pending license are approved in writing.

## Audit behavior

`tools/security_audit.py` performs a conservative offline scan. It detects
absolute Windows and network paths, literal secret assignments, private-key
markers, obvious email addresses and international phone numbers, forbidden
file types, and files larger than 10 MiB. Findings report only the rule, path,
and line number; matched content is never printed.

The scanner skips version-control metadata, virtual environments, build caches,
its own implementation, and its security tests. A clean result is necessary
but not sufficient: the dedicated history scan and human review remain release
requirements.
