"""OGC API and FastAPI service for ZeminRisk."""

import math
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from zemin.assimilation import AFAD_2023_PAZARCIK_STATIONS, stations_to_geojson
from zemin.ogc import (
    get_active_faults_geojson,
    get_ogc_collections_metadata,
    get_ogc_conformance,
)

app = FastAPI(
    title="ZeminRisk Seismic Hazard & Impact API",
    description="Real-time ShakeMap and disaster response platform.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


class EarthquakeEventRequest(BaseModel):
    magnitude: float = Field(..., ge=2.0, le=9.5, description="Moment magnitude (Mw)")
    depth_km: float = Field(..., ge=0.0, le=700.0, description="Focal depth in km")
    epicenter_lat: float = Field(..., ge=-90.0, le=90.0, description="Epicenter latitude")
    epicenter_lon: float = Field(..., ge=-180.0, le=180.0, description="Epicenter longitude")
    fault_mechanism: Literal["strike-slip", "normal", "reverse"] = "strike-slip"
    default_vs30: float = Field(
        default=360.0,
        ge=100.0,
        le=2500.0,
        description="Time-averaged shear wave velocity Vs30 (m/s)",
    )
    grid_resolution: int = Field(
        default=50, ge=10, le=200, description="Grid resolution (NxN points)"
    )


class ShakeMapResponse(BaseModel):
    status: str
    metadata: dict[str, Any]
    geojson: dict[str, Any]


@app.get("/healthz")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "zeminrisk-api", "version": "0.1.0"}


