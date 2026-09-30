"""Filesystem adapters for the canonical pipeline stages.

Scientific calculations live in small testable modules. This module owns the
side effects and the public on-disk contracts used by both the CLI and Snakemake.
"""

from __future__ import annotations

import calendar
import csv
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xarray as xr
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .config import ConfigurationError, PipelineConfig
from .features import build_abcd_features, log_ratio_target, reconstruct_positive_column
from .gridding import grid_inverse_variance
from .io import DataContractError, write_netcdf
from .merra2 import daily_mean_eight_steps, integrate_co_column
from .models import (
    apply_gridded_statistical_calibration,
    fit_gridded_statistical_calibration,
)
from .plotting import save_field_map
from .provenance import write_manifest
from .units import convert_co_column
from .validation import (
    interquartile_range,
    regional_iqr_threshold,
    satellite_consensus,
    satellite_median,
)

DATE_PATTERN = re.compile(r"(?<!\d)(20\d{6})(?!\d)")
STAGES = (
    "grid-iasi",
    "merra2-daily",
    "download-cams",
    "common-grid",
    "benchmark",
    "train",
    "apply",
    "download-validation",
    "validation-grid",
    "validate",
    "figures",
)


@dataclass(frozen=True)
class Layout:
    data: Path
    output: Path
    cache: Path

    @classmethod
    def from_config(cls, config: PipelineConfig) -> Layout:
        output = config.path("paths", "output_root", create=True) / config.profile
        output.mkdir(parents=True, exist_ok=True)
        cache = config.path("paths", "cache_root", create=True) / config.profile
        cache.mkdir(parents=True, exist_ok=True)
        return cls(
            config.path("paths", "data_root"),
            output,
            cache,
        )

    @property
    def manifests(self) -> Path:
        return self.output / "manifests"

    def product(self, name: str) -> Path:
        path = self.output / "products" / name
        path.mkdir(parents=True, exist_ok=True)
        return path


def _date_key(path: Path) -> str:
    match = DATE_PATTERN.search(path.name)
    if not match:
        raise DataContractError(f"Filename must contain YYYYMMDD: {path.name}")
    return match.group(1)


def _coordinates(config: PipelineConfig) -> tuple[np.ndarray, np.ndarray]:
    domain = config.section("domain")
    lon_min, lon_max = map(float, domain["longitude"])
    lat_min, lat_max = map(float, domain["latitude"])
    lon_step, lat_step = map(float, domain["resolution"])
    lon = np.arange(lon_min, lon_max + lon_step / 2, lon_step)
    lat = np.arange(lat_min, lat_max + lat_step / 2, lat_step)
    expected = tuple(map(int, domain["shape"]))
    if (lat.size, lon.size) != expected:
        raise ConfigurationError(
            f"Configured grid produces {(lat.size, lon.size)}, expected {expected}"
        )
    return lat, lon


def _expected_product_dates(config: PipelineConfig) -> set[str]:
    """Return every configured calendar day covered by the seasonal product."""

    first_year, last_year = map(int, config.value("period.product_years"))
    months = tuple(map(int, config.value("period.months")))
    return {
        f"{year:04d}{month:02d}{day:02d}"
        for year in range(first_year, last_year + 1)
        for month in months
        for day in range(1, calendar.monthrange(year, month)[1] + 1)
    }


def _validate_product_coverage(config: PipelineConfig, paths: Iterable[Path]) -> None:
    """Require the complete historical date inventory when coverage is enforced."""

    if not bool(config.value("coverage.enforce_complete", True)):
        return
    actual = {_date_key(path) for path in paths}
    expected = _expected_product_dates(config)
    allowed_missing = {str(item) for item in config.value("coverage.allowed_missing_dates", [])}
    missing = expected - actual
    unexpected = actual - expected
    declared_outside_period = allowed_missing - expected
    expected_count = int(config.value("coverage.expected_product_days"))
    if declared_outside_period:
        raise DataContractError(
            "Allowed missing dates fall outside the configured product period: "
            f"{sorted(declared_outside_period)}"
        )
    if missing != allowed_missing or unexpected or len(actual) != expected_count:
        undeclared = sorted(missing - allowed_missing)
        unexpectedly_present = sorted(allowed_missing - missing)
        raise DataContractError(
            "Product coverage mismatch: "
            f"expected {expected_count} files, found {len(actual)}; "
            f"undeclared missing={undeclared}; "
            f"declared-but-present={unexpectedly_present}; "
            f"outside-period={sorted(unexpected)}"
        )


def _input_files(config: PipelineConfig, key: str, *, year: int | None = None) -> list[Path]:
    pattern = str(config.section("inputs")[key])
    if year is not None:
        pattern = pattern.format(year=year)
    root = config.path("paths", "data_root")
    return sorted(root.glob(pattern))


def _variable(config: PipelineConfig, key: str) -> str:
    return str(config.section("variables")[key])


def _manifest(
    config: PipelineConfig,
    layout: Layout,
    stage: str,
    inputs: Iterable[Path],
    outputs: Iterable[Path],
    *,
    model: str | None = None,
) -> Path:
    missing = config.value("coverage.allowed_missing_dates", [])
    return write_manifest(
        layout.manifests / f"{stage}.json",
        repository=Path(__file__).resolve().parents[2],
        config=config,
        stage=stage,
        inputs=list(inputs),
        outputs=list(outputs),
        missing_dates=[str(item) for item in missing],
        model=model,
    )


