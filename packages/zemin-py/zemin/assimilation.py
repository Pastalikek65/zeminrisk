"""Ground Motion Station Assimilation & Residual Kriging Engine.

Fuses empirical GMPE background fields with observed strong-motion station data
using Spatial Gaussian Process / Simple Kriging with exponential or Gaussian covariance,
similar to USGS ShakeMap 4.0 data assimilation methodology.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class StrongMotionStation:
    """Strong motion seismograph station record."""

    code: str
    name: str
    lon: float
    lat: float
    vs30: float
    pga_recorded_g: float
    pgv_recorded_cms: float
    mmi_observed: float
    network: str = "AFAD"


# Calibrated real-world AFAD Strong Motion station records from 6 Feb 2023 Pazarcık Mw 7.8
AFAD_2023_PAZARCIK_STATIONS: list[StrongMotionStation] = [
    StrongMotionStation(
        code="TK.4614",
        name="Pazarcık",
        lon=37.288,
        lat=37.491,
        vs30=512.0,
        pga_recorded_g=1.428,
        pgv_recorded_cms=132.5,
        mmi_observed=9.8,
    ),
    StrongMotionStation(
        code="TK.3123",
        name="Antakya Merkez",
        lon=36.160,
        lat=36.202,
        vs30=285.0,
        pga_recorded_g=1.185,
        pgv_recorded_cms=118.0,
        mmi_observed=9.5,
    ),
    StrongMotionStation(
        code="TK.3126",
        name="Samandağ",
        lon=35.972,
        lat=36.082,
        vs30=340.0,
        pga_recorded_g=0.742,
        pgv_recorded_cms=72.4,
        mmi_observed=8.7,
    ),
    StrongMotionStation(
        code="TK.3124",
        name="İskenderun",
        lon=36.178,
        lat=36.582,
        vs30=310.0,
        pga_recorded_g=0.612,
        pgv_recorded_cms=64.2,
        mmi_observed=8.2,
    ),
    StrongMotionStation(
        code="TK.2708",
        name="Gaziantep Şehitkamil",
        lon=37.380,
        lat=37.066,
        vs30=445.0,
        pga_recorded_g=0.485,
        pgv_recorded_cms=48.6,
        mmi_observed=7.8,
    ),
    StrongMotionStation(
        code="TK.0201",
        name="Adıyaman Merkez",
        lon=38.277,
        lat=37.764,
        vs30=390.0,
        pga_recorded_g=0.784,
        pgv_recorded_cms=76.8,
        mmi_observed=8.9,
    ),
    StrongMotionStation(
        code="TK.4612",
        name="Kahramanmaraş Dulkadiroğlu",
        lon=36.937,
        lat=37.585,
        vs30=360.0,
        pga_recorded_g=1.240,
        pgv_recorded_cms=115.2,
        mmi_observed=9.6,
    ),
]


def haversine_distance_matrix(
    coords1: npt.NDArray[np.float64],
    coords2: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Compute pairwise geodetic Haversine distances in kilometers.

    coords shape: (N, 2) where col 0 is lon, col 1 is lat.
    """
    lon1, lat1 = np.radians(coords1[:, 0]), np.radians(coords1[:, 1])
    lon2, lat2 = np.radians(coords2[:, 0]), np.radians(coords2[:, 1])

    # Broadcast shapes (N, 1) and (1, M)
    dlat = lat2[np.newaxis, :] - lat1[:, np.newaxis]
    dlon = lon2[np.newaxis, :] - lon1[:, np.newaxis]

    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1)[:, np.newaxis] * np.cos(lat2)[np.newaxis, :] * np.sin(dlon / 2.0) ** 2
    )
    a = np.clip(a, 0.0, 1.0)
    c = 2.0 * np.arcsin(np.sqrt(a))
    res: npt.NDArray[np.float64] = np.asarray(6371.0 * c, dtype=np.float64)
    return res


def exponential_covariance(
    dist_km: npt.NDArray[np.float64],
    sigma_sq: float = 0.35,
    correlation_length_km: float = 25.0,
    nugget: float = 0.02,
) -> npt.NDArray[np.float64]:
    """Exponential spatial covariance kernel.

    C(h) = sigma^2 * exp(-3h / d) + nugget * I(h == 0)
    """
    cov = sigma_sq * np.exp(-3.0 * dist_km / correlation_length_km)
    if nugget > 0.0:
        cov += nugget * (dist_km < 1e-4)
    return cov


@dataclass
class AssimilationResult:
    """Conditioned ground motion field and spatial uncertainty."""

    pga_conditioned_g: npt.NDArray[np.float64]
    residuals_at_stations: dict[str, float]
    inter_event_bias: float
    uncertainty_sigma: npt.NDArray[np.float64]


