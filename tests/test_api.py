"""Unit and integration tests for FastAPI disaster simulation endpoints."""

from fastapi.testclient import TestClient
from zemin.api import app

client = TestClient(app)


def test_healthz_endpoint() -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "zeminrisk-api"


def test_simulate_shakemap_endpoint() -> None:
    payload = {
        "magnitude": 7.8,
        "depth_km": 8.6,
        "epicenter_lat": 37.288,
        "epicenter_lon": 37.043,
        "fault_mechanism": "strike-slip",
        "default_vs30": 360.0,
        "grid_resolution": 20,
    }
    res = client.post("/api/v1/shakemap/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "metadata" in data
    assert "geojson" in data
    assert data["geojson"]["type"] == "FeatureCollection"
    assert len(data["geojson"]["features"]) > 0
    # PGA and MMI values should be physically realistic for M7.8
    assert data["metadata"]["max_pga_g"] > 0.5


def test_simulate_insar_dpm_endpoint() -> None:
    payload = {
        "min_lon": 36.12,
        "min_lat": 36.17,
        "max_lon": 36.20,
        "max_lat": 36.24,
        "epicenter_lon": 37.043,
        "epicenter_lat": 37.288,
        "magnitude": 7.8,
        "resolution": 15,
    }
    res = client.post("/api/v1/insar/simulate-dpm", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "geojson" in data
    assert data["geojson"]["type"] == "FeatureCollection"
    assert 0.0 <= data["severe_damage_ratio"] <= 1.0


def test_damage_sample_antakya_endpoint() -> None:
    payload = {
        "pga_g": 0.85,
        "building_count": 30,
    }
    res = client.post("/api/v1/damage/sample-antakya", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["summary"]["total_buildings"] == 30
    assert data["summary"]["collapsed_buildings"] > 0
    assert len(data["geojson"]["features"]) == 30


def test_routing_isochrone_endpoint() -> None:
    payload = {
        "center_lon": 36.160,
        "center_lat": 36.202,
        "cutoff_minutes": 10.0,
    }
    res = client.post("/api/v1/routing/isochrone", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "isochrone_geojson" in data
    assert data["isochrone_geojson"]["type"] == "Polygon"
    assert len(data["isochrone_geojson"]["coordinates"][0]) >= 3
