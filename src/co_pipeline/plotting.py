"""Small plotting interface shared by report and reviewed profiles."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def save_field_map(
    values: np.ndarray,
    *,
    output: Path,
    title: str,
    colorbar_label: str,
    vmin: float | None = None,
    vmax: float | None = None,
) -> Path:
    """Save a deterministic diagnostic map without embedding local metadata."""

    output.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    image = axis.imshow(values, origin="lower", cmap="YlOrRd", vmin=vmin, vmax=vmax)
    axis.set_title(title)
    axis.set_xlabel("Longitude index")
    axis.set_ylabel("Latitude index")
    figure.colorbar(image, ax=axis, label=colorbar_label)
    figure.savefig(output, dpi=200, metadata={"Software": "co-column-reconstruction"})
    plt.close(figure)
    return output