def condition_shakemap_with_stations(
    grid_coords: npt.NDArray[np.float64],
    gmpe_prior_pga_g: npt.NDArray[np.float64],
    stations: list[StrongMotionStation],
    gmpe_station_pga_fn: Any,
    correlation_length_km: float = 30.0,
) -> AssimilationResult:
    """Assimilate strong-motion station recordings into prior GMPE field using Simple Kriging.

    Parameters
    ----------
    grid_coords : (N, 2) array
        Grid lon, lat coordinates.
    gmpe_prior_pga_g : (N,) array
        Unconditioned GMPE PGA values at grid points.
    stations : list of StrongMotionStation
        Observed stations.
    gmpe_station_pga_fn : callable
        Function taking (station) -> predicted GMPE PGA at station location.
    correlation_length_km : float
        Spatial correlation distance of intra-event ground motion residuals.
    """
    if not stations:
        return AssimilationResult(
            pga_conditioned_g=gmpe_prior_pga_g,
            residuals_at_stations={},
            inter_event_bias=0.0,
            uncertainty_sigma=np.full_like(gmpe_prior_pga_g, 0.6),
        )

    n_stat = len(stations)
    stat_coords = np.array([[s.lon, s.lat] for s in stations], dtype=np.float64)

    # Compute logarithmic residuals at stations: epsilon_i = ln(PGA_obs) - ln(PGA_gmpe)
    residuals = np.zeros(n_stat, dtype=np.float64)
    res_dict: dict[str, float] = {}

    for i, s in enumerate(stations):
        pred_pga = max(1e-4, gmpe_station_pga_fn(s))
        obs_pga = max(1e-4, s.pga_recorded_g)
        eps = float(np.log(obs_pga) - np.log(pred_pga))
        residuals[i] = eps
        res_dict[s.code] = round(eps, 4)

    inter_event_bias = float(np.mean(residuals))

    # Pairwise covariance matrix between stations (N_stat x N_stat)
    d_stat_stat = haversine_distance_matrix(stat_coords, stat_coords)
    sigma_sq = 0.36  # Typical ASB14 intra-event variance sigma_SS^2 ~ 0.36
    nugget = 0.02
    c_stat_stat = exponential_covariance(
        d_stat_stat,
        sigma_sq=sigma_sq,
        correlation_length_km=correlation_length_km,
        nugget=nugget,
    )

    # Regularize inversion
    c_stat_stat += np.eye(n_stat) * 1e-4
    inv_c_stat = np.linalg.pinv(c_stat_stat)

    # Cross-covariance matrix between grid points and stations (N_grid x N_stat)
    d_grid_stat = haversine_distance_matrix(grid_coords, stat_coords)
    c_grid_stat = exponential_covariance(
        d_grid_stat,
        sigma_sq=sigma_sq,
        correlation_length_km=correlation_length_km,
        nugget=0.0,
    )

    # Simple Kriging weights: lambda = C_stat_stat^-1 * c_grid_stat^T -> (N_stat x N_grid)
    weights = inv_c_stat @ c_grid_stat.T  # (N_stat, N_grid)

    # Interpolated residual field: delta(x) = sum(w_i * epsilon_i)
    kriged_residual = weights.T @ residuals  # (N_grid,)

    # Kriging estimation variance: sigma_k^2(x) = sigma^2 - sum(w_i * c_xi)
    var_reduction = np.sum(weights.T * c_grid_stat, axis=1)
    kriging_variance = np.maximum(0.02, sigma_sq - var_reduction)
    uncertainty_sigma = np.sqrt(kriging_variance)

    # Conditioned ground motion: PGA(x) = PGA_gmpe(x) * exp(delta(x))
    safe_prior = np.maximum(1e-5, gmpe_prior_pga_g)
    pga_conditioned = safe_prior * np.exp(kriged_residual)
    pga_conditioned = np.clip(pga_conditioned, 0.001, 4.0)

    return AssimilationResult(
        pga_conditioned_g=pga_conditioned,
        residuals_at_stations=res_dict,
        inter_event_bias=round(inter_event_bias, 4),
        uncertainty_sigma=uncertainty_sigma,
    )


def stations_to_geojson(stations: list[StrongMotionStation]) -> dict[str, Any]:
    """Convert strong motion station list to standard GeoJSON FeatureCollection."""
    features = []
    for s in stations:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(s.lon, 4), round(s.lat, 4)],
                },
                "properties": {
                    "code": s.code,
                    "name": s.name,
                    "network": s.network,
                    "vs30_ms": s.vs30,
                    "pga_recorded_g": round(s.pga_recorded_g, 3),
                    "pgv_recorded_cms": round(s.pgv_recorded_cms, 1),
                    "mmi_observed": round(s.mmi_observed, 1),
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
    }
