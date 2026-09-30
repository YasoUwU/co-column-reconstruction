"""Safe filesystem and NetCDF helpers used across pipeline stages."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import xarray as xr


class DataContractError(ValueError):
    """Raised when a scientific input violates an explicit data contract."""


def require_files(paths: Iterable[Path], *, label: str) -> list[Path]:
    checked = [Path(path) for path in paths]
    missing = [path for path in checked if not path.is_file()]
    if missing:
        preview = ", ".join(str(path) for path in missing[:5])
        raise FileNotFoundError(f"Missing {label} files ({len(missing)}): {preview}")
    return checked


def open_dataset_checked(path: str | Path, required: Iterable[str] = ()) -> xr.Dataset:
    dataset = xr.open_dataset(Path(path))
    missing = sorted(set(required) - set(dataset.variables))
    if missing:
        dataset.close()
        raise DataContractError(f"Missing variables in {Path(path).name}: {missing}")
    return dataset


def write_json(path: str | Path, payload: Any) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination


def write_netcdf(dataset: xr.Dataset, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    dataset.to_netcdf(temporary)
    temporary.replace(destination)
    return destination
