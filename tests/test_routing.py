"""Tests for Disaster Road Routing, Isochrones & Facility Location."""

from shapely.geometry import Polygon
from zemin.routing import (
    DemandPoint,
    DisasterRoadGraph,
    FacilityCandidate,
    create_sample_antakya_road_grid,
    generate_isochrone_polygon,
    solve_p_median_facility_location,
)


def test_shortest_path_blockage() -> None:
    graph = DisasterRoadGraph()
    graph.add_node(0, 36.20, 36.16)
    graph.add_node(1, 36.21, 36.16)
    graph.add_node(2, 36.22, 36.16)

    # Direct edge (0 -> 2) has high PGA & 4 collapsed buildings -> impassable
    graph.add_edge(0, 2, length_m=2000.0, pga_g=1.2, debris_collapse_count=4)
    # Detour edges (0 -> 1 -> 2) are intact
    graph.add_edge(0, 1, length_m=1200.0, pga_g=0.2, debris_collapse_count=0)
    graph.add_edge(1, 2, length_m=1200.0, pga_g=0.2, debris_collapse_count=0)

    path, cost = graph.shortest_path(0, 2)

    # Must take detour 0 -> 1 -> 2
    assert path == [0, 1, 2]
    assert cost < float("inf")


def test_isochrone_generation() -> None:
    grid = create_sample_antakya_road_grid(grid_n=4, spacing_deg=0.005)
    center_node = 5

    poly = generate_isochrone_polygon(grid, center_node, cutoff_minutes=15.0)
    assert poly is not None
    assert isinstance(poly, Polygon)
    assert poly.area > 0.0


def test_p_median_location_allocation() -> None:
    demand = [
        DemandPoint(id=1, lat=36.20, lon=36.15, weight=100.0),
        DemandPoint(id=2, lat=36.21, lon=36.15, weight=150.0),
        DemandPoint(id=3, lat=36.25, lon=36.20, weight=200.0),
    ]

    candidates = [
        FacilityCandidate(id=10, lat=36.205, lon=36.15),  # Close to clusters 1 & 2
        FacilityCandidate(id=20, lat=36.245, lon=36.20),  # Close to cluster 3
        FacilityCandidate(id=30, lat=36.350, lon=36.30),  # Far away
    ]

    chosen, cost = solve_p_median_facility_location(demand, candidates, p=2)

    assert len(chosen) == 2
    chosen_ids = {c.id for c in chosen}
    assert 10 in chosen_ids
    assert 20 in chosen_ids
    assert 30 not in chosen_ids


def test_shortest_path_disconnected_components() -> None:
    graph = DisasterRoadGraph()
    # Component 1
    graph.add_node(0, 36.20, 36.16)
    graph.add_node(1, 36.21, 36.16)
    graph.add_edge(0, 1, length_m=1000.0)

    # Component 2 (completely disconnected)
    graph.add_node(10, 36.50, 36.50)
    graph.add_node(11, 36.51, 36.50)
    graph.add_edge(10, 11, length_m=1000.0)

    # Disconnected search must return empty path and infinite distance without raising
    path, dist = graph.shortest_path(0, 10)
    assert path == []
    assert dist == float("inf")

    # Isolated node with no edges
    graph.add_node(99, 36.60, 36.60)
    path_iso, dist_iso = graph.shortest_path(99, 0)
    assert path_iso == []
    assert dist_iso == float("inf")

    # Non-existent nodes
    path_none, dist_none = graph.shortest_path(999, 0)
    assert path_none == []
    assert dist_none == float("inf")

    path_none2, dist_none2 = graph.shortest_path(0, 999)
    assert path_none2 == []
    assert dist_none2 == float("inf")

    # Origin == Destination
    path_same, dist_same = graph.shortest_path(0, 0)
    assert path_same == [0]
    assert dist_same == 0.0


def test_p_median_empty_cases() -> None:
    candidates = [FacilityCandidate(id=1, lat=36.20, lon=36.15)]
    # Empty demand
    chosen, cost = solve_p_median_facility_location([], candidates, p=1)
    assert len(chosen) == 1
    assert cost == 0.0

    # Empty candidates
    chosen_empty, cost_empty = solve_p_median_facility_location([], [], p=1)
    assert chosen_empty == []
    assert cost_empty == 0.0