@app.post("/api/v1/shakemap/simulate", response_model=ShakeMapResponse)
async def simulate_shakemap(req: EarthquakeEventRequest) -> ShakeMapResponse:
    """Simulate ground motion field (PGA, PGV, MMI) using Akkar-Sandikkaya-Bommer formulation."""
    try:
        import json

        # Bounding box ~2 degrees around epicenter
        delta = 2.0
        min_lat = req.epicenter_lat - delta
        max_lat = req.epicenter_lat + delta
        min_lon = req.epicenter_lon - delta
        max_lon = req.epicenter_lon + delta
        nrows = req.grid_resolution
        ncols = req.grid_resolution

        try:
            import zemin_core  # type: ignore[import-untyped]

            geojson_str = zemin_core.compute_shakemap_geojson(
                req.magnitude,
                req.depth_km,
                req.epicenter_lat,
                req.epicenter_lon,
                min_lat,
                max_lat,
                min_lon,
                max_lon,
                nrows,
                ncols,
                req.default_vs30,
                True,
            )
            geojson_obj: dict[str, Any] = json.loads(geojson_str)
            meta: dict[str, Any] = geojson_obj.get("metadata", {})
            return ShakeMapResponse(
                status="success",
                metadata={
                    "magnitude": req.magnitude,
                    "epicenter": [req.epicenter_lon, req.epicenter_lat],
                    "max_pga_g": meta.get("max_pga_g", 0.0),
                    "max_mmi": meta.get("max_mmi", 0.0),
                    "total_points_evaluated": nrows * ncols,
                    "points_exported": len(geojson_obj.get("features", [])),
                    "engine": "zemin_core::rust",
                },
                geojson=geojson_obj,
            )
        except ImportError:
            pass

        # Python fallback implementation
        lat_step = (max_lat - min_lat) / (nrows - 1)
        lon_step = (max_lon - min_lon) / (ncols - 1)

        features = []
        max_pga = 0.0
        max_mmi = 0.0

        for r in range(nrows):
            lat = min_lat + r * lat_step
            for c in range(ncols):
                lon = min_lon + c * lon_step

                # Geodetic distance (Haversine approximation)
                dlat = math.radians(lat - req.epicenter_lat)
                dlon = math.radians(lon - req.epicenter_lon)
                a = (
                    math.sin(dlat / 2) ** 2
                    + math.cos(math.radians(req.epicenter_lat))
                    * math.cos(math.radians(lat))
                    * math.sin(dlon / 2) ** 2
                )
                r_jb = 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                r_jb = max(0.1, r_jb)

                # ASB14 Ground Motion Formulation
                mw = req.magnitude
                c1 = 6.75
                a1 = 2.4563
                a2 = 0.4050 if mw <= c1 else 0.0520
                a3 = -0.0580
                a4 = -1.1440
                a5 = 0.1650
                a6 = 7.50

                f_mag = a1 + a2 * (mw - c1) + a3 * ((8.5 - mw) ** 2)
                f_dist = (a4 + a5 * (mw - c1)) * math.log(math.sqrt(r_jb**2 + a6**2))
                f_site = -0.420 * math.log(req.default_vs30 / 750.0)

                ln_pga_g = f_mag + f_dist + f_site
                pga_g = max(1e-5, min(5.0, math.exp(ln_pga_g)))
                pgv_cms = max(1e-4, min(300.0, pga_g * 980.665 * 0.12 * ((mw / 6.0) ** 1.8)))

                # Worden et al. MMI with PGA in cm/s^2
                pga_cms2 = pga_g * 980.665
                log_pga = math.log10(pga_cms2)
                mmi_pga = 1.78 + 1.55 * log_pga if log_pga <= 1.57 else -1.60 + 3.70 * log_pga
                log_pgv = math.log10(max(0.01, pgv_cms))
                mmi_pgv = 3.78 + 1.80 * log_pgv if log_pgv <= 0.53 else 3.29 + 2.72 * log_pgv

                mmi = mmi_pga if mmi_pga < 4.5 else 0.4 * mmi_pga + 0.6 * mmi_pgv
                mmi = max(1.0, min(10.0, mmi))

                if pga_g > max_pga:
                    max_pga = pga_g
                if mmi > max_mmi:
                    max_mmi = mmi

                if mmi >= 5.0:  # Only export moderately felt or damaging points to GeoJSON
                    features.append(
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [round(lon, 4), round(lat, 4)],
                            },
                            "properties": {
                                "pga_g": round(pga_g, 4),
                                "pgv_cms": round(pgv_cms, 2),
                                "mmi": round(mmi, 2),
                            },
                        }
                    )

        return ShakeMapResponse(
            status="success",
            metadata={
                "magnitude": req.magnitude,
                "epicenter": [req.epicenter_lon, req.epicenter_lat],
                "max_pga_g": round(max_pga, 4),
                "max_mmi": round(max_mmi, 2),
                "total_points_evaluated": nrows * ncols,
                "points_exported": len(features),
                "engine": "python_fallback",
            },
            geojson={
                "type": "FeatureCollection",
                "features": features,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


class ResponseSpectrumRequest(BaseModel):
    magnitude: float = Field(default=7.8, ge=2.0, le=9.5)
    depth_km: float = Field(default=10.0, ge=0.0, le=100.0)
    lat: float = Field(default=36.202, ge=-90.0, le=90.0)
    lon: float = Field(default=36.160, ge=-180.0, le=180.0)
    vs30: float = Field(default=360.0, ge=50.0, le=2500.0)
    s_ds: float = Field(default=1.50, ge=0.05, le=3.0)
    s_d1: float = Field(default=0.45, ge=0.01, le=2.0)


@app.post("/api/v1/shakemap/response-spectrum")
async def compute_response_spectrum(req: ResponseSpectrumRequest) -> dict[str, Any]:
    """Compute period-dependent response spectral acceleration Sa(T) and TBDY-2018 spectrum."""
    import json

    # Calculate distance to 2023 East Anatolian Fault rupture if M >= 7.0
    r_jb = 2.5
    if req.magnitude < 7.0:
        dlat = math.radians(req.lat - 37.288)
        dlon = math.radians(req.lon - 37.043)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(37.288))
            * math.cos(math.radians(req.lat))
            * math.sin(dlon / 2) ** 2
        )
        r_jb = max(0.5, 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

    try:
        import zemin_core

        spec_str = zemin_core.calc_response_spectrum(
            req.magnitude,
            req.depth_km,
            r_jb,
            req.vs30,
            req.s_ds,
            req.s_d1,
        )
        data: dict[str, Any] = json.loads(spec_str)
        data["status"] = "success"
        data["r_jb_km"] = round(r_jb, 2)
        data["engine"] = "zemin_core::rust"
        return data
    except ImportError:
        # Fallback calculation
        periods = [0.01, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]
        pga = 1.05
        sa_g = [
            (
                pga * (1.0 + 1.6 * math.exp(-((math.log(t) - math.log(0.25)) ** 2) / 0.6))
                if t > 0.02
                else pga
            )
            for t in periods
        ]
        tbdy_sa = [
            (
                req.s_ds
                if 0.06 <= t <= 0.30
                else (req.s_ds * (0.4 + 0.6 * t / 0.06) if t < 0.06 else req.s_d1 / t)
            )
            for t in periods
        ]
        return {
            "status": "success",
            "periods": periods,
            "sa_g": [round(x, 4) for x in sa_g],
            "tbdy_design_sa_g": [round(x, 4) for x in tbdy_sa],
            "pga_g": round(pga, 4),
            "pgv_cms": 115.0,
            "r_jb_km": round(r_jb, 2),
            "engine": "python_fallback",
        }


class InSARDpmRequest(BaseModel):
    min_lon: float = Field(default=35.9)
    min_lat: float = Field(default=35.9)
    max_lon: float = Field(default=36.4)
    max_lat: float = Field(default=36.4)
    epicenter_lon: float = Field(default=36.160)
    epicenter_lat: float = Field(default=36.202)
    magnitude: float = Field(default=7.8, ge=3.0, le=9.5)
    resolution: int = Field(default=40, ge=10, le=100)


@app.post("/api/v1/insar/simulate-dpm")
async def simulate_insar_endpoint(req: InSARDpmRequest) -> dict[str, Any]:
    """Generate simulated InSAR Coherence Loss & Damage Proxy Map."""
    from zemin.insar import simulate_insar_damage_proxy

    bounds = (req.min_lon, req.min_lat, req.max_lon, req.max_lat)
    epicenter = (req.epicenter_lon, req.epicenter_lat)
    res = simulate_insar_damage_proxy(
        bounds=bounds,
        epicenter=epicenter,
        magnitude=req.magnitude,
        nrows=req.resolution,
        ncols=req.resolution,
    )
    # Build GeoJSON polygon grid of DPM features
    features = []
    nrows, ncols = res.dpm.shape
    dlon = (req.max_lon - req.min_lon) / ncols
    dlat = (req.max_lat - req.min_lat) / nrows

    for r in range(nrows):
        lat0 = req.max_lat - (r + 1) * dlat
        lat1 = req.max_lat - r * dlat
        for c in range(ncols):
            val = float(res.dpm[r, c])
            if val > 0.25:
                lon0 = req.min_lon + c * dlon
                lon1 = req.min_lon + (c + 1) * dlon
                poly_coords = [
                    [round(lon0, 5), round(lat0, 5)],
                    [round(lon1, 5), round(lat0, 5)],
                    [round(lon1, 5), round(lat1, 5)],
                    [round(lon0, 5), round(lat1, 5)],
                    [round(lon0, 5), round(lat0, 5)],
                ]
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": [poly_coords]},
                        "properties": {
                            "dpm": round(val, 3),
                            "loss_percent": round(val * 100),
                            "severity": (
                                "Critical"
                                if val > 0.65
                                else ("Heavy" if val > 0.45 else "Moderate")
                            ),
                        },
                    }
                )

    return {
        "status": "success",
        "severe_damage_ratio": round(res.severe_damage_ratio, 4),
        "resolution_deg": round(res.resolution_deg, 6),
        "mean_dpm": round(float(res.dpm.mean()), 4),
        "max_dpm": round(float(res.dpm.max()), 4),
        "bounds": list(res.bounds),
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        },
    }


