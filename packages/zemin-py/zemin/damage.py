"""Building Vulnerability, Fragility Curves, and Damage Assessment Engine.

Implements EMS-98 / GEM fragility curves, casualty estimation,
and multi-modal ground motion + InSAR fusion for building stock.
"""

import math
from dataclasses import dataclass
from enum import StrEnum

import geopandas as gpd
import numpy as np
import numpy.typing as npt
from shapely.geometry import Polygon


class BuildingTypology(StrEnum):
    RC_PRE_2000 = "RC_PRE_2000"  # Pre-1999 seismic code RC frame (high vulnerability)
    RC_POST_2000 = "RC_POST_2000"  # Modern compliant RC frame
    UNREINFORCED_MASONRY = "URM"  # Unreinforced brick/stone masonry
    STEEL_FRAME = "STEEL"  # Structural steel frame


@dataclass(frozen=True)
class FragilityParameters:
    """Lognormal median capacity theta (in g) and log-standard deviation beta."""

    theta_slight: float
    theta_moderate: float
    theta_extensive: float
    theta_collapse: float
    beta: float = 0.60


# Regional calibration based on Turkish Building Earthquake Code (TBDY 2018)
# and European Seismic Risk Model (ESRM20)
TYPOLOGY_FRAGILITY: dict[BuildingTypology, FragilityParameters] = {
    BuildingTypology.RC_PRE_2000: FragilityParameters(
        theta_slight=0.12,
        theta_moderate=0.24,
        theta_extensive=0.42,
        theta_collapse=0.68,
        beta=0.62,
    ),
    BuildingTypology.RC_POST_2000: FragilityParameters(
        theta_slight=0.22,
        theta_moderate=0.45,
        theta_extensive=0.78,
        theta_collapse=1.15,
        beta=0.58,
    ),
    BuildingTypology.UNREINFORCED_MASONRY: FragilityParameters(
        theta_slight=0.08,
        theta_moderate=0.16,
        theta_extensive=0.30,
        theta_collapse=0.48,
        beta=0.65,
    ),
    BuildingTypology.STEEL_FRAME: FragilityParameters(
        theta_slight=0.30,
        theta_moderate=0.60,
        theta_extensive=1.05,
        theta_collapse=1.55,
        beta=0.55,
    ),
}


def lognormal_cdf(
    im: npt.NDArray[np.float64],
    theta: float,
    beta: float,
) -> npt.NDArray[np.float64]:
    """Vectorized lognormal cumulative distribution function: Phi((ln(IM) - ln(theta)) / beta)."""
    im_arr = np.asarray(im, dtype=np.float64)
    result = np.zeros_like(im_arr, dtype=np.float64)
    positive_mask = (im_arr > 0.0) & np.isfinite(im_arr)
    if not np.any(positive_mask):
        return result

    im_pos = im_arr[positive_mask]
    im_safe = np.maximum(im_pos, 1e-6)
    x = (np.log(im_safe) - math.log(theta)) / beta
    # Approximation of erf for vectorization: 0.5 * (1 + erf(x / sqrt(2)))
    # scipy.special.erf equivalent using math or vectorized expansion
    erf_vec = np.vectorize(math.erf)
    result[positive_mask] = np.clip(
        0.5 * (1.0 + erf_vec(x / math.sqrt(2.0))), 0.0, 1.0
    ).astype(np.float64)
    return result


def evaluate_fragility_state_probabilities(
    pga_array: npt.NDArray[np.float64],
    typology: BuildingTypology,
) -> dict[str, npt.NDArray[np.float64]]:
    """Compute discrete probabilities for damage states DS0 (None) through DS4 (Collapse)."""
    params = TYPOLOGY_FRAGILITY[typology]

    p_ge_ds1 = lognormal_cdf(pga_array, params.theta_slight, params.beta)
    p_ge_ds2 = lognormal_cdf(pga_array, params.theta_moderate, params.beta)
    p_ge_ds3 = lognormal_cdf(pga_array, params.theta_extensive, params.beta)
    p_ge_ds4 = lognormal_cdf(pga_array, params.theta_collapse, params.beta)

    # Discrete probabilities
    p_ds0 = np.clip(1.0 - p_ge_ds1, 0.0, 1.0)
    p_ds1 = np.clip(p_ge_ds1 - p_ge_ds2, 0.0, 1.0)
    p_ds2 = np.clip(p_ge_ds2 - p_ge_ds3, 0.0, 1.0)
    p_ds3 = np.clip(p_ge_ds3 - p_ge_ds4, 0.0, 1.0)
    p_ds4 = p_ge_ds4

    expected_ds = p_ds1 * 1.0 + p_ds2 * 2.0 + p_ds3 * 3.0 + p_ds4 * 4.0

    return {
        "p_none": p_ds0,
        "p_slight": p_ds1,
        "p_moderate": p_ds2,
        "p_extensive": p_ds3,
        "p_collapse": p_ds4,
        "expected_damage_state": expected_ds,
    }


