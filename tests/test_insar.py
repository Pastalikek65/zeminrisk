"""Tests for InSAR Coherence Change Detection and Displacement."""

import numpy as np
import pytest
from zemin.insar import (
    compute_coherence_loss,
    simulate_insar_damage_proxy,
    unwrapped_phase_to_displacement,
    write_cog,
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


def test_coherence_loss_all_nan_or_zero() -> None:
    # All NaN coherence arrays
    arr_nan = np.full((10, 10), np.nan, dtype=np.float32)
    dpm_nan, ratio_nan = compute_coherence_loss(arr_nan, arr_nan)
    assert not np.isnan(dpm_nan).any()
    assert np.all(dpm_nan == 0.0)
    assert ratio_nan == 0.0

    # All Zero coherence arrays
    arr_zero = np.zeros((10, 10), dtype=np.float32)
    dpm_zero, ratio_zero = compute_coherence_loss(arr_zero, arr_zero)
    assert not np.isnan(dpm_zero).any()
    assert np.all(dpm_zero == 0.0)
    assert ratio_zero == 0.0

    # All Zero with min_pre_coherence = 0.0
    dpm_zero_min0, ratio_zero_min0 = compute_coherence_loss(
        arr_zero, arr_zero, min_pre_coherence=0.0
    )
    assert not np.isnan(dpm_zero_min0).any()
    assert np.all(dpm_zero_min0 == 0.0)
    assert ratio_zero_min0 == 0.0

    # Mixed NaNs (pre valid, co-seismic is NaN)
    pre_valid = np.full((10, 10), 0.8, dtype=np.float32)
    dpm_mixed, ratio_mixed = compute_coherence_loss(pre_valid, arr_nan)
    assert not np.isnan(dpm_mixed).any()
    assert np.all(dpm_mixed == 0.0)
    assert ratio_mixed == 0.0


def test_write_cog_with_tiling_and_overviews(tmp_path: pytest.TempPathFactory) -> None:
    import rasterio

    data = np.full((64, 64), 0.5, dtype=np.float32)
    bounds = (36.0, 36.0, 36.5, 36.5)
    cog_path = str(tmp_path / "test_output.tif")  # type: ignore[operator]

    write_cog(cog_path, data, bounds)

    with rasterio.open(cog_path) as src:
        assert src.profile.get("tiled") is True
        assert src.count == 1
        assert src.shape == (64, 64)
        # Should have built overviews for factors [2, 4]
        assert len(src.overviews(1)) >= 2
        # Verify read data
        read_data = src.read(1)
        assert np.allclose(read_data, 0.5)


