"""Tests for InSAR Coherence Change Detection and Displacement."""

import numpy as np
import pytest
from zemin.insar import (
    compute_coherence_loss,
    simulate_insar_damage_proxy,
    unwrapped_phase_to_displacement,
)


def test_coherence_loss_calculation() -> None:
    # 3x3 synthetic coherence
    co_pre = np.array(
        [
            [0.8, 0.85, 0.9],
            [0.75, 0.8, 0.78],
            [0.2, 0.8, 0.82],  # (2, 0) is below min_pre_coherence 0.35 (e.g. water)
        ],
        dtype=np.float32,
    )

    co_co = np.array(
        [
            [0.75, 0.30, 0.20],  # (0, 1) and (0, 2) suffered severe loss
            [0.70, 0.75, 0.72],
            [0.1, 0.78, 0.80],
        ],
        dtype=np.float32,
    )

    dpm, severe_ratio = compute_coherence_loss(co_pre, co_co, threshold=0.30)

    # (0, 1): pre=0.85, co=0.30 -> loss = (0.85-0.30)/0.85 = 0.55 / 0.85 = ~0.647
    assert dpm[0, 1] > 0.60
    # (2, 0) was low coherence pre-event, so dpm should be 0.0
    assert dpm[2, 0] == 0.0
    assert severe_ratio > 0.0


def test_unwrapped_phase_displacement() -> None:
    # 2*pi phase shift should correspond to lambda/2 (~2.77 cm for Sentinel-1)
    phase = np.array([2.0 * np.pi], dtype=np.float32)
    disp = unwrapped_phase_to_displacement(phase)
    # disp = -lambda / (4*pi) * 2*pi = -lambda / 2
    assert pytest.approx(disp[0], rel=1e-3) == -0.055465 / 2.0


def test_simulate_insar_damage_proxy() -> None:
    bounds = (36.0, 36.0, 36.5, 36.5)
    epicenter = (36.2, 36.2)
    result = simulate_insar_damage_proxy(bounds, epicenter, magnitude=7.8, nrows=30, ncols=30)

    assert result.dpm.shape == (30, 30)
    assert 0.0 <= result.severe_damage_ratio <= 1.0
    assert result.resolution_deg > 0.0
