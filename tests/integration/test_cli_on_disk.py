from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr

from co_pipeline.cli import main
from co_pipeline.constants import AVOGADRO, CO_MOLAR_MASS_KG_PER_MOL


def test_two_day_cli_preprocessing_writes_products_and_manifests(tmp_path: Path) -> None:
    data = tmp_path / "data"
    output = tmp_path / "output"
    cache = tmp_path / "cache"
    for name in (
        "iasi_l2",
        "merra2",
        "cams",
        "covariates",
        "validation/tropomi/2023",
        "validation/mopitt/2023",
    ):
        (data / name).mkdir(parents=True)
    latitude = np.array([-1.0, 0.0, 1.0])
    longitude = np.array([10.0, 11.0, 12.0, 13.0])
    point_latitude = np.repeat(latitude, longitude.size)
    point_longitude = np.tile(longitude, latitude.size)
    days = ("20230801", "20230802")
    for day_index, day in enumerate(days):
        xr.Dataset(
            {
                "latitude": ("point", point_latitude),
                "longitude": ("point", point_longitude),
                "CO_total_column": (
                    "point",
                    0.1 + day_index * 0.01 + np.arange(point_latitude.size) * 0.001,
                ),
                "CO_total_column_error": ("point", np.full(point_latitude.size, 0.1)),
                "retrieval_quality_flag": ("point", np.full(point_latitude.size, 2)),
            }
        ).to_netcdf(data / "iasi_l2" / f"iasi_{day}.nc")
        xr.Dataset(
            {
                "CO": (
                    ("time", "lev", "lat", "lon"),
                    np.full((8, 2, 3, 4), 1.0e-7),
                ),
                "DELP": (
                    ("time", "lev", "lat", "lon"),
                    np.full((8, 2, 3, 4), 5_000.0),
                ),
            },
            coords={"time": np.arange(8), "lev": [1, 2], "lat": latitude, "lon": longitude},
        ).to_netcdf(data / "merra2" / f"merra2_{day}.nc")
        validation_mol_cm2 = (
            1.0e-5
            + day_index * 1.0e-6
            + np.arange(latitude.size * longitude.size).reshape(3, 4) * 1.0e-7
        )
        xr.Dataset(
            {"CO_column_number_density": (("latitude", "longitude"), validation_mol_cm2 * 1.0e4)},
            coords={"latitude": latitude, "longitude": longitude},
        ).to_netcdf(data / "validation" / "tropomi" / "2023" / f"tropomi_{day}.nc")
        if day_index == 0:
            xr.Dataset(
                {
                    "RetrievedCOTotalColumn": (
                        ("latitude", "longitude"),
                        validation_mol_cm2 * AVOGADRO,
                    )
                },
                coords={"latitude": latitude, "longitude": longitude},
            ).to_netcdf(data / "validation" / "mopitt" / "2023" / f"mopitt_{day}.nc")
    times = np.concatenate(
        [
            np.datetime64(f"{day[:4]}-{day[4:6]}-{day[6:]}") + np.arange(8) * np.timedelta64(3, "h")
            for day in days
        ]
    )
    xr.Dataset(
        {
            "tcco": (
                ("time", "latitude", "longitude"),
                np.full((16, 3, 4), 1.0e-5 * 1.0e4 * CO_MOLAR_MASS_KG_PER_MOL),
            )
        },
        coords={"time": times, "latitude": latitude, "longitude": longitude},
    ).to_netcdf(data / "cams" / "cams_202308.nc")
    (data / "covariates" / "frp_monthly_domain.csv").write_text(
        "year,month,frp_mean,frp_total,severity_score\n2023,8,1.0,2.0,0.5\n",
        encoding="utf-8",
    )
    config = tmp_path / "synthetic.yaml"
    config.write_text(
        f"""
profile: reviewed
paths:
  data_root: {data.as_posix()}
  output_root: {output.as_posix()}
  cache_root: {cache.as_posix()}
inputs:
  iasi_l2_glob: iasi_l2/*.nc
  merra2_glob: merra2/*.nc
  cams_glob: cams/*.nc
  tropomi_glob: validation/tropomi/{{year}}/*.nc
  mopitt_glob: validation/mopitt/{{year}}/*.nc
  frp_csv: covariates/frp_monthly_domain.csv
variables:
  latitude: latitude
  longitude: longitude
  iasi_column: CO_total_column
  iasi_relative_error: CO_total_column_error
  iasi_quality_flag: retrieval_quality_flag
  iasi_partial_column: CO_partial_column_profile
  iasi_partial_error: CO_partial_column_error
  merra2_co: CO
  merra2_delp: DELP
  merra2_pressure_edges: PLE
  cams_column: tcco
  tropomi_column: CO_column_number_density
  mopitt_column: RetrievedCOTotalColumn
source_units:
  iasi_column: mol/m²
  cams_column: kg/m²
  tropomi_column: mol/m²
  mopitt_column: molecules/cm²
domain:
  longitude: [10.0, 13.0]
  latitude: [-1.0, 1.0]
  resolution: [1.0, 1.0]
  shape: [3, 4]
regions:
  synthetic: {{longitude: [10.0, 13.0], latitude: [-1.0, 1.0]}}
period:
  product_years: [2023, 2023]
  benchmark_training_years: [2023, 2023]
  final_training_years: [2023, 2023]
  evaluation_years: [2023, 2023]
  validation_years: [2023]
  months: [8, 9, 10]
units:
  internal: mol/cm²
model:
  primary: random_forest
  pixels_per_day: 1000
  max_samples: 600000
  statistical_quantiles: 2
  minimum_cell_samples: 2
  seed: 42
  ratio_clip: [0.2, 5.0]
validation:
  map_minimum_satellites: 2
  strong_agreement_satellites: 3
  neutral_z_threshold: 0.25
  regional_iqr_quantile: 0.33
coverage:
  enforce_complete: false
  expected_product_days: 2
  allowed_missing_dates: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert main(["run", "--config", str(config)]) == 0
    products = sorted((output / "reviewed" / "products" / "common_grid").glob("*/*.nc"))
    assert len(products) == 2
    with xr.open_dataset(products[0]) as product:
        assert product["CO_IASI"].shape == (3, 4)
        assert product["CO_CAMS"].shape == (3, 4)
        assert product["CO_MERRA2"].shape == (3, 4)
    manifest_path = output / "reviewed" / "manifests" / "common-grid.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["profile"] == "reviewed"
    assert manifest["configuration"]["paths"]["data_root"] == "<configured-data-root>"
    manifests = sorted((output / "reviewed" / "manifests").glob("*.json"))
    assert len(manifests) == 11
    assert (output / "reviewed" / "tables" / "benchmark_metrics_reviewed.csv").is_file()
    assert (output / "reviewed" / "tables" / "validation_metrics_reviewed.csv").is_file()
    assert (output / "reviewed" / "tables" / "reviewed_regional_satellite_consensus.csv").is_file()
