"""Tests for Strong-Motion Station Assimilation & Residual Kriging."""

import numpy as np
import pytest
from zemin.assimilation import (
    AFAD_2023_PAZARCIK_STATIONS,
    StrongMotionStation,
    condition_shakemap_with_stations,
    exponential_covariance,
    haversine_distance_matrix,
    stations_to_geojson,
)


def test_haversine_distance_matrix() -> None:
    c1 = np.array([[36.0, 36.0], [37.0, 37.0]], dtype=np.float64)
    dist = haversine_distance_matrix(c1, c1)
    assert dist.shape == (2, 2)
    assert dist[0, 0] == pytest.approx(0.0, abs=1e-5)
    assert dist[1, 1] == pytest.approx(0.0, abs=1e-5)
    assert dist[0, 1] == pytest.approx(dist[1, 0], rel=1e-5)
    assert dist[0, 1] > 100.0  # Approx 140 km


def test_exponential_covariance() -> None:
    dists = np.array([0.0, 10.0, 50.0, 100.0], dtype=np.float64)
    cov = exponential_covariance(dists, sigma_sq=0.35, correlation_length_km=25.0)
    # Monotonically decaying with distance
    assert cov[0] > cov[1] > cov[2] > cov[3]
    assert np.all(cov >= 0.0)


def test_condition_shakemap_with_stations() -> None:
    # Station at (36.16, 36.20) with observed PGA 1.0g
    st = StrongMotionStation(
        code="TEST.01",
        name="Test Station",
        lon=36.16,
        lat=36.20,
        vs30=360.0,
        pga_recorded_g=1.0,
        pgv_recorded_cms=90.0,
        mmi_observed=9.0,
    )

    # Prior GMPE predicted lower: 0.5g
    def gmpe_fn(_: StrongMotionStation) -> float:
        return 0.5

    # Grid point 1: exactly at station location
    # Grid point 2: far away (150 km)
    grid_coords = np.array([[36.16, 36.20], [38.00, 38.00]], dtype=np.float64)
    prior_pga = np.array([0.5, 0.5], dtype=np.float64)

    res = condition_shakemap_with_stations(
        grid_coords,
        prior_pga,
        [st],
        gmpe_fn,
        correlation_length_km=30.0,
    )

    assert res.pga_conditioned_g.shape == (2,)
    # Near station, conditioned PGA should be pulled upward toward observed 1.0g
    assert res.pga_conditioned_g[0] > 0.8
    # Far from station, conditioned PGA stays closer to prior 0.5g
    assert res.pga_conditioned_g[1] < res.pga_conditioned_g[0]
    # Uncertainty at station is lower than far away
    assert res.uncertainty_sigma[0] < res.uncertainty_sigma[1]


def test_stations_to_geojson() -> None:
    gj = stations_to_geojson(AFAD_2023_PAZARCIK_STATIONS)
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == len(AFAD_2023_PAZARCIK_STATIONS)
    first = gj["features"][0]
    assert "geometry" in first
    assert "properties" in first
    assert "pga_recorded_g" in first["properties"]
    assert "vs30_ms" in first["properties"]

