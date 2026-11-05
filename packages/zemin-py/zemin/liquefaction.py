"""Soil Liquefaction Susceptibility & Lateral Spreading Engine.

Implements Seed & Idriss / Youd et al. (2001) Cyclic Stress Ratio (CSR),
Andrus & Stokoe (2000) shear-wave velocity CRR formulation,
and Iwasaki et al. (1982) Liquefaction Potential Index (LPI).
Calibrated for the Holocene alluvial silts and sands of the Asi River Basin (Antakya).
"""

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SoilBoreholeProfile:
    """Geotechnical borehole soil stratigraphy."""

    borehole_id: str
    lon: float
    lat: float
    groundwater_depth_m: float  # Depth to groundwater table
    layer_depths_m: list[float]  # Depth to bottom of each layer
    vs_profile: list[float]  # Shear wave velocity Vs (m/s) per layer
    total_unit_weight_kn_m3: float = 18.5  # Typical saturated soil unit weight
    soil_types: list[str] | None = None  # e.g. ["Silt", "Fine Sand", "Clay"]


@dataclass
class LiquefactionEvaluationResult:
    """Computed liquefaction safety factors and LPI."""

    lpi: float
    hazard_class: str  # "Very Low", "Low", "High", "Very High"
    min_factor_of_safety: float
    liquefied_depth_range_m: tuple[float, float]
    estimated_lateral_spread_m: float  # Youd et al. empirical lateral displacement


def compute_cyclic_stress_ratio(
    pga_g: float,
    magnitude: float,
    depth_m: float,
    groundwater_depth_m: float,
    unit_weight_kn_m3: float = 18.5,
    water_unit_weight_kn_m3: float = 9.81,
) -> float:
    """Compute Cyclic Stress Ratio (CSR) via Youd et al. (2001).

    CSR = 0.65 * (PGA/g) * (sigma_v / sigma_v') * r_d * (1 / MSF)
    """
    pga = max(0.01, pga_g)
    mw = max(4.5, min(9.5, magnitude))
    z = max(0.1, min(20.0, depth_m))

    # Stress reduction coefficient r_d (Youd et al. 2001)
    r_d = 1.0 - 0.00765 * z if z <= 9.15 else 1.174 - 0.0267 * z
    r_d = max(0.4, min(1.0, r_d))

    # Magnitude Scaling Factor (MSF = (Mw / 7.5)^-2.56)
    msf = (mw / 7.5) ** (-2.56)

    # Total and effective vertical overburden stress (kPa)
    sigma_v = unit_weight_kn_m3 * z
    if z > groundwater_depth_m:
        pore_pressure = water_unit_weight_kn_m3 * (z - groundwater_depth_m)
        sigma_v_eff = max(5.0, sigma_v - pore_pressure)
    else:
        sigma_v_eff = max(5.0, sigma_v)

    stress_ratio = sigma_v / sigma_v_eff
    csr = 0.65 * pga * stress_ratio * r_d * (1.0 / msf)
    return float(np.clip(csr, 0.05, 3.0))


def compute_cyclic_resistance_ratio_vs(
    vs_m_s: float,
    depth_m: float,
    groundwater_depth_m: float,
    fines_content_percent: float = 15.0,
    unit_weight_kn_m3: float = 18.5,
) -> float:
    """Compute Cyclic Resistance Ratio (CRR) from shear-wave velocity (Andrus & Stokoe 2000).

    CRR_7.5 = 0.022 * (Vs1 / 100)^2 + 2.8 * (1 / (Vs1_star - Vs1) - 1 / Vs1_star)
    """
    z = max(0.1, min(20.0, depth_m))
    sigma_v = unit_weight_kn_m3 * z
    if z > groundwater_depth_m:
        pore_pressure = 9.81 * (z - groundwater_depth_m)
        sigma_v_eff = max(5.0, sigma_v - pore_pressure)
    else:
        sigma_v_eff = max(5.0, sigma_v)

    # Overburden stress correction factor C_v = (P_a / sigma_v')^0.25
    p_a = 100.0  # atmospheric pressure in kPa
    c_v = min(1.4, (p_a / sigma_v_eff) ** 0.25)
    vs1 = vs_m_s * c_v

    # Limiting upper-bound velocity Vs1* based on fines content
    if fines_content_percent <= 5.0:
        vs1_star = 215.0
    elif fines_content_percent >= 35.0:
        vs1_star = 200.0
    else:
        vs1_star = 215.0 - 0.5 * (fines_content_percent - 5.0)

    if vs1 >= vs1_star:
        return 2.5  # Non-liquefiable dense layer

    term1 = 0.022 * ((vs1 / 100.0) ** 2)
    term2 = 2.8 * (1.0 / (vs1_star - vs1) - 1.0 / vs1_star)
    crr = term1 + term2
    return float(np.clip(crr, 0.05, 2.5))


