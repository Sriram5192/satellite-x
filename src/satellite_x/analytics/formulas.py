"""Vectorized Set 3 spectral formulas."""

from __future__ import annotations

import numpy as np

EPSILON = 1e-10


def compute_indices(bands: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    blue = bands["B02"]
    green = bands["B03"]
    red = bands["B04"]
    rededge = bands["B05"]
    nir = bands["B08"]
    swir = bands["B11"]
    return {
        "ndvi": (nir - red) / (nir + red + EPSILON),
        "evi": 2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1 + EPSILON),
        "savi": 1.5 * (nir - red) / (nir + red + 0.5 + EPSILON),
        "ndre": (nir - rededge) / (nir + rededge + EPSILON),
        "ndmi": (nir - swir) / (nir + swir + EPSILON),
        "ndwi": (green - nir) / (green + nir + EPSILON),
        "gndvi": (nir - green) / (nir + green + EPSILON),
    }
