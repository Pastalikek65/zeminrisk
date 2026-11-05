"""OGC API and FastAPI service for ZeminRisk."""

import math
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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
        # Bounding box ~2 degrees around epicenter
        delta = 2.0
        min_lat = req.epicenter_lat - delta
        max_lat = req.epicenter_lat + delta
        min_lon = req.epicenter_lon - delta
        max_lon = req.epicenter_lon + delta

        # Grid generation
        nrows = req.grid_resolution
        ncols = req.grid_resolution
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

                # ASB14 Simplified Ground Motion Form
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

                # Worden et al. MMI
                log_pga = math.log10(pga_g * 100.0)
                mmi_pga = 1.78 + 1.55 * log_pga if log_pga <= 1.0 else 3.10 + 2.87 * log_pga
                log_pgv = math.log10(max(0.01, pgv_cms))
                mmi_pgv = 3.78 + 1.80 * log_pgv if log_pgv <= 0.5 else 4.37 + 2.72 * log_pgv
                mmi = mmi_pga if mmi_pga < 5.0 else 0.4 * mmi_pga + 0.6 * mmi_pgv
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
            },
            geojson={
                "type": "FeatureCollection",
                "features": features,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