def evaluate_borehole_liquefaction(
    borehole: SoilBoreholeProfile,
    pga_g: float,
    magnitude: float,
) -> LiquefactionEvaluationResult:
    """Evaluate Liquefaction Potential Index (LPI) through soil stratigraphy (Iwasaki et al. 1982).

    LPI = Integral_0^20m F * w(z) dz
    where F = 1 - FS if FS <= 1.0, else 0; w(z) = 10 - 0.5z
    """
    depth_steps = np.linspace(0.5, 20.0, 40)  # 0.5m intervals up to 20m depth
    dz = float(depth_steps[1] - depth_steps[0])

    fs_list: list[float] = []
    lpi_accum = 0.0
    liquefied_depths: list[float] = []

    for z in depth_steps:
        # Find which layer z belongs to
        layer_idx = 0
        for idx, bound_depth in enumerate(borehole.layer_depths_m):
            if z <= bound_depth:
                layer_idx = idx
                break
            layer_idx = idx

        vs_layer = borehole.vs_profile[min(layer_idx, len(borehole.vs_profile) - 1)]

        # Above groundwater, soil is unsaturated -> not liquefiable
        if z < borehole.groundwater_depth_m:
            fs = 2.5
        else:
            csr = compute_cyclic_stress_ratio(
                pga_g, magnitude, z, borehole.groundwater_depth_m, borehole.total_unit_weight_kn_m3
            )
            crr = compute_cyclic_resistance_ratio_vs(
                vs_layer,
                z,
                borehole.groundwater_depth_m,
                unit_weight_kn_m3=borehole.total_unit_weight_kn_m3,
            )
            fs = crr / max(1e-4, csr)

        fs_list.append(fs)

        if fs < 1.0:
            liquefied_depths.append(z)
            f_val = 1.0 - fs
            w_z = 10.0 - 0.5 * z
            lpi_accum += f_val * w_z * dz

    min_fs = float(np.min(fs_list)) if fs_list else 2.5
    lpi = float(np.clip(lpi_accum, 0.0, 100.0))

    if lpi == 0.0:
        hazard_class = "Very Low"
    elif lpi <= 5.0:
        hazard_class = "Low"
    elif lpi <= 15.0:
        hazard_class = "High"
    else:
        hazard_class = "Very High"

    depth_range = (
        (float(np.min(liquefied_depths)), float(np.max(liquefied_depths)))
        if liquefied_depths
        else (0.0, 0.0)
    )

    # Lateral spreading displacement estimation (Youd et al. empirical proxy)
    # L = 0.2 * LPI^0.8 for gently sloping / free-face alluvial banks
    lateral_spread_m = round(float(0.18 * (lpi**0.85)), 2) if lpi > 5.0 else 0.0

    return LiquefactionEvaluationResult(
        lpi=round(lpi, 2),
        hazard_class=hazard_class,
        min_factor_of_safety=round(min_fs, 3),
        liquefied_depth_range_m=depth_range,
        estimated_lateral_spread_m=lateral_spread_m,
    )