def grid_iasi(config: PipelineConfig, *, overwrite: bool = False, **_: object) -> Path:
    """Grid point-level IASI files with inverse-variance weights."""

    layout = Layout.from_config(config)
    sources = _input_files(config, "iasi_l2_glob")
    if not sources:
        raise FileNotFoundError("No IASI L2 files matched inputs.iasi_l2_glob")
    destination = layout.product("iasi_l3")
    lat_grid, lon_grid = _coordinates(config)
    lat_name = _variable(config, "latitude")
    lon_name = _variable(config, "longitude")
    co_name = _variable(config, "iasi_column")
    error_name = _variable(config, "iasi_relative_error")
    quality_name = _variable(config, "iasi_quality_flag")
    partial_name = _variable(config, "iasi_partial_column")
    partial_error_name = _variable(config, "iasi_partial_error")
    source_unit = str(config.section("source_units")["iasi_column"])
    outputs: list[Path] = []
    for source in sources:
        day = _date_key(source)
        output = destination / day[:4] / f"iasi_l3_{day}.nc"
        if output.exists() and not overwrite:
            outputs.append(output)
            continue
        with xr.open_dataset(source) as dataset:
            required = {lat_name, lon_name, quality_name}
            missing = required - set(dataset.variables)
            if missing:
                raise DataContractError(f"{source.name} is missing {sorted(missing)}")
            quality = np.asarray(dataset[quality_name]).ravel() == 2
            if co_name in dataset:
                if error_name not in dataset:
                    raise DataContractError(f"{source.name} is missing {error_name}")
                co_source = np.asarray(dataset[co_name], dtype=float).ravel()
                relative_error = np.asarray(dataset[error_name], dtype=float).ravel()
            elif partial_name in dataset:
                partial = np.asarray(dataset[partial_name], dtype=float)
                co_source = np.sum(partial, axis=-1).ravel()
                if partial_error_name in dataset:
                    relative_error = np.mean(
                        np.asarray(dataset[partial_error_name], dtype=float), axis=-1
                    ).ravel()
                else:
                    relative_error = np.full(co_source.shape, 0.15)
            else:
                raise DataContractError(
                    f"{source.name} contains neither {co_name} nor {partial_name}"
                )
            latitude = np.asarray(dataset[lat_name], dtype=float).ravel()
            longitude = np.asarray(dataset[lon_name], dtype=float).ravel()
            valid = (
                quality
                & np.isfinite(latitude)
                & np.isfinite(longitude)
                & np.isfinite(co_source)
                & np.isfinite(relative_error)
                & (co_source > 0)
                & (relative_error > 0)
            )
            co = convert_co_column(co_source[valid], source_unit, "mol/cm²")
            sigma = np.clip(co * relative_error[valid], 1.0e-12, None)
            result = grid_inverse_variance(
                latitude[valid],
                longitude[valid],
                co,
                sigma,
                lat_grid,
                lon_grid,
            )
        product = xr.Dataset(
            {
                "CO_IASI": (("lat", "lon"), result.value, {"units": "mol/cm²"}),
                "CO_IASI_uncertainty": (
                    ("lat", "lon"),
                    result.uncertainty,
                    {"units": "mol/cm²"},
                ),
                "observation_count": (("lat", "lon"), result.count),
            },
            coords={"lat": lat_grid, "lon": lon_grid},
            attrs={"date": day, "profile": config.profile},
        )
        outputs.append(write_netcdf(product, output))
    return _manifest(config, layout, "grid-iasi", sources, outputs)


def merra2_daily(config: PipelineConfig, *, overwrite: bool = False, **_: object) -> Path:
    """Integrate eight three-hourly MERRA-2 fields and calculate a daily mean."""

    layout = Layout.from_config(config)
    sources = _input_files(config, "merra2_glob")
    if not sources:
        raise FileNotFoundError("No MERRA-2 files matched inputs.merra2_glob")
    destination = layout.product("merra2_daily")
    co_name = _variable(config, "merra2_co")
    delp_name = _variable(config, "merra2_delp")
    pressure_edges_name = _variable(config, "merra2_pressure_edges")
    outputs: list[Path] = []
    for source in sources:
        day = _date_key(source)
        output = destination / day[:4] / f"merra2_daily_{day}.nc"
        if output.exists() and not overwrite:
            outputs.append(output)
            continue
        with xr.open_dataset(source) as dataset:
            if co_name not in dataset:
                raise DataContractError(f"{source.name} must contain {co_name}")
            co = dataset[co_name]
            level_dim = next((dim for dim in co.dims if dim.lower() in {"lev", "level"}), None)
            time_dim = next((dim for dim in co.dims if dim.lower() == "time"), None)
            if level_dim is None or time_dim is None:
                raise DataContractError("MERRA-2 CO must expose time and lev/level dimensions")
            if delp_name in dataset:
                delp = dataset[delp_name]
            elif pressure_edges_name in dataset:
                delp = abs(dataset[pressure_edges_name].diff(level_dim))
                co = co.isel({level_dim: slice(1, None)})
            else:
                raise DataContractError(
                    f"{source.name} must contain {delp_name} or {pressure_edges_name}"
                )
            ordered = [time_dim, level_dim] + [
                dim for dim in co.dims if dim not in {time_dim, level_dim}
            ]
            co_values = np.asarray(co.transpose(*ordered))
            delp_values = np.asarray(delp.broadcast_like(co).transpose(*ordered))
            instantaneous = integrate_co_column(co_values, delp_values, level_axis=1)
            daily = daily_mean_eight_steps(instantaneous, time_axis=0, require_complete=True)
            lat = np.asarray(dataset["lat"])
            lon = np.asarray(dataset["lon"])
        product = xr.Dataset(
            {"CO_MERRA2": (("lat", "lon"), daily, {"units": "mol/cm²"})},
            coords={"lat": lat, "lon": lon},
            attrs={"date": day, "temporal_sampling": "mean_of_8_three_hourly_fields"},
        )
        outputs.append(write_netcdf(product, output))
    return _manifest(config, layout, "merra2-daily", sources, outputs)


