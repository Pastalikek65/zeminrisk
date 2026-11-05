"""OGC API Features (ISO 19168-1) Core Implementation.

Provides standard-compliant collections, conformance declarations,
and spatial filtering for Active Faults, Strong-Motion Stations, and Hazard Layers.
"""

from typing import Any

# Active Tectonic Faults of Turkey & Surrounding Region (MTA / AFAD reference)
MTA_ACTIVE_FAULTS: list[dict[str, Any]] = [
    {
        "id": "EAF_AMANOS",
        "name": "East Anatolian Fault - Amanos Segment",
        "mechanism": "strike-slip (left-lateral)",
        "slip_rate_mm_yr": 6.5,
        "last_rupture": "2023-02-06 (Mw 7.8 Pazarcık)",
        "length_km": 115.0,
        "coordinates": [
            [36.14, 36.18],
            [36.25, 36.32],
            [36.32, 36.42],
            [36.45, 36.65],
            [36.58, 36.85],
        ],
    },
    {
        "id": "EAF_PAZARCIK",
        "name": "East Anatolian Fault - Pazarcık / Narlı Segment",
        "mechanism": "strike-slip (left-lateral)",
        "slip_rate_mm_yr": 8.0,
        "last_rupture": "2023-02-06 (Mw 7.8 Pazarcık)",
        "length_km": 140.0,
        "coordinates": [
            [36.58, 36.85],
            [36.80, 37.10],
            [37.04, 37.29],
            [37.30, 37.55],
            [37.52, 37.74],
        ],
    },
    {
        "id": "EAF_ERKENEK",
        "name": "East Anatolian Fault - Erkenek / Çelikhan Segment",
        "mechanism": "strike-slip (left-lateral)",
        "slip_rate_mm_yr": 9.2,
        "last_rupture": "2023-02-06 (Mw 7.8 Pazarcık)",
        "length_km": 95.0,
        "coordinates": [
            [37.52, 37.74],
            [37.82, 37.92],
            [38.05, 38.08],
            [38.25, 38.22],
        ],
    },
    {
        "id": "CARDAK_FAULT",
        "name": "Çardak - Sürgü Fault Zone",
        "mechanism": "strike-slip (left-lateral)",
        "slip_rate_mm_yr": 4.5,
        "last_rupture": "2023-02-06 (Mw 7.6 Elbistan)",
        "length_km": 160.0,
        "coordinates": [
            [36.60, 38.02],
            [36.90, 38.05],
            [37.20, 38.09],
            [37.60, 38.02],
            [37.95, 37.98],
        ],
    },
    {
        "id": "DSF_HATAY",
        "name": "Dead Sea Fault - Hatay / Ghab Valley Segment",
        "mechanism": "strike-slip (left-lateral)",
        "slip_rate_mm_yr": 5.0,
        "last_rupture": "1822 Aleppo / 1872 Amik",
        "length_km": 85.0,
        "coordinates": [
            [36.35, 35.50],
            [36.30, 35.85],
            [36.20, 36.15],
            [36.14, 36.18],
        ],
    },
]


def get_ogc_conformance() -> dict[str, list[str]]:
    """Return OGC API Features conformance classes."""
    return {
        "conformsTo": [
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/req/core",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/req/geojson",
        ]
    }


def get_ogc_collections_metadata(base_url: str) -> dict[str, Any]:
    """Return OGC API collection catalog."""
    return {
        "links": [
            {"rel": "self", "type": "application/json", "href": f"{base_url}/collections"},
        ],
        "collections": [
            {
                "id": "active-faults",
                "title": "MTA Active Tectonic Faults",
                "description": (
                    "Active fault traces and rupture histories in the Eastern "
                    "Mediterranean tectonic regime."
                ),
                "extent": {
                    "spatial": {"bbox": [[35.0, 35.0, 39.0, 39.0]]},
                    "temporal": {"interval": [["1822-01-01T00:00:00Z", None]]},
                },
                "itemType": "feature",
                "links": [
                    {
                        "rel": "items",
                        "type": "application/geo+json",
                        "href": f"{base_url}/collections/active-faults/items",
                    }
                ],
            },
            {
                "id": "strong-motion-stations",
                "title": "AFAD Strong Ground Motion Stations",
                "description": (
                    "Seismometer stations recording Peak Ground Acceleration (PGA) "
                    "and Velocity (PGV)."
                ),
                "extent": {
                    "spatial": {"bbox": [[35.5, 35.8, 38.5, 38.0]]},
                    "temporal": {"interval": [["2023-02-06T00:00:00Z", None]]},
                },
                "itemType": "feature",
                "links": [
                    {
                        "rel": "items",
                        "type": "application/geo+json",
                        "href": f"{base_url}/collections/strong-motion-stations/items",
                    }
                ],
            },
            {
                "id": "liquefaction-zones",
                "title": "Asi Basin Soil Liquefaction Zones",
                "description": (
                    "Soil Liquefaction Potential Index (LPI) and lateral spreading "
                    "hazard across the Asi River Holocene alluvial floodplain."
                ),
                "extent": {
                    "spatial": {"bbox": [[36.14, 36.18, 36.18, 36.23]]},
                    "temporal": {"interval": [["2023-02-06T00:00:00Z", None]]},
                },
                "itemType": "feature",
                "links": [
                    {
                        "rel": "items",
                        "type": "application/geo+json",
                        "href": f"{base_url}/collections/liquefaction-zones/items",
                    }
                ],
            },
        ],
    }


def get_active_faults_geojson(
    bbox: tuple[float, float, float, float] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Return MTA Active Faults as standard GeoJSON FeatureCollection."""
    features = []
    for f in MTA_ACTIVE_FAULTS:
        coords = f["coordinates"]
        # Spatial bbox filter if provided: (min_lon, min_lat, max_lon, max_lat)
        if bbox is not None:
            min_lon, min_lat, max_lon, max_lat = bbox
            has_intersect = any(
                min_lon <= pt[0] <= max_lon and min_lat <= pt[1] <= max_lat for pt in coords
            )
            if not has_intersect:
                continue

        features.append(
            {
                "type": "Feature",
                "id": f["id"],
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
                "properties": {
                    "name": f["name"],
                    "mechanism": f["mechanism"],
                    "slip_rate_mm_yr": f["slip_rate_mm_yr"],
                    "last_rupture": f["last_rupture"],
                    "length_km": f["length_km"],
                },
            }
        )

    paginated = features[offset : offset + limit]
    return {
        "type": "FeatureCollection",
        "features": paginated,
        "numberMatched": len(features),
        "numberReturned": len(paginated),
    }
