"""Disaster Network Routing, Stochastic Isochrones & Location-Allocation Engine.

Implements emergency routing under debris blockage, post-disaster reachability
isochrones, and facility location-allocation (p-median / maximum coverage).
"""

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from shapely.geometry import MultiPoint, Point, Polygon


@dataclass
class NetworkNode:
    id: int
    lat: float
    lon: float


@dataclass
class NetworkEdge:
    u: int
    v: int
    length_m: float
    base_speed_kmh: float = 40.0
    pga_g: float = 0.0
    debris_collapse_count: int = 0

    @property
    def failure_probability(self) -> float:
        """Calculate blockage probability based on ground shaking and adjacent debris."""
        # Baseline structural road cracking from PGA
        p_shaking = 1.0 - math.exp(-1.8 * (self.pga_g**2))
        # Additional debris obstacle risk (each collapsed building near roadway)
        p_debris = min(0.95, self.debris_collapse_count * 0.25)
        # Combined independent failure probability
        return min(0.999, p_shaking + p_debris - (p_shaking * p_debris))

    @property
    def effective_travel_time_sec(self) -> float:
        """Expected travel time taking into account failure probability."""
        free_flow_time = (self.length_m / 1000.0) / (self.base_speed_kmh / 3600.0)
        p_fail = self.failure_probability
        if p_fail >= 0.95:
            return float("inf")  # Completely impassable
        # Risk-inflated impedance
        return free_flow_time / (1.0 - p_fail)


class DisasterRoadGraph:
    """Directed / Bidirectional graph representation of a road network."""

    def __init__(self) -> None:
        self.nodes: dict[int, NetworkNode] = {}
        self.adj: dict[int, list[NetworkEdge]] = defaultdict(list)

    def add_node(self, node_id: int, lat: float, lon: float) -> None:
        self.nodes[node_id] = NetworkNode(node_id, lat, lon)

    def add_edge(
        self,
        u: int,
        v: int,
        length_m: float,
        base_speed_kmh: float = 40.0,
        pga_g: float = 0.0,
        debris_collapse_count: int = 0,
        bidirectional: bool = True,
    ) -> None:
        edge1 = NetworkEdge(u, v, length_m, base_speed_kmh, pga_g, debris_collapse_count)
        self.adj[u].append(edge1)
        if bidirectional:
            edge2 = NetworkEdge(v, u, length_m, base_speed_kmh, pga_g, debris_collapse_count)
            self.adj[v].append(edge2)

    def shortest_path(self, origin: int, destination: int) -> tuple[list[int], float]:
        """Compute least-risk shortest path using Dijkstra algorithm."""
        if origin not in self.nodes or destination not in self.nodes:
            return [], float("inf")

        if origin == destination:
            return [origin], 0.0

        dist: dict[int, float] = {node: float("inf") for node in self.nodes}
        parent: dict[int, int | None] = {node: None for node in self.nodes}
        dist[origin] = 0.0

        pq: list[tuple[float, int]] = [(0.0, origin)]

        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            if u == destination:
                break

            for edge in self.adj[u]:
                cost = edge.effective_travel_time_sec
                if cost == float("inf"):
                    continue
                if edge.v not in dist:
                    continue
                if dist[u] + cost < dist[edge.v]:
                    dist[edge.v] = dist[u] + cost
                    parent[edge.v] = u
                    heapq.heappush(pq, (dist[edge.v], edge.v))

        if dist[destination] == float("inf"):
            return [], float("inf")

        path: list[int] = []
        curr: int | None = destination
        while curr is not None:
            path.append(curr)
            curr = parent[curr]
        path.reverse()
        return path, dist[destination]

    def compute_isochrone_nodes(self, origin: int, max_time_sec: float) -> dict[int, float]:
        """Returns all nodes reachable within max_time_sec from origin with their travel times."""
        if origin not in self.nodes:
            return {}

        dist: dict[int, float] = {node: float("inf") for node in self.nodes}
        dist[origin] = 0.0
        pq: list[tuple[float, int]] = [(0.0, origin)]

        reachable: dict[int, float] = {}

        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            if d <= max_time_sec:
                reachable[u] = d

            for edge in self.adj[u]:
                cost = edge.effective_travel_time_sec
                if cost == float("inf"):
                    continue
                if edge.v not in dist:
                    continue
                nxt_d = dist[u] + cost
                if nxt_d <= max_time_sec and nxt_d < dist[edge.v]:
                    dist[edge.v] = nxt_d
                    heapq.heappush(pq, (nxt_d, edge.v))

        return reachable


def generate_isochrone_polygon(
    graph: DisasterRoadGraph,
    origin_node: int,
    cutoff_minutes: float,
) -> Polygon | None:
    """Generate a convex hull polygon contour representing the reachability zone."""
    cutoff_sec = cutoff_minutes * 60.0
    reachable_nodes = graph.compute_isochrone_nodes(origin_node, cutoff_sec)

    if len(reachable_nodes) < 3:
        return None

    points = [
        Point(graph.nodes[nid].lon, graph.nodes[nid].lat)
        for nid in reachable_nodes
        if nid in graph.nodes
    ]
    hull = MultiPoint(points).convex_hull
    if isinstance(hull, Polygon):
        return hull
    return None


