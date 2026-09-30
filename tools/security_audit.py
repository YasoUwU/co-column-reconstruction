#!/usr/bin/env python3
"""Fail safely when a repository contains common release hazards.

The scanner is deliberately dependency-free and offline. Diagnostic messages
never include matched text, which prevents a CI log from amplifying a secret.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_SIZE = 10 * 1024 * 1024

SKIP_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "venv",
    }
)

SKIP_RELATIVE_FILES = frozenset(
    {
        Path("tools/security_audit.py"),
    }
)

SKIP_RELATIVE_PREFIXES = (Path("tests/security"),)

FORBIDDEN_SUFFIXES = frozenset(
    {
        ".7z",
        ".csv",
        ".doc",
        ".docx",
        ".eps",
        ".feather",
        ".grb",
        ".grib",
        ".grib2",
        ".gz",
        ".h5",
        ".hdf",
        ".hdf5",
        ".he5",
        ".joblib",
        ".jpeg",
        ".jpg",
        ".log",
        ".nc",
        ".nc4",
        ".npy",
        ".npz",
        ".onnx",
        ".pdf",
        ".parquet",
        ".pickle",
        ".pkl",
        ".png",
        ".pt",
        ".pth",
        ".rar",
        ".svg",
        ".tar",
        ".tsv",
        ".tgz",
        ".tif",
        ".tiff",
        ".zip",
    }
)

FORBIDDEN_FILENAMES = frozenset(
    {
        ".cdsapirc",
        ".env",
        ".netrc",
        "_netrc",
    }
)

FORBIDDEN_DIRECTORY_NAMES = frozenset(
    {
        "data",
        "figures",
        "logs",
        "models",
        "output",
        "outputs",
        "scratch",
        "tmp",
    }
)


@dataclass(frozen=True, order=True)
class Finding:
    """A redacted audit finding."""

    path: str
    rule: str
    line: int | None = None

    def format(self) -> str:
        location = f"{self.path}:{self.line}" if self.line is not None else self.path
        return f"{location}: {self.rule}"


TEXT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "absolute Windows path",
        re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/](?![\\/])"),
    ),
    (
        "UNC/network path",
        re.compile(r"(?<![\\])\\\\[^\\\s]+\\[^\\\s]+"),
    ),
    (
        "literal secret assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
            r"earthdata[_-]?(?:password|token)|password|passwd|secret|token)\b"
            r"\s*(?::|=)\s*(?!\s*(?:none|null|true|false)\b)"
            r"(?:['\"][^'\"\r\n]{1,}|[^\s#,'\"{}\[\]]{4,})"
        ),
    ),
    (
        "private key material",
        re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    ),
    (
        "email address (possible PII)",
        re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+"),
    ),
    (
        "phone number (possible PII)",
        re.compile(r"(?<!\w)\+\d(?:[ .()-]*\d){8,14}(?!\w)"),
    ),
)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def iter_files(root: Path) -> Iterator[tuple[Path, Path]]:
    """Yield physical files as ``(absolute_path, repository_relative_path)``."""

    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names[:] = sorted(
            name for name in directory_names if name not in SKIP_DIRECTORIES
        )
        base = Path(directory)
        for name in sorted(file_names):
            path = base / name
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root)
            if relative in SKIP_RELATIVE_FILES:
                continue
            if any(_is_relative_to(relative, prefix) for prefix in SKIP_RELATIVE_PREFIXES):
                continue
            yield path, relative


def _has_forbidden_suffix(path: Path) -> bool:
    lower_name = path.name.lower()
    return any(lower_name.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES)


def _decode_text(path: Path) -> str | None:
    """Decode likely text without ever returning binary content in diagnostics."""

    sample = path.read_bytes()
    if b"\x00" in sample:
        return None
    try:
        return sample.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return sample.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None


def audit_file(path: Path, relative: Path) -> list[Finding]:
    """Return redacted findings for one file."""

    display_path = relative.as_posix()
    findings: list[Finding] = []

    if path.stat().st_size > MAX_FILE_SIZE:
        findings.append(Finding(display_path, "file exceeds 10 MiB"))
    lower_name = path.name.lower()
    if (
        lower_name in FORBIDDEN_FILENAMES
        or lower_name.startswith(".env.")
        or lower_name.endswith((".local.yaml", ".local.yml"))
    ):
        findings.append(Finding(display_path, "forbidden credential/configuration file"))
    if _has_forbidden_suffix(path):
        findings.append(Finding(display_path, "forbidden data/model/archive/media type"))
    if any(part.lower() in FORBIDDEN_DIRECTORY_NAMES for part in relative.parts[:-1]):
        findings.append(Finding(display_path, "file stored in a forbidden artefact directory"))

    # Large and known-forbidden binary files do not need to be loaded again.
    if path.stat().st_size > MAX_FILE_SIZE or _has_forbidden_suffix(path):
        return findings

    text = _decode_text(path)
    if text is None:
        return findings
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in TEXT_RULES:
            if pattern.search(line):
                findings.append(Finding(display_path, rule, line_number))
    return findings


def audit_repository(root: Path) -> list[Finding]:
    """Audit a repository tree and return stable, deduplicated findings."""

    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    findings = [
        finding for path, relative in iter_files(root) for finding in audit_file(path, relative)
    ]
    return sorted(set(findings))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan a repository for secrets, PII, local paths, and forbidden files."
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="repository root to scan (default: current directory)",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        findings = audit_repository(args.root)
    except (OSError, NotADirectoryError) as error:
        print(
            f"security audit could not scan the requested root: {type(error).__name__}",
            file=sys.stderr,
        )
        return 2

    if findings:
        print(f"security audit failed with {len(findings)} finding(s):", file=sys.stderr)
        for finding in findings:
            print(f"- {finding.format()}", file=sys.stderr)
        return 1

    print("security audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