def assess_building_stock_damage(
    buildings: gpd.GeoDataFrame,
    pga_g: float | npt.NDArray[np.float64],
    dpm_values: npt.NDArray[np.float64] | None = None,
) -> gpd.GeoDataFrame:
    """Perform building damage assessment across a GeoDataFrame of building footprints.

    Computes damage states, casualty potentials, and fused InSAR damage probability.
    """
    gdf = buildings.copy()
    n = len(gdf)

    if isinstance(pga_g, (int, float)):
        pga_arr = np.full(n, float(pga_g), dtype=np.float64)
    else:
        pga_arr = np.asarray(pga_g, dtype=np.float64)

    # Default typology if column absent
    if "typology" not in gdf.columns:
        gdf["typology"] = BuildingTypology.RC_PRE_2000.value

    # Default occupancy
    if "occupancy" not in gdf.columns:
        gdf["occupancy"] = 10

    # Calculate probabilities per typology subset
    p_collapse = np.zeros(n, dtype=np.float64)
    p_extensive = np.zeros(n, dtype=np.float64)
    expected_ds = np.zeros(n, dtype=np.float64)

    if n > 0:
        for typo in BuildingTypology:
            mask = gdf["typology"] == typo.value
            if np.any(mask):
                sub_pga = pga_arr[mask]
                probs = evaluate_fragility_state_probabilities(sub_pga, typo)
                p_collapse[mask] = probs["p_collapse"]
                p_extensive[mask] = probs["p_extensive"]
                expected_ds[mask] = probs["expected_damage_state"]

    gdf["pga_g"] = np.round(pga_arr, 4)
    gdf["p_collapse"] = np.round(p_collapse, 4)
    gdf["p_extensive"] = np.round(p_extensive, 4)
    gdf["expected_ds"] = np.round(expected_ds, 2)

    # Multi-modal fusion with InSAR DPM if provided
    # Posterior P(Severe | PGA, DPM) = alpha * P_pga + (1 - alpha) * DPM
    if dpm_values is not None and len(dpm_values) == n and n > 0:
        gdf["dpm_coherence_loss"] = np.round(dpm_values, 3)
        fused_prob = 0.55 * p_collapse + 0.45 * dpm_values
        gdf["fused_damage_prob"] = np.round(np.clip(fused_prob, 0.0, 1.0), 4)
    else:
        gdf["fused_damage_prob"] = gdf["p_collapse"]

    # Coburn & Spence (1992) casualty model:
    # Fatalities = Occupants * P(Collapse) * Indoor_trapped_rate (0.5) * Lethality_rate (0.2)
    lethality_rate = 0.10
    occupants = (
        gdf["occupancy"].to_numpy(dtype=np.float64)
        if n > 0
        else np.zeros(0, dtype=np.float64)
    )
    gdf["estimated_fatalities"] = np.round(occupants * p_collapse * lethality_rate, 1)

    # Discrete classification
    if n == 0:
        gdf["damage_grade"] = np.array([], dtype=object)
    else:
        gdf["damage_grade"] = np.where(
            gdf["p_collapse"] >= 0.50,
            "D4_Collapse",
            np.where(
                gdf["p_extensive"] >= 0.40,
                "D3_Extensive",
                np.where(
                    gdf["expected_ds"] >= 1.5,
                    "D2_Moderate",
                    np.where(
                        gdf["expected_ds"] >= 0.5,
                        "D1_Slight",
                        "D0_None",
                    ),
                ),
            ),
        )

    return gdf


def generate_sample_antakya_buildings(
    center_lon: float = 36.160,
    center_lat: float = 36.202,
    count: int = 50,
    radius_deg: float = 0.02,
    seed: int = 42,
) -> gpd.GeoDataFrame:
    """Generate a sample synthetic building stock GeoDataFrame for Antakya center."""
    if count <= 0:
        return gpd.GeoDataFrame(
            {
                "building_id": [],
                "typology": [],
                "occupancy": [],
                "geometry": [],
            },
            crs="EPSG:4326",
        )
    rng = np.random.default_rng(seed)
    polygons = []
    typologies = []
    occupancies = []

    for _ in range(count):
        bx = center_lon + rng.uniform(-radius_deg, radius_deg)
        by = center_lat + rng.uniform(-radius_deg, radius_deg)
        size = rng.uniform(0.0001, 0.0004)

        poly = Polygon(
            [
                (bx - size, by - size),
                (bx + size, by - size),
                (bx + size, by + size),
                (bx - size, by + size),
                (bx - size, by - size),
            ]
        )
        polygons.append(poly)

        # Pre-2000 RC is predominant in historical districts
        t_choice = rng.choice(
            [
                BuildingTypology.RC_PRE_2000.value,
                BuildingTypology.RC_POST_2000.value,
                BuildingTypology.UNREINFORCED_MASONRY.value,
            ],
            p=[0.60, 0.25, 0.15],
        )
        typologies.append(t_choice)
        occupancies.append(int(rng.integers(4, 30)))

    return gpd.GeoDataFrame(
        {
            "building_id": [f"BLD_{i + 1:04d}" for i in range(count)],
            "typology": typologies,
            "occupancy": occupancies,
            "geometry": polygons,
        },
        crs="EPSG:4326",
    )