@dataclass
class DemandPoint:
    id: int
    lat: float
    lon: float
    weight: float  # e.g. population or estimated injured count


@dataclass
class FacilityCandidate:
    id: int
    lat: float
    lon: float
    capacity: int = 1000


def solve_p_median_facility_location(
    demand: list[DemandPoint],
    candidates: list[FacilityCandidate],
    p: int,
) -> tuple[list[FacilityCandidate], float]:
    """Solve p-Median Location-Allocation using the Teitz-Bart (1968) heuristic.

    Selects p candidate locations that minimize total demand-weighted distance.
    Guarantees monotonic improvement and rapid convergence.
    """
    if not candidates or p <= 0:
        return [], 0.0

    if not demand:
        return candidates[: min(p, len(candidates))], 0.0

    if p >= len(candidates):
        return candidates, 0.0

    # Distance matrix D[i][j]: demand i to candidate j (in km)
    num_dem = len(demand)
    num_cand = len(candidates)
    dist_matrix = np.zeros((num_dem, num_cand), dtype=np.float64)

    for i, d in enumerate(demand):
        for j, c in enumerate(candidates):
            # Great circle approx
            dlat = (d.lat - c.lat) * 111.0
            dlon = (d.lon - c.lon) * 111.0 * math.cos(math.radians((d.lat + c.lat) / 2.0))
            dist_matrix[i, j] = math.sqrt(dlat**2 + dlon**2)

    weights = np.array([d.weight for d in demand], dtype=np.float64)

    def total_cost(selected_indices: set[int]) -> float:
        sub_dist = dist_matrix[:, list(selected_indices)]
        min_dists = np.min(sub_dist, axis=1)
        cost: float = float(np.sum(weights * min_dists))
        return cost

    # Initial selection: greedy selection of p facilities
    current_selected: set[int] = set()
    for _ in range(p):
        best_cand = -1
        best_val = float("inf")
        for j in range(num_cand):
            if j not in current_selected:
                test_set = current_selected | {j}
                val = total_cost(test_set)
                if val < best_val:
                    best_val = val
                    best_cand = j
        if best_cand != -1:
            current_selected.add(best_cand)

    # Teitz-Bart Local Search Vertex Substitution
    improved = True
    current_val = total_cost(current_selected)

    while improved:
        improved = False
        unselected = set(range(num_cand)) - current_selected
        for u in unselected:
            for s in list(current_selected):
                neighbor = (current_selected - {s}) | {u}
                neighbor_val = total_cost(neighbor)
                if neighbor_val < current_val - 1e-4:
                    current_selected = neighbor
                    current_val = neighbor_val
                    improved = True
                    break
            if improved:
                break

    chosen_candidates = [candidates[idx] for idx in sorted(current_selected)]
    return chosen_candidates, current_val


def create_sample_antakya_road_grid(
    center_lon: float = 36.160,
    center_lat: float = 36.202,
    grid_n: int = 5,
    spacing_deg: float = 0.005,
    pga_center: float = 0.65,
) -> DisasterRoadGraph:
    """Generate a sample synthetic street grid for Antakya center with realistic seismic damage."""
    graph = DisasterRoadGraph()
    node_id = 0
    grid_coords: dict[tuple[int, int], int] = {}

    for r in range(grid_n):
        for c in range(grid_n):
            lat = center_lat + (r - grid_n // 2) * spacing_deg
            lon = center_lon + (c - grid_n // 2) * spacing_deg
            graph.add_node(node_id, lat, lon)
            grid_coords[(r, c)] = node_id
            node_id += 1

    # Connect adjacent horizontal and vertical edges
    length_m = spacing_deg * 111_000.0

    for r in range(grid_n):
        for c in range(grid_n):
            u = grid_coords[(r, c)]
            # Horizontal
            if c + 1 < grid_n:
                v = grid_coords[(r, c + 1)]
                # Near center gets higher PGA and debris
                dist_from_mid = abs(r - grid_n // 2) + abs(c - grid_n // 2)
                pga = max(0.1, pga_center - dist_from_mid * 0.1)
                debris = 2 if dist_from_mid == 0 else (1 if dist_from_mid == 1 else 0)
                graph.add_edge(
                    u, v, length_m, base_speed_kmh=40.0, pga_g=pga, debris_collapse_count=debris
                )
            # Vertical
            if r + 1 < grid_n:
                v = grid_coords[(r + 1, c)]
                dist_from_mid = abs(r - grid_n // 2) + abs(c - grid_n // 2)
                pga = max(0.1, pga_center - dist_from_mid * 0.1)
                debris = 2 if dist_from_mid == 0 else (1 if dist_from_mid == 1 else 0)
                graph.add_edge(
                    u, v, length_m, base_speed_kmh=40.0, pga_g=pga, debris_collapse_count=debris
                )

    return graph