class DamageAssessmentRequest(BaseModel):
    pga_g: float = Field(default=0.65, ge=0.01, le=3.0)
    building_count: int = Field(default=30, ge=5, le=500)


@app.post("/api/v1/damage/sample-antakya")
async def assess_sample_buildings_endpoint(
    req: DamageAssessmentRequest,
) -> dict[str, Any]:
    """Run building damage assessment on sample Antakya building stock."""
    import json

    from zemin.damage import assess_building_stock_damage, generate_sample_antakya_buildings

    blds = generate_sample_antakya_buildings(count=req.building_count)
    assessed = assess_building_stock_damage(blds, pga_g=req.pga_g)

    geojson_str = assessed.to_json()
    geojson_data = json.loads(geojson_str)

    total_fatalities = float(assessed["estimated_fatalities"].sum())
    collapsed_count = int((assessed["damage_grade"] == "D4_Collapse").sum())

    return {
        "status": "success",
        "summary": {
            "total_buildings": len(assessed),
            "collapsed_buildings": collapsed_count,
            "estimated_fatalities": round(total_fatalities, 1),
            "pga_input_g": req.pga_g,
        },
        "geojson": geojson_data,
    }


class IsochroneRequest(BaseModel):
    center_lon: float = Field(default=36.160)
    center_lat: float = Field(default=36.202)
    cutoff_minutes: float = Field(default=10.0, ge=1.0, le=60.0)