def download_cams(
    config: PipelineConfig, *, allow_network: bool = False, overwrite: bool = False, **_: object
) -> Path:
    """Download CAMS EAC4 monthly CO fields after explicit network authorization."""

    layout = Layout.from_config(config)
    existing = _input_files(config, "cams_glob")
    if existing and (not overwrite or not allow_network):
        return _manifest(config, layout, "download-cams", existing, existing)
    if not allow_network:
        raise PermissionError("CAMS download requires the explicit --allow-network flag")
    import cdsapi

    destination = layout.data / "cams"
    destination.mkdir(parents=True, exist_ok=True)
    start, end = map(int, config.value("period.product_years"))
    months = list(map(int, config.value("period.months")))
    north = float(config.value("domain.latitude")[1])
    south = float(config.value("domain.latitude")[0])
    west = float(config.value("domain.longitude")[0])
    east = float(config.value("domain.longitude")[1])
    client = cdsapi.Client()
    outputs: list[Path] = []
    for year in range(start, end + 1):
        for month in months:
            output = destination / f"cams_eac4_tcco_{year}_{month:02d}.nc"
            if output.exists() and not overwrite:
                outputs.append(output)
                continue
            last = calendar.monthrange(year, month)[1]
            client.retrieve(
                "cams-global-reanalysis-eac4",
                {
                    "variable": ["total_column_carbon_monoxide"],
                    "date": f"{year}-{month:02d}-01/{year}-{month:02d}-{last:02d}",
                    "time": [f"{hour:02d}:00" for hour in range(0, 24, 3)],
                    "area": [north, west, south, east],
                    "data_format": "netcdf",
                },
                str(output),
            )
            outputs.append(output)
    return _manifest(config, layout, "download-cams", [], outputs)


