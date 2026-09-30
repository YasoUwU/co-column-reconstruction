from __future__ import annotations

from pathlib import Path

from co_pipeline.config import PipelineConfig
from co_pipeline.provenance import build_manifest
from co_pipeline.stages import Layout


def _config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        source=tmp_path / "config.yaml",
        values={
            "profile": "reviewed",
            "paths": {
                "data_root": str(tmp_path / "private-data"),
                "output_root": str(tmp_path / "outputs"),
                "cache_root": str(tmp_path / "cache"),
            },
            "period": {"months": [8, 9, 10]},
            "units": {"internal": "mol/cm²"},
            "model": {"seed": 42, "ratio_clip": [0.2, 5.0]},
        },
    )


def test_layout_separates_profile_outputs(tmp_path: Path) -> None:
    layout = Layout.from_config(_config(tmp_path))
    assert layout.output == tmp_path / "outputs" / "reviewed"
    assert layout.cache == tmp_path / "cache" / "reviewed"


def test_manifest_contains_normalized_config_without_private_roots(tmp_path: Path) -> None:
    config = _config(tmp_path)
    manifest = build_manifest(
        repository=tmp_path,
        config=config,
        stage="synthetic",
    )
    assert manifest["configuration"]["profile"] == "reviewed"  # type: ignore[index]
    assert manifest["configuration"]["paths"] == {  # type: ignore[index]
        "data_root": "<configured-data-root>",
        "output_root": "<configured-output-root>",
        "cache_root": "<configured-cache-root>",
    }
    assert str(tmp_path) not in str(manifest)
