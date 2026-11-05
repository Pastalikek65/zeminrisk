"""Tests for Soil Liquefaction Susceptibility and Iwasaki LPI Engine."""

from zemin.liquefaction import (
    ANTAKYA_REPRESENTATIVE_BOREHOLES,
    compute_cyclic_resistance_ratio_vs,
    compute_cyclic_stress_ratio,
    evaluate_borehole_liquefaction,
    generate_asi_basin_liquefaction_geojson,
)


def test_cyclic_stress_ratio() -> None:
    # High PGA (1.0g) should yield high CSR
    csr_high = compute_cyclic_stress_ratio(
        pga_g=1.0, magnitude=7.8, depth_m=5.0, groundwater_depth_m=1.0
    )
    # Low PGA (0.1g) should yield low CSR
    csr_low = compute_cyclic_stress_ratio(
        pga_g=0.1, magnitude=7.8, depth_m=5.0, groundwater_depth_m=1.0
    )

    assert csr_high > csr_low
    assert 0.05 <= csr_high <= 3.0


def test_cyclic_resistance_ratio_vs() -> None:
    # Stiff soil (Vs = 220 m/s) vs Loose soil (Vs = 120 m/s)
    crr_dense = compute_cyclic_resistance_ratio_vs(
        vs_m_s=220.0, depth_m=5.0, groundwater_depth_m=1.5
    )
    crr_loose = compute_cyclic_resistance_ratio_vs(
        vs_m_s=120.0, depth_m=5.0, groundwater_depth_m=1.5
    )

    assert crr_dense > crr_loose


def test_borehole_liquefaction_alluvium_vs_bedrock() -> None:
    # Asi river soft borehole (BH_ASI_01)
    bh_alluvium = ANTAKYA_REPRESENTATIVE_BOREHOLES[0]
    res_alluvium = evaluate_borehole_liquefaction(bh_alluvium, pga_g=1.05, magnitude=7.8)

    # Alluvial basin with high PGA must have high or very high liquefaction susceptibility
    assert res_alluvium.lpi > 5.0
    assert res_alluvium.hazard_class in ["High", "Very High"]
    assert res_alluvium.min_factor_of_safety < 1.0

    # Mountain bedrock borehole (BH_HABIB_01)
    bh_bedrock = ANTAKYA_REPRESENTATIVE_BOREHOLES[3]
    res_bedrock = evaluate_borehole_liquefaction(bh_bedrock, pga_g=1.05, magnitude=7.8)

    # Bedrock must not liquefy (LPI = 0)
    assert res_bedrock.lpi == 0.0
    assert res_bedrock.hazard_class == "Very Low"
    assert res_bedrock.min_factor_of_safety >= 1.0


def test_generate_asi_basin_liquefaction_geojson() -> None:
    gj = generate_asi_basin_liquefaction_geojson(pga_g=1.0, magnitude=7.8)
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) > 0

    first = gj["features"][0]
    assert first["geometry"]["type"] == "Polygon"
    assert "lpi" in first["properties"]
    assert "hazard_class" in first["properties"]
    assert "lateral_spread_m" in first["properties"]
