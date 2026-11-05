"""InSAR (Interferometric Synthetic Aperture Radar) & Remote Sensing Pipeline.

Provides STAC catalog querying, InSAR coherence change detection (CCD),
and Damage Proxy Map (DPM) generation for post-earthquake assessment.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import rasterio
from rasterio.transform import from_bounds

# Sentinel-1 C-band radar wavelength in meters
SENTINEL1_WAVELENGTH_M: float = 0.055465


@dataclass
class InSARProductMetadata:
    orbit_direction: str  # "ASCENDING" or "DESCENDING"
    relative_orbit: int
    pre_event_dates: tuple[str, str]
    post_event_dates: tuple[str, str]
    perpendicular_baseline_m: float
    temporal_baseline_days: int


@dataclass
class DamageProxyMapResult:
    dpm: npt.NDArray[np.float32]
    coherence_pre: npt.NDArray[np.float32]
    coherence_co: npt.NDArray[np.float32]
    severe_damage_ratio: float
    bounds: tuple[float, float, float, float]
    resolution_deg: float


def search_sentinel_stac(
    bbox: tuple[float, float, float, float],
    start_date: str,
    end_date: str,
    stac_endpoint: str = "https://planetarycomputer.microsoft.com/api/stac/v1",
    collection: str = "sentinel-1-grd",
) -> list[dict[str, Any]]:
    """Query STAC endpoint for Sentinel items covering the AOI.

    Returns item summaries including IDs, dates, and orbit metadata.
    """
    from pystac_client import Client

    client = Client.open(stac_endpoint)
    search = client.search(
        collections=[collection],
        bbox=list(bbox),
        datetime=f"{start_date}/{end_date}",
        max_items=20,
    )
    items = search.item_collection()
    return [
        {
            "id": item.id,
            "datetime": item.datetime.isoformat() if item.datetime else None,
            "bbox": item.bbox,
            "properties": {
                "platform": item.properties.get("platform", "sentinel-1"),
                "sar:instrument_mode": item.properties.get("sar:instrument_mode", "IW"),
                "sat:orbit_state": item.properties.get("sat:orbit_state", "descending"),
            },
        }
        for item in items
    ]


def compute_coherence_loss(
    coherence_pre: npt.NDArray[np.float32],
    coherence_co: npt.NDArray[np.float32],
    min_pre_coherence: float = 0.35,
    threshold: float = 0.25,
) -> tuple[npt.NDArray[np.float32], float]:
    """Compute InSAR Coherence Change Detection (CCD) and Damage Proxy Map (DPM).

    Parameters
    ----------
    coherence_pre : 2D array
        Pre-event interferometric coherence [0, 1].
    coherence_co : 2D array
        Co-seismic interferometric coherence [0, 1].
    min_pre_coherence : float
        Exclude naturally low-coherence surfaces (water, dense vegetation).
    threshold : float
        Threshold above which coherence loss is flagged as structural/surface damage.

    Returns
    -------
    dpm : 2D array
        Damage Proxy Map values normalized [0, 1].
    severe_ratio : float
        Percentage of valid pixels with severe coherence loss.
    """
    if coherence_pre.shape != coherence_co.shape:
        raise ValueError("Coherence arrays must have matching shapes")

    # Valid mask: areas that had stable coherence prior to the event
    valid_mask = coherence_pre >= min_pre_coherence

    # Relative Coherence Loss: Delta_gamma / gamma_pre
    # Higher loss indicates surface disruption / building collapse
    delta_gamma = np.clip(coherence_pre - coherence_co, 0.0, 1.0)
    dpm = np.zeros_like(coherence_pre, dtype=np.float32)

    with np.errstate(divide="ignore", invalid="ignore"):
        dpm[valid_mask] = np.clip(delta_gamma[valid_mask] / coherence_pre[valid_mask], 0.0, 1.0)

    severe_pixels = np.count_nonzero((dpm >= threshold) & valid_mask)
    total_valid = np.count_nonzero(valid_mask)
    severe_ratio = float(severe_pixels / total_valid) if total_valid > 0 else 0.0

    return dpm, severe_ratio


def unwrapped_phase_to_displacement(
    unwrapped_phase: npt.NDArray[np.float32],
    wavelength_m: float = SENTINEL1_WAVELENGTH_M,
) -> npt.NDArray[np.float32]:
    """Convert unwrapped phase (rad) to Line-of-Sight (LOS) displacement (m).

    d_LOS = - (lambda / 4*pi) * Delta_phi
    Negative displacement denotes movement away from the satellite.
    """
    factor = -wavelength_m / (4.0 * np.pi)
    displacement: npt.NDArray[np.float32] = (unwrapped_phase * factor).astype(np.float32)
    return displacement


def simulate_insar_damage_proxy(
    bounds: tuple[float, float, float, float],
    epicenter: tuple[float, float],
    magnitude: float,
    nrows: int = 100,
    ncols: int = 100,
    noise_level: float = 0.05,
    seed: int = 42,
) -> DamageProxyMapResult:
    """Generate a calibrated synthetic InSAR coherence loss field for testing or scenario replay.

    Simulates the characteristic coherence decay surrounding a fault rupture zone.
    """
    rng = np.random.default_rng(seed)
    min_lon, min_lat, max_lon, max_lat = bounds

    lons = np.linspace(min_lon, max_lon, ncols)
    lats = np.linspace(max_lat, min_lat, nrows)  # top to bottom
    grid_lon, grid_lat = np.meshgrid(lons, lats)

    # Distance to epicenter in degrees (~111 km/deg)
    dlat = (grid_lat - epicenter[1]) * 111.0
    dlon = (grid_lon - epicenter[0]) * 111.0 * np.cos(np.radians(epicenter[1]))
    dist_km = np.sqrt(dlat**2 + dlon**2)

    # Pre-event coherence: high on urban/dry surfaces (0.7-0.9), with random texture
    co_pre = 0.78 + rng.normal(0.0, noise_level, size=(nrows, ncols)).astype(np.float32)
    co_pre = np.clip(co_pre, 0.2, 0.98)

    # Co-seismic coherence drop proportional to rupture intensity and proximity
    rupture_radius_km = 10.0 ** (0.45 * magnitude - 2.0)
    damage_influence = np.exp(-(dist_km**2) / (2.0 * (rupture_radius_km * 0.8) ** 2))

    co_co = co_pre - (damage_influence * 0.65).astype(np.float32)
    co_co += rng.normal(0.0, noise_level, size=(nrows, ncols)).astype(np.float32)
    co_co = np.clip(co_co, 0.05, 0.95)

    dpm, severe_ratio = compute_coherence_loss(co_pre, co_co)

    resolution_deg = (max_lat - min_lat) / nrows

    return DamageProxyMapResult(
        dpm=dpm,
        coherence_pre=co_pre,
        coherence_co=co_co,
        severe_damage_ratio=severe_ratio,
        bounds=bounds,
        resolution_deg=resolution_deg,
    )


def write_cog(
    output_path: str,
    data: npt.NDArray[np.float32],
    bounds: tuple[float, float, float, float],
    crs: str = "EPSG:4326",
) -> None:
    """Write 2D float32 raster as GeoTIFF with spatial transform."""
    min_lon, min_lat, max_lon, max_lat = bounds
    nrows, ncols = data.shape
    transform = from_bounds(min_lon, min_lat, max_lon, max_lat, ncols, nrows)

    with rasterio.open(
        output_path,
        "w",
        driver="GTiff",
        height=nrows,
        width=ncols,
        count=1,
        dtype=rasterio.float32,
        crs=crs,
        transform=transform,
        compress="lzw",
    ) as dst:
        dst.write(data, 1)
