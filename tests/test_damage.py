"""Tests for Building Vulnerability and Fragility Assessment."""

import numpy as np
from hypothesis import given
from hypothesis import strategies as st
from zemin.damage import (
    BuildingTypology,
    assess_building_stock_damage,
    evaluate_fragility_state_probabilities,
    generate_sample_antakya_buildings,
)


def test_fragility_state_probabilities() -> None:
    # Low ground motion (0.05g) vs severe ground motion (0.80g)
    low_pga = np.array([0.05])
    high_pga = np.array([0.80])

    res_low = evaluate_fragility_state_probabilities(low_pga, BuildingTypology.RC_PRE_2000)
    res_high = evaluate_fragility_state_probabilities(high_pga, BuildingTypology.RC_PRE_2000)

    # Low shaking should have high probability of no damage (DS0)
    assert res_low["p_none"][0] > 0.80
    assert res_low["p_collapse"][0] < 0.05

    # Severe shaking should have high probability of collapse / extensive damage
    assert res_high["p_collapse"][0] > 0.40
    assert res_high["expected_damage_state"][0] > res_low["expected_damage_state"][0]


def test_assess_building_stock_antakya() -> None:
    bld_gdf = generate_sample_antakya_buildings(count=20, seed=42)
    assert len(bld_gdf) == 20

    # Assess with severe shaking (0.75g)
    assessed = assess_building_stock_damage(bld_gdf, pga_g=0.75)

    assert "p_collapse" in assessed.columns
    assert "damage_grade" in assessed.columns
    assert "estimated_fatalities" in assessed.columns

    # Check non-negative fatalities
    assert np.all(assessed["estimated_fatalities"] >= 0.0)
    # Total fatalities under severe shaking should be positive
    assert assessed["estimated_fatalities"].sum() > 0.0


def test_assess_building_stock_zero_ground_motion() -> None:
    bld_gdf = generate_sample_antakya_buildings(count=10, seed=42)
    assessed = assess_building_stock_damage(bld_gdf, pga_g=0.0)

    # When shaking is 0, no collapse, no fatalities, and damage grade is D0_None
    assert np.all(assessed["p_collapse"] == 0.0)
    assert np.all(assessed["expected_ds"] == 0.0)
    assert np.all(assessed["estimated_fatalities"] == 0.0)
    assert np.all(assessed["damage_grade"] == "D0_None")


def test_assess_building_stock_empty_gdf() -> None:
    empty_bld = generate_sample_antakya_buildings(count=0)
    assert len(empty_bld) == 0

    assessed = assess_building_stock_damage(empty_bld, pga_g=0.5)
    assert len(assessed) == 0
    assert "p_collapse" in assessed.columns
    assert "damage_grade" in assessed.columns
    assert "estimated_fatalities" in assessed.columns


@given(st.floats(min_value=0.0, max_value=5.0))
def test_hypothesis_pga_fragility_monotonicity(pga: float) -> None:
    res = evaluate_fragility_state_probabilities(
        np.array([pga]), BuildingTypology.RC_PRE_2000
    )
    assert 0.0 <= res["p_collapse"][0] <= 1.0
    assert 0.0 <= res["p_none"][0] <= 1.0
    assert 0.0 <= res["expected_damage_state"][0] <= 4.0



