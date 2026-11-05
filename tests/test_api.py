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


def test_compute_response_spectrum_endpoint() -> None:
    payload = {
        "magnitude": 7.8,
        "depth_km": 8.6,
        "lat": 36.202,
        "lon": 36.160,
        "vs30": 360.0,
        "s_ds": 1.5,
        "s_d1": 0.45,
    }
    res = client.post("/api/v1/shakemap/response-spectrum", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "periods" in data
    assert "sa_g" in data
    assert "tbdy_design_sa_g" in data
    assert len(data["sa_g"]) == len(data["periods"])
    assert max(data["sa_g"]) > 1.0


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


def test_ogc_conformance_endpoint() -> None:
    res = client.get("/conformance")
    assert res.status_code == 200
    data = res.json()
    assert "conformsTo" in data
    assert any("req/core" in item for item in data["conformsTo"])


def test_ogc_collections_endpoint() -> None:
    res = client.get("/collections")
    assert res.status_code == 200
    data = res.json()
    assert "collections" in data
    col_ids = [c["id"] for c in data["collections"]]
    assert "active-faults" in col_ids
    assert "strong-motion-stations" in col_ids


def test_ogc_active_faults_items_endpoint() -> None:
    res = client.get("/collections/active-faults/items")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    first = data["features"][0]
    assert first["geometry"]["type"] == "LineString"
    assert "name" in first["properties"]
    assert "mechanism" in first["properties"]

    # Test spatial bbox filter
    res_bbox = client.get("/collections/active-faults/items?bbox=36.0,36.0,37.0,37.0")
    assert res_bbox.status_code == 200
    data_bbox = res_bbox.json()
    assert data_bbox["type"] == "FeatureCollection"


def test_ogc_strong_motion_stations_items_endpoint() -> None:
    res = client.get("/collections/strong-motion-stations/items")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 7
    first = data["features"][0]
    assert first["geometry"]["type"] == "Point"
    assert "pga_recorded_g" in first["properties"]


def test_liquefaction_endpoint() -> None:
    res = client.get("/collections/liquefaction-zones/items?pga_g=1.1&magnitude=7.8")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    first = data["features"][0]
    assert first["geometry"]["type"] == "Polygon"
    assert "lpi" in first["properties"]
    assert "hazard_class" in first["properties"]