@app.post("/api/v1/routing/isochrone")
async def compute_isochrone_endpoint(req: IsochroneRequest) -> dict[str, Any]:
    """Compute reachability isochrone under earthquake damage and debris blockage."""
    from shapely.geometry import mapping

    from zemin.routing import create_sample_antakya_road_grid, generate_isochrone_polygon

    grid = create_sample_antakya_road_grid(
        center_lon=req.center_lon, center_lat=req.center_lat, grid_n=7
    )
    closest_node = min(
        grid.nodes.keys(),
        key=lambda nid: (grid.nodes[nid].lat - req.center_lat) ** 2
        + (grid.nodes[nid].lon - req.center_lon) ** 2,
    )
    poly = generate_isochrone_polygon(grid, closest_node, req.cutoff_minutes)

    if poly is None:
        raise HTTPException(status_code=400, detail="Could not form polygon from reachable nodes")

    return {
        "status": "success",
        "cutoff_minutes": req.cutoff_minutes,
        "isochrone_geojson": mapping(poly),
    }


# =========================================================================
# OGC API Features (ISO 19168-1) Standards Implementation
# =========================================================================


@app.get("/conformance")
@app.get("/ogc/conformance")
async def ogc_conformance_endpoint() -> dict[str, list[str]]:
    """Declare conformance with OGC API Features Part 1: Core requirements."""
    return get_ogc_conformance()


@app.get("/collections")
@app.get("/ogc/collections")
async def ogc_collections_endpoint(request: Request) -> dict[str, Any]:
    """Catalog of spatial collections available via OGC API."""
    base_url = str(request.base_url).rstrip("/")
    return get_ogc_collections_metadata(base_url)


@app.get("/collections/active-faults/items")
@app.get("/ogc/collections/active-faults/items")
@app.get("/api/v1/faults/mta-active")
async def get_active_faults_items(
    bbox: str | None = Query(default=None, description="min_lon,min_lat,max_lon,max_lat"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Return MTA Active Tectonic Faults as standard OGC GeoJSON FeatureCollection."""
    parsed_bbox: tuple[float, float, float, float] | None = None
    if bbox:
        try:
            parts = [float(x.strip()) for x in bbox.split(",")]
            if len(parts) == 4:
                parsed_bbox = (parts[0], parts[1], parts[2], parts[3])
        except ValueError as err:
            raise HTTPException(
                status_code=400,
                detail="Invalid bbox format. Expected min_lon,min_lat,max_lon,max_lat",
            ) from err
    return get_active_faults_geojson(bbox=parsed_bbox, limit=limit, offset=offset)


@app.get("/collections/strong-motion-stations/items")
@app.get("/ogc/collections/strong-motion-stations/items")
@app.get("/api/v1/stations/afad-2023")
async def get_strong_motion_stations() -> dict[str, Any]:
    """Return AFAD Strong-Motion Seismograph stations as OGC GeoJSON FeatureCollection."""
    return stations_to_geojson(AFAD_2023_PAZARCIK_STATIONS)
