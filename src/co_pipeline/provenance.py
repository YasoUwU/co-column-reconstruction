"""Create privacy-safe, deterministic execution manifests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import subprocess
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from .config import PipelineConfig
from .io import write_json

TRACKED_PACKAGES = (
    "numpy",
    "pandas",
    "xarray",
    "scipy",
    "scikit-learn",
    "netCDF4",
    "h5py",
    "joblib",
    "matplotlib",
    "cartopy",
)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _git_revision(repository: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in TRACKED_PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def build_manifest(
    *,
    repository: Path,
    config: PipelineConfig,
    stage: str,
    inputs: Iterable[Path] = (),
    outputs: Iterable[Path] = (),
    missing_dates: Iterable[str] = (),
    model: str | None = None,
) -> dict[str, object]:
    """Return a manifest that stores relative paths and never stores credentials."""

    repository = repository.resolve()

    normalized_configuration = config.normalized()
    configured_paths = normalized_configuration.get("paths", {})
    if isinstance(configured_paths, dict):
        for key in tuple(configured_paths):
            configured_paths[key] = f"<configured-{key.replace('_', '-')}>"
    safe_roots = {
        "repository": repository,
        "data-root": config.path("paths", "data_root").resolve(),
        "output-root": config.path("paths", "output_root").resolve(),
        "cache-root": config.path("paths", "cache_root").resolve(),
    }

    def describe(path: Path) -> dict[str, object]:
        resolved = path.resolve()
        display = resolved.name
        for label, root in safe_roots.items():
            try:
                display = f"<{label}>/{resolved.relative_to(root).as_posix()}"
                break
            except ValueError:
                continue
        return {
            "path": display,
            "sha256": sha256_file(resolved) if resolved.is_file() else None,
            "size_bytes": resolved.stat().st_size if resolved.is_file() else None,
        }

    return {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "profile": config.profile,
        "configuration": normalized_configuration,
        "configuration_sha256": config.fingerprint(),
        "git_revision": _git_revision(repository),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": _package_versions(),
        "model": model,
        "missing_dates": sorted(set(missing_dates)),
        "inputs": [describe(path) for path in inputs],
        "outputs": [describe(path) for path in outputs],
    }


def write_manifest(path: Path, **kwargs: object) -> Path:
    return write_json(path, build_manifest(**kwargs))