# Representative geotechnical boreholes across Antakya & Asi River Basin
ANTAKYA_REPRESENTATIVE_BOREHOLES: list[SoilBoreholeProfile] = [
    SoilBoreholeProfile(
        borehole_id="BH_ASI_01",
        lon=36.158,
        lat=36.205,
        groundwater_depth_m=1.2,  # Very shallow alluvial water table
        layer_depths_m=[3.0, 8.0, 14.0, 25.0],
        vs_profile=[130.0, 160.0, 210.0, 340.0],  # Soft Holocene silt & fine sand
        soil_types=["Alluvial Silt", "Loose Sand", "Clayey Silt", "Dense Gravel"],
    ),
    SoilBoreholeProfile(
        borehole_id="BH_ASI_02",
        lon=36.162,
        lat=36.198,
        groundwater_depth_m=1.8,
        layer_depths_m=[4.0, 10.0, 16.0, 30.0],
        vs_profile=[145.0, 175.0, 240.0, 380.0],
        soil_types=["Silty Sand", "Fine Sand", "Stiff Clay", "Gravel"],
    ),
    SoilBoreholeProfile(
        borehole_id="BH_AMIK_01",
        lon=36.250,
        lat=36.310,
        groundwater_depth_m=0.8,  # Amik lake basin dried bed - saturated
        layer_depths_m=[5.0, 12.0, 20.0, 35.0],
        vs_profile=[110.0, 140.0, 190.0, 320.0],
        soil_types=["Soft Lacustrine Clay", "Silty Sand", "Peat", "Marl"],
    ),
    SoilBoreholeProfile(
        borehole_id="BH_HABIB_01",
        lon=36.175,
        lat=36.210,
        groundwater_depth_m=8.5,  # Habib-i Neccar mountain slope - bedrock
        layer_depths_m=[2.0, 6.0, 30.0],
        vs_profile=[380.0, 620.0, 1100.0],  # Limestone bedrock
        soil_types=["Colluvium", "Weathered Limestone", "Intact Limestone"],
    ),
]


def generate_asi_basin_liquefaction_geojson(
    pga_g: float = 1.05, magnitude: float = 7.8
) -> dict[str, Any]:
    """Generate 2D spatial liquefaction susceptibility polygons for the Asi River alluvial zone."""
    # Asi river basin bounding corridor [lon_min, lat_min, lon_max, lat_max]
    min_lon, max_lon = 36.140, 36.180
    min_lat, max_lat = 36.185, 36.230
    cols, rows = 12, 14
    dlon = (max_lon - min_lon) / cols
    dlat = (max_lat - min_lat) / rows

    features = []

    for r in range(rows):
        lat0 = max_lat - (r + 1) * dlat
        lat1 = max_lat - r * dlat
        c_lat = (lat0 + lat1) / 2.0

        for c in range(cols):
            lon0 = min_lon + c * dlon
            lon1 = min_lon + (c + 1) * dlon
            c_lon = (lon0 + lon1) / 2.0

            # Distance to Asi River centerline (approx lon 36.160)
            dist_to_river_km = abs(c_lon - 36.160) * 111.0 * np.cos(np.radians(36.20))
            is_alluvium = dist_to_river_km < 1.4

            if is_alluvium:
                # High groundwater table near river (1.0m to 2.5m)
                gw_depth = max(0.8, 1.0 + dist_to_river_km * 0.9)
                vs_avg = 135.0 + dist_to_river_km * 45.0

                borehole = SoilBoreholeProfile(
                    borehole_id=f"SYN_BH_{r}_{c}",
                    lon=c_lon,
                    lat=c_lat,
                    groundwater_depth_m=gw_depth,
                    layer_depths_m=[3.0, 8.0, 20.0],
                    vs_profile=[vs_avg, vs_avg * 1.25, vs_avg * 1.6],
                )
                res = evaluate_borehole_liquefaction(borehole, pga_g=pga_g, magnitude=magnitude)

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
                            "lpi": res.lpi,
                            "hazard_class": res.hazard_class,
                            "min_fs": res.min_factor_of_safety,
                            "lateral_spread_m": res.estimated_lateral_spread_m,
                            "gw_depth_m": round(gw_depth, 1),
                            "zone": "Asi River Holocene Floodplain",
                        },
                    }
                )

    return {
        "type": "FeatureCollection",
        "features": features,
    }