def _cams_for_day(config: PipelineConfig, day: str, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    candidates = [
        path for path in _input_files(config, "cams_glob") if day[:6] in path.stem.replace("_", "")
    ]
    if not candidates:
        raise FileNotFoundError(f"No CAMS monthly file found for {day[:6]}")
    with xr.open_dataset(candidates[0]) as dataset:
        variable = dataset[_variable(config, "cams_column")]
        if "valid_time" in variable.dims:
            variable = variable.rename({"valid_time": "time"})
        if "time" in variable.dims:
            daily_steps = variable.where(variable.time.dt.strftime("%Y%m%d") == day, drop=True)
            if daily_steps.sizes.get("time") != 8:
                raise DataContractError(
                    f"CAMS day {day} requires 8 three-hourly fields; "
                    f"found {daily_steps.sizes.get('time', 0)}"
                )
            daily = daily_steps.mean("time")
        else:
            daily = variable
        lat_name = "latitude" if "latitude" in daily.coords else "lat"
        lon_name = "longitude" if "longitude" in daily.coords else "lon"
        daily = daily.rename({lat_name: "lat", lon_name: "lon"})
        daily = daily.sortby("lat").sortby("lon").interp(lat=lat, lon=lon)
        unit = str(config.section("source_units")["cams_column"])
        return np.asarray(convert_co_column(daily.values, unit, "mol/cm²"), dtype=float)


def common_grid(config: PipelineConfig, *, overwrite: bool = False, **_: object) -> Path:
    """Collocate IASI, daily MERRA-2, and CAMS on the IASI analysis grid."""

    layout = Layout.from_config(config)
    iasi_files = sorted((layout.output / "products" / "iasi_l3").glob("*/*.nc"))
    merra_root = layout.output / "products" / "merra2_daily"
    if not iasi_files:
        raise FileNotFoundError("Run grid-iasi before common-grid")
    outputs: list[Path] = []
    inputs: list[Path] = []
    destination = layout.product("common_grid")
    for iasi_path in iasi_files:
        day = _date_key(iasi_path)
        merra_path = merra_root / day[:4] / f"merra2_daily_{day}.nc"
        if not merra_path.is_file():
            raise FileNotFoundError(f"Missing MERRA-2 daily product for {day}")
        output = destination / day[:4] / f"common_grid_{day}.nc"
        if output.exists() and not overwrite:
            outputs.append(output)
            continue
        with xr.open_dataset(iasi_path) as iasi, xr.open_dataset(merra_path) as merra:
            lat = np.asarray(iasi["lat"])
            lon = np.asarray(iasi["lon"])
            merra_field = merra["CO_MERRA2"].interp(lat=lat, lon=lon)
            cams_field = _cams_for_day(config, day, lat, lon)
            product = xr.Dataset(
                {
                    "CO_IASI": iasi["CO_IASI"].load(),
                    "CO_IASI_uncertainty": iasi["CO_IASI_uncertainty"].load(),
                    "CO_MERRA2": merra_field.load(),
                    "CO_CAMS": (("lat", "lon"), cams_field, {"units": "mol/cm²"}),
                },
                coords={"lat": lat, "lon": lon},
                attrs={"date": day, "profile": config.profile, "units": "mol/cm²"},
            )
        inputs.extend([iasi_path, merra_path])
        outputs.append(write_netcdf(product, output))
    _validate_product_coverage(config, outputs)
    return _manifest(config, layout, "common-grid", inputs, outputs)


def _frp_table(config: PipelineConfig, layout: Layout) -> pd.DataFrame:
    path = layout.data / str(config.section("inputs")["frp_csv"])
    if not path.is_file():
        raise FileNotFoundError(f"Missing domain-monthly FRP table: {path.name}")
    table = pd.read_csv(path)
    required = {"year", "month", "frp_mean", "frp_total", "severity_score"}
    missing = required - set(table.columns)
    if missing:
        raise DataContractError(f"FRP table is missing {sorted(missing)}")
    return table


def _frp_values(table: pd.DataFrame, day: str) -> tuple[float, float, float]:
    selected = table[(table["year"] == int(day[:4])) & (table["month"] == int(day[4:6]))]
    if len(selected) != 1:
        raise DataContractError(f"Expected one domain-monthly FRP row for {day[:6]}")
    row = selected.iloc[0]
    return float(row.frp_mean), float(row.frp_total), float(row.severity_score)


def _estimator(name: str, seed: int) -> object:
    if name == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    if name == "hgb":
        return make_pipeline(
            StandardScaler(),
            HistGradientBoostingRegressor(
                max_iter=300,
                learning_rate=0.05,
                max_leaf_nodes=31,
                min_samples_leaf=20,
                random_state=seed,
            ),
        )
    if name == "random_forest":
        return make_pipeline(
            StandardScaler(),
            RandomForestRegressor(
                n_estimators=200,
                max_features="sqrt",
                min_samples_leaf=10,
                random_state=seed,
                n_jobs=-1,
            ),
        )
    raise ValueError(f"Unknown estimator: {name}")


def _collect_samples(
    config: PipelineConfig, files: Iterable[Path], years: tuple[int, int]
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    layout = Layout.from_config(config)
    frp = _frp_table(config, layout)
    seed = int(config.value("model.seed"))
    rng = {
        "cams": np.random.default_rng(seed),
        "merra": np.random.default_rng(seed),
    }
    per_day = int(config.value("model.pixels_per_day"))
    maximum = int(config.value("model.max_samples"))
    buckets: dict[str, list[np.ndarray]] = {
        key: []
        for key in (
            "cams_x",
            "cams_y",
            "cams_source",
            "cams_obs",
            "merra_x",
            "merra_y",
            "merra_source",
            "merra_obs",
        )
    }
    for path in files:
        day = _date_key(path)
        year = int(day[:4])
        if not years[0] <= year <= years[1]:
            continue
        with xr.open_dataset(path) as dataset:
            obs = np.asarray(dataset["CO_IASI"], dtype=float)
            lat = np.asarray(dataset["lat"], dtype=float)
            lon = np.asarray(dataset["lon"], dtype=float)
            frp_values = _frp_values(frp, day)
            for prefix, variable in (("cams", "CO_CAMS"), ("merra", "CO_MERRA2")):
                source = np.asarray(dataset[variable], dtype=float)
                valid = np.isfinite(obs) & np.isfinite(source) & (obs > 0) & (source > 0)
                indices = np.flatnonzero(valid)
                if indices.size > per_day:
                    indices = rng[prefix].choice(indices, size=per_day, replace=False)
                if indices.size == 0:
                    continue
                mask = np.zeros(source.size, dtype=bool)
                mask[indices] = True
                mask = mask.reshape(source.shape)
                x = build_abcd_features(
                    source,
                    lat,
                    lon,
                    day,
                    frp_mean=frp_values[0],
                    frp_total=frp_values[1],
                    severity_score=frp_values[2],
                    mask=mask,
                )
                source_values = source.ravel()[indices]
                obs_values = obs.ravel()[indices]
                buckets[f"{prefix}_x"].append(x)
                buckets[f"{prefix}_y"].append(log_ratio_target(obs_values, source_values))
                buckets[f"{prefix}_source"].append(source_values)
                buckets[f"{prefix}_obs"].append(obs_values)
    result: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    for prefix in ("cams", "merra"):
        if not buckets[f"{prefix}_x"]:
            raise DataContractError(f"No samples collected for {prefix} in {years}")
        combined = tuple(
            np.concatenate(buckets[f"{prefix}_{suffix}"], axis=0)
            for suffix in ("x", "y", "source", "obs")
        )
        if combined[0].shape[0] > maximum:
            selected = rng[prefix].choice(combined[0].shape[0], size=maximum, replace=False)
            combined = tuple(values[selected] for values in combined)
        result[prefix] = combined  # type: ignore[assignment]
    return result


def _fit_statistical_fields(
    config: PipelineConfig, files: Iterable[Path], years: tuple[int, int], source_name: str
) -> object:
    selected = [path for path in files if years[0] <= int(_date_key(path)[:4]) <= years[1]]
    source_fields: list[np.ndarray] = []
    target_fields: list[np.ndarray] = []
    for path in selected:
        with xr.open_dataset(path) as dataset:
            source_fields.append(np.asarray(dataset[source_name], dtype=float))
            target_fields.append(np.asarray(dataset["CO_IASI"], dtype=float))
    if not source_fields:
        raise DataContractError(f"No statistical-calibration fields for {source_name}")
    return fit_gridded_statistical_calibration(
        np.stack(source_fields),
        np.stack(target_fields),
        n_quantiles=int(config.value("model.statistical_quantiles", 10)),
        minimum_cell_samples=int(config.value("model.minimum_cell_samples", 20)),
        correction_bounds=tuple(map(float, config.value("model.ratio_clip"))),
    )


def _fit_bundle(
    config: PipelineConfig, years: tuple[int, int]
) -> tuple[dict[str, object], list[Path]]:
    layout = Layout.from_config(config)
    files = sorted((layout.output / "products" / "common_grid").glob("*/*.nc"))
    if not files:
        raise FileNotFoundError("Run common-grid before model training")
    samples = _collect_samples(config, files, years)
    seed = int(config.value("model.seed"))
    bundle: dict[str, object] = {"profile": config.profile, "years": years, "axes": {}}
    for prefix, (x, target, _source, _obs) in samples.items():
        estimators = {name: _estimator(name, seed) for name in ("ridge", "hgb", "random_forest")}
        for estimator in estimators.values():
            estimator.fit(x, target)
        bundle["axes"][prefix] = {  # type: ignore[index]
            "estimators": estimators,
            "statistical": _fit_statistical_fields(
                config,
                files,
                years,
                "CO_CAMS" if prefix == "cams" else "CO_MERRA2",
            ),
        }
    return bundle, files


def _save_bundle(config: PipelineConfig, stage: str, years: tuple[int, int]) -> Path:
    layout = Layout.from_config(config)
    bundle, inputs = _fit_bundle(config, years)
    output = layout.product("models") / f"{stage}_{config.profile}.joblib"
    joblib.dump(bundle, output)
    outputs = [output]
    if stage == "benchmark":
        evaluation_years = tuple(map(int, config.value("period.evaluation_years")))
        metrics = _evaluate_bundle(config, bundle, inputs, evaluation_years)
        table = layout.output / "tables" / f"benchmark_metrics_{config.profile}.csv"
        table.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(metrics).to_csv(table, index=False)
        outputs.append(table)
    return _manifest(
        config,
        layout,
        stage,
        inputs,
        outputs,
        model="linear_scaling,quantile_mapping,quantile_delta_mapping,ridge,hgb,random_forest; "
        "feature_set=ABCD",
    )


def _evaluate_bundle(
    config: PipelineConfig,
    bundle: dict[str, object],
    files: Iterable[Path],
    years: tuple[int, int],
) -> list[dict[str, object]]:
    """Evaluate every benchmark method on the configured held-out years."""

    layout = Layout.from_config(config)
    frp = _frp_table(config, layout)
    bounds = tuple(map(float, config.value("model.ratio_clip")))
    totals: dict[tuple[str, str], dict[str, float]] = {}

    def update(axis: str, method: str, observation: np.ndarray, prediction: np.ndarray) -> None:
        valid = np.isfinite(observation) & np.isfinite(prediction)
        observed = observation[valid].astype(float)
        predicted = prediction[valid].astype(float)
        if observed.size == 0:
            return
        stats = totals.setdefault(
            (axis, method),
            {key: 0.0 for key in ("n", "obs", "pred", "obs2", "pred2", "cross", "sse")},
        )
        stats["n"] += observed.size
        stats["obs"] += float(observed.sum())
        stats["pred"] += float(predicted.sum())
        stats["obs2"] += float(np.dot(observed, observed))
        stats["pred2"] += float(np.dot(predicted, predicted))
        stats["cross"] += float(np.dot(observed, predicted))
        stats["sse"] += float(np.dot(predicted - observed, predicted - observed))

    for path in files:
        day = _date_key(path)
        if not years[0] <= int(day[:4]) <= years[1]:
            continue
        with xr.open_dataset(path) as dataset:
            observation = np.asarray(dataset["CO_IASI"], dtype=float)
            lat = np.asarray(dataset["lat"], dtype=float)
            lon = np.asarray(dataset["lon"], dtype=float)
            frp_values = _frp_values(frp, day)
            axes = bundle["axes"]
            for prefix, source_name in (("cams", "CO_CAMS"), ("merra", "CO_MERRA2")):
                source = np.asarray(dataset[source_name], dtype=float)
                update(prefix, "raw", observation, source)
                statistical = apply_gridded_statistical_calibration(
                    source, axes[prefix]["statistical"]
                )
                for method, prediction in statistical.items():
                    update(prefix, method.lower(), observation, prediction)
                valid = np.isfinite(source) & (source > 0)
                features = build_abcd_features(
                    np.where(valid, source, 1.0),
                    lat,
                    lon,
                    day,
                    frp_mean=frp_values[0],
                    frp_total=frp_values[1],
                    severity_score=frp_values[2],
                    mask=valid,
                )
                for method, estimator in axes[prefix]["estimators"].items():
                    prediction = np.full(source.shape, np.nan)
                    prediction[valid] = reconstruct_positive_column(
                        source[valid], estimator.predict(features), correction_bounds=bounds
                    )
                    update(prefix, method, observation, prediction)
    rows: list[dict[str, object]] = []
    for (axis, method), stats in sorted(totals.items()):
        count = stats["n"]
        obs_variation = stats["obs2"] - stats["obs"] ** 2 / count
        pred_variation = stats["pred2"] - stats["pred"] ** 2 / count
        covariance = stats["cross"] - stats["obs"] * stats["pred"] / count
        rows.append(
            {
                "profile": config.profile,
                "evaluation_years": f"{years[0]}-{years[1]}",
                "axis": axis,
                "method": method,
                "n": int(count),
                "bias_mol_cm2": (stats["pred"] - stats["obs"]) / count,
                "rmse_mol_cm2": np.sqrt(stats["sse"] / count),
                "r2": 1.0 - stats["sse"] / obs_variation if obs_variation > 0 else np.nan,
                "correlation": covariance / np.sqrt(obs_variation * pred_variation)
                if obs_variation > 0 and pred_variation > 0
                else np.nan,
            }
        )
    if not rows:
        raise DataContractError(f"No benchmark evaluation fields found for {years}")
    return rows


def benchmark(config: PipelineConfig, **_: object) -> Path:
    years = tuple(map(int, config.value("period.benchmark_training_years")))
    return _save_bundle(config, "benchmark", years)


def train(config: PipelineConfig, **_: object) -> Path:
    years = tuple(map(int, config.value("period.final_training_years")))
    return _save_bundle(config, "train", years)


def apply_models(config: PipelineConfig, *, overwrite: bool = False, **_: object) -> Path:
    layout = Layout.from_config(config)
    model_path = layout.output / "products" / "models" / f"train_{config.profile}.joblib"
    if not model_path.is_file():
        raise FileNotFoundError("Run train before apply")
    bundle = joblib.load(model_path)
    frp = _frp_table(config, layout)
    sources = sorted((layout.output / "products" / "common_grid").glob("*/*.nc"))
    outputs: list[Path] = []
    destination = layout.product("corrected")
    bounds = tuple(map(float, config.value("model.ratio_clip")))
    for source_path in sources:
        day = _date_key(source_path)
        output = destination / day[:4] / f"corrected_{day}.nc"
        if output.exists() and not overwrite:
            outputs.append(output)
            continue
        with xr.open_dataset(source_path) as dataset:
            lat = np.asarray(dataset["lat"])
            lon = np.asarray(dataset["lon"])
            variables: dict[str, tuple[tuple[str, str], np.ndarray, dict[str, str]]] = {
                name: (
                    ("lat", "lon"),
                    np.asarray(dataset[name], dtype=float),
                    dict(dataset[name].attrs),
                )
                for name in ("CO_IASI", "CO_IASI_uncertainty", "CO_CAMS", "CO_MERRA2")
                if name in dataset
            }
            frp_values = _frp_values(frp, day)
            for prefix, source_name in (("cams", "CO_CAMS"), ("merra", "CO_MERRA2")):
                source_values = np.asarray(dataset[source_name], dtype=float)
                valid = np.isfinite(source_values) & (source_values > 0)
                filled = np.where(valid, source_values, 1.0)
                x = build_abcd_features(
                    filled,
                    lat,
                    lon,
                    day,
                    frp_mean=frp_values[0],
                    frp_total=frp_values[1],
                    severity_score=frp_values[2],
                    mask=valid,
                )
                axis_bundle = bundle["axes"][prefix]
                for name, estimator in axis_bundle["estimators"].items():
                    prediction = np.full(source_values.shape, np.nan)
                    prediction[valid] = reconstruct_positive_column(
                        source_values[valid], estimator.predict(x), correction_bounds=bounds
                    )
                    variables[f"CO_{prefix.upper()}_{name.upper()}"] = (
                        ("lat", "lon"),
                        prediction,
                        {"units": "mol/cm²"},
                    )
                statistical = apply_gridded_statistical_calibration(
                    source_values, axis_bundle["statistical"]
                )
                for name, prediction in statistical.items():
                    variables[f"CO_{prefix.upper()}_{name}"] = (
                        ("lat", "lon"),
                        prediction,
                        {"units": "mol/cm²"},
                    )
            product = xr.Dataset(
                variables,
                coords={"lat": lat, "lon": lon},
                attrs={"date": day, "profile": config.profile, "target": "IASI"},
            )
        outputs.append(write_netcdf(product, output))
    return _manifest(
        config,
        layout,
        "apply",
        [model_path, *sources],
        outputs,
        model=f"primary={config.value('model.primary')}; feature_set=ABCD",
    )


def download_validation(config: PipelineConfig, **_: object) -> Path:
    """Register externally acquired validation files without redistributing them."""

    layout = Layout.from_config(config)
    inputs: list[Path] = []
    for year in map(int, config.value("period.validation_years")):
        inputs.extend(_input_files(config, "tropomi_glob", year=year))
        inputs.extend(_input_files(config, "mopitt_glob", year=year))
    if not inputs:
        raise FileNotFoundError(
            "No external validation files found. Acquire them from the official providers "
            "described in DATA_SOURCES.md; credentials are never accepted by this command."
        )
    return _manifest(config, layout, "download-validation", inputs, [])


def validation_grid(config: PipelineConfig, *, overwrite: bool = False, **_: object) -> Path:
    """Bin external satellite points onto each corrected daily product grid."""

    layout = Layout.from_config(config)
    corrected = sorted((layout.output / "products" / "corrected").glob("*/*.nc"))
    if not corrected:
        raise FileNotFoundError("Run apply before validation-grid")
    minimum = int(config.value("validation.map_minimum_satellites"))
    outputs: list[Path] = []
    inputs: list[Path] = []
    destination = layout.product("validation_grid")
    validation_years = {int(year) for year in config.value("period.validation_years")}
    for product_path in corrected:
        day = _date_key(product_path)
        year = int(day[:4])
        if year not in validation_years:
            continue
        external = [
            (key.removesuffix("_glob"), path)
            for key in ("tropomi_glob", "mopitt_glob")
            for path in _input_files(config, key, year=year)
            if day in path.name
        ]
        if not external:
            continue
        output = destination / str(year) / f"validation_grid_{day}.nc"
        if output.exists() and not overwrite:
            outputs.append(output)
            continue
        with xr.open_dataset(product_path) as product:
            lat = np.asarray(product["lat"])
            lon = np.asarray(product["lon"])
            fields: list[np.ndarray] = [np.asarray(product["CO_IASI"], dtype=float)]
            variables: dict[str, tuple[tuple[str, str], np.ndarray, dict[str, str]]] = {}
            for instrument, external_path in external:
                with xr.open_dataset(external_path) as dataset:
                    lat_name = _variable(config, "latitude")
                    lon_name = _variable(config, "longitude")
                    column_name = _variable(config, f"{instrument}_column")
                    if column_name not in dataset:
                        raise DataContractError(
                            f"{external_path.name} is missing configured variable {column_name}"
                        )
                    column = np.asarray(dataset[column_name], dtype=float)
                    source_lat = np.asarray(dataset[lat_name], dtype=float)
                    source_lon = np.asarray(dataset[lon_name], dtype=float)
                    if source_lat.ndim == source_lon.ndim == 1 and column.shape == (
                        source_lat.size,
                        source_lon.size,
                    ):
                        source_lon, source_lat = np.meshgrid(source_lon, source_lat)
                    if column.size != source_lat.size or column.size != source_lon.size:
                        raise DataContractError(
                            f"{external_path.name} column and coordinates have incompatible shapes"
                        )
                    values = convert_co_column(
                        column.ravel(),
                        str(config.section("source_units")[f"{instrument}_column"]),
                        "mol/cm²",
                    )
                    binned = grid_inverse_variance(
                        source_lat.ravel(),
                        source_lon.ravel(),
                        values,
                        np.ones(values.size),
                        lat,
                        lon,
                    ).value
                    name = instrument.upper()
                    variables[f"CO_{name}"] = (("lat", "lon"), binned, {"units": "mol/cm²"})
                    fields.append(binned)
            median, count = satellite_median(
                np.stack(fields), satellite_axis=0, minimum_satellites=minimum
            )
            variables["CO_satellite_median"] = (("lat", "lon"), median, {"units": "mol/cm²"})
            variables["n_satellites"] = (("lat", "lon"), count, {})
            for name in product.data_vars:
                variables[name] = (
                    ("lat", "lon"),
                    np.asarray(product[name]),
                    dict(product[name].attrs),
                )
            dataset_out = xr.Dataset(
                variables,
                coords={"lat": lat, "lon": lon},
                attrs={"date": day, "profile": config.profile},
            )
        inputs.extend([product_path, *(path for _, path in external)])
        outputs.append(write_netcdf(dataset_out, output))
    return _manifest(config, layout, "validation-grid", inputs, outputs)


def validate(config: PipelineConfig, **_: object) -> Path:
    """Calculate transparent daily metrics against the satellite median."""

    layout = Layout.from_config(config)
    sources = sorted((layout.output / "products" / "validation_grid").glob("*/*.nc"))
    if not sources:
        raise FileNotFoundError("Run validation-grid before validate")
    rows: list[dict[str, object]] = []
    for source in sources:
        with xr.open_dataset(source) as dataset:
            reference = np.asarray(dataset["CO_satellite_median"]).ravel()
            for name in dataset.data_vars:
                if (
                    not name.startswith("CO_")
                    or name
                    in {
                        "CO_satellite_median",
                        "CO_TROPOMI",
                        "CO_MOPITT",
                    }
                    or name.endswith("_uncertainty")
                ):
                    continue
                prediction = np.asarray(dataset[name]).ravel()
                valid = np.isfinite(reference) & np.isfinite(prediction)
                if valid.sum() < 2:
                    continue
                rows.append(
                    {
                        "date": _date_key(source),
                        "product": name,
                        "n": int(valid.sum()),
                        "bias_mol_cm2": float(np.mean(prediction[valid] - reference[valid])),
                        "rmse_mol_cm2": float(
                            np.sqrt(mean_squared_error(reference[valid], prediction[valid]))
                        ),
                        "r2": float(r2_score(reference[valid], prediction[valid])),
                        "correlation": float(
                            np.corrcoef(reference[valid], prediction[valid])[0, 1]
                        ),
                    }
                )
    output = layout.output / "tables" / f"validation_metrics_{config.profile}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["date", "product"])
        writer.writeheader()
        writer.writerows(rows)
    outputs = [output]
    if config.profile == "reviewed":
        outputs.append(_write_reviewed_regional_consensus(config, sources, layout))
    return _manifest(config, layout, "validate", sources, outputs)


def _write_reviewed_regional_consensus(
    config: PipelineConfig, sources: Iterable[Path], layout: Layout
) -> Path:
    """Apply reviewed agreement rules to regional daily time-series anomalies."""

    records: list[dict[str, object]] = []
    instruments = ("IASI", "TROPOMI", "MOPITT")
    for source in sources:
        day = _date_key(source)
        with xr.open_dataset(source) as dataset:
            lat = np.asarray(dataset["lat"], dtype=float)
            lon = np.asarray(dataset["lon"], dtype=float)
            for region_name, bounds in config.section("regions").items():
                lon_min, lon_max = map(float, bounds["longitude"])
                lat_min, lat_max = map(float, bounds["latitude"])
                mask = (
                    (lat[:, None] >= lat_min)
                    & (lat[:, None] <= lat_max)
                    & (lon[None, :] >= lon_min)
                    & (lon[None, :] <= lon_max)
                )
                row: dict[str, object] = {
                    "date": day,
                    "year": int(day[:4]),
                    "region": region_name,
                }
                for instrument in instruments:
                    variable = f"CO_{instrument}"
                    if variable not in dataset:
                        row[instrument] = np.nan
                    else:
                        field = np.asarray(dataset[variable], dtype=float)
                        selected = field[mask]
                        row[instrument] = (
                            float(np.nanmean(selected)) if np.isfinite(selected).any() else np.nan
                        )
                records.append(row)
    daily = pd.DataFrame(records).sort_values(["year", "region", "date"])
    for instrument in instruments:
        daily[f"z_{instrument}"] = daily.groupby(["year", "region"])[instrument].transform(
            lambda values: (
                (values - values.mean()) / values.std(ddof=0)
                if values.notna().sum() >= 2 and values.std(ddof=0) > 0
                else np.nan
            )
        )
    minimum = int(config.value("validation.map_minimum_satellites"))
    strong_satellites = int(config.value("validation.strong_agreement_satellites"))
    tolerance = float(config.value("validation.neutral_z_threshold"))
    anomaly_values = daily[[f"z_{instrument}" for instrument in instruments]].to_numpy().T
    consensus = satellite_consensus(
        anomaly_values,
        satellite_axis=0,
        minimum_satellites=minimum,
        strong_satellites=strong_satellites,
        neutral_tolerance=tolerance,
    )
    daily["n_satellites"] = consensus.count
    daily["median_z"] = consensus.median
    daily["direction"] = consensus.direction
    daily["sign_convergence"] = consensus.strong_agreement
    daily["satellite_iqr"] = interquartile_range(anomaly_values, axis=0)
    quantile = float(config.value("validation.regional_iqr_quantile"))
    daily["regional_iqr_q33"] = daily.groupby(["year", "region"])["satellite_iqr"].transform(
        lambda values: (
            regional_iqr_threshold(values, quantile=quantile) if values.notna().any() else np.nan
        )
    )
    daily["strong_agreement"] = (
        daily["sign_convergence"]
        & np.isfinite(daily["regional_iqr_q33"])
        & (daily["satellite_iqr"] <= daily["regional_iqr_q33"])
    )
    output = layout.output / "tables" / "reviewed_regional_satellite_consensus.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(output, index=False)
    return output


def figures(config: PipelineConfig, **_: object) -> Path:
    """Generate deterministic report diagnostics from validated fields."""

    layout = Layout.from_config(config)
    sources = sorted((layout.output / "products" / "validation_grid").glob("*/*.nc"))
    if not sources:
        raise FileNotFoundError("Run validation-grid before figures")
    destination = layout.output / "report_figures" / config.profile
    outputs: list[Path] = []
    for source in sources[:8]:
        day = _date_key(source)
        with xr.open_dataset(source) as dataset:
            field = np.asarray(dataset["CO_satellite_median"], dtype=float) * 6.02214076e5
        outputs.append(
            save_field_map(
                field,
                output=destination / f"satellite_median_{day}.png",
                title=f"Satellite median - {day}",
                colorbar_label="CO (10^18 molecules cm-2)",
            )
        )
    return _manifest(config, layout, "figures", sources, outputs)


EXECUTORS: dict[str, Callable[..., Path]] = {
    "grid-iasi": grid_iasi,
    "merra2-daily": merra2_daily,
    "download-cams": download_cams,
    "common-grid": common_grid,
    "benchmark": benchmark,
    "train": train,
    "apply": apply_models,
    "download-validation": download_validation,
    "validation-grid": validation_grid,
    "validate": validate,
    "figures": figures,
}


def run_stage(stage: str, config: PipelineConfig, **options: object) -> Path:
    if stage not in EXECUTORS:
        raise ValueError(f"Unknown stage {stage!r}; expected one of {STAGES}")
    return EXECUTORS[stage](config, **options)
