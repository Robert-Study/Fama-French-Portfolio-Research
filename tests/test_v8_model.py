"""Unit tests for Portfolio Construction Lab V8 PreparedModel and Model Preparation Contract.

Tests Stage 04 Section 1 specification invariants:
1. Valid model instantiation, field types, and shapes.
2. Spectral PSD projection on small negative eigenvalues in [-1e-12, 0).
3. Fatal ModelSpecificationError on structural negative eigenvalues (< -1e-12).
4. Non-symmetric covariance error.
5. Cash anchor zero volatility enforcement.
6. Immutability (frozen dataclass and read-only buffers).
7. Quote currency normalization to GBP.
8. Dist policy and parameter uncertainty invariants.
9. Canonical prepare_model entry-point and routing stubs.
"""

from __future__ import annotations

import dataclasses
from typing import Any
import numpy as np
import pytest
import scipy.sparse as sp

from portfolio.model import ModelSpecificationError, PreparedModel, prepare_model


def make_valid_model_inputs(m: int = 3, cash_idx: int | None = 2) -> dict[str, Any]:
    """Factory creating fully compliant inputs for PreparedModel."""
    asset_ids = np.arange(m, dtype=np.uint16)
    quote_currency = ["GBP"] * m
    mu_arith_ann = np.array([0.08, 0.05, 0.038][:m], dtype=np.float64)
    if len(mu_arith_ann) < m:
        mu_arith_ann = np.full(m, 0.04, dtype=np.float64)

    # 3x3 base covariance with cash at index 2 (exact 0 volatility)
    cov_ann = np.array(
        [
            [0.04, 0.01, 0.0],
            [0.01, 0.02, 0.0],
            [0.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    )[:m, :m].copy()
    if cash_idx is not None and cash_idx < m:
        cov_ann[cash_idx, :] = 0.0
        cov_ann[:, cash_idx] = 0.0

    mu_log_ann = mu_arith_ann - 0.5 * np.diag(cov_ann)
    cov_monthly = cov_ann / 12.0

    param_uncertainty = (
        np.zeros((m, m), dtype=np.float64),
        np.zeros((m, m), dtype=np.float64),
    )

    is_dist = np.zeros(m, dtype=bool)
    d_yield = np.zeros(m, dtype=np.float64)
    if m > 1:
        is_dist[1] = True
        d_yield[1] = 0.02
    dist_policy = (is_dist, d_yield)

    sleeve_masks = np.ones((64, m), dtype=bool)
    holdings_csr = sp.csr_matrix(np.eye(min(2, m), 5, dtype=np.float32))

    return {
        "asset_ids": asset_ids,
        "quote_currency": quote_currency,
        "mu_arith_ann": mu_arith_ann,
        "mu_log_ann": mu_log_ann,
        "cov_ann": cov_ann,
        "cov_monthly": cov_monthly,
        "param_uncertainty": param_uncertainty,
        "dist_policy": dist_policy,
        "sleeve_masks": sleeve_masks,
        "holdings_csr": holdings_csr,
        "cash_idx": cash_idx,
        "metadata": {"source": "unit_test", "cash_rates": {"obs_aer": 0.0380, "plan_aer": 0.0425}},
    }


def test_valid_prepared_model_instantiation() -> None:
    """Verify clean instantiation, field types, and dimensional consistency."""
    inputs = make_valid_model_inputs(m=3, cash_idx=2)
    model = PreparedModel(**inputs)

    assert model.num_assets == 3
    assert model.M == 3
    assert model.asset_ids.dtype == np.uint16
    assert np.array_equal(model.asset_ids, np.array([0, 1, 2], dtype=np.uint16))
    assert model.quote_currency == ["GBP", "GBP", "GBP"]
    assert model.mu_arith_ann.dtype == np.float64
    assert model.mu_log_ann.dtype == np.float64
    assert model.cov_ann.shape == (3, 3)
    assert model.cov_ann.dtype == np.float64
    assert model.cov_monthly.shape == (3, 3)
    assert model.sleeve_masks.shape == (64, 3)
    assert model.cash_idx == 2
    assert model.holdings_csr is not None
    assert model.holdings_csr.data.dtype == np.float32
    assert model.metadata["source"] == "unit_test"


def test_immutability_frozen_and_read_only_buffers() -> None:
    """Verify dataclass frozenness and read-only status of internal array buffers."""
    inputs = make_valid_model_inputs(m=3, cash_idx=2)
    model = PreparedModel(**inputs)

    # Dataclass attribute assignment is prohibited
    with pytest.raises(dataclasses.FrozenInstanceError):
        model.mu_arith_ann = np.array([0.1, 0.1, 0.1])  # type: ignore[misc]

    # Buffer mutation is prohibited
    with pytest.raises(ValueError, match="read-only"):
        model.cov_ann[0, 0] = 0.99

    with pytest.raises(ValueError, match="read-only"):
        model.mu_arith_ann[0] = 0.99

    with pytest.raises(ValueError, match="read-only"):
        model.asset_ids[0] = 5

    # External modification of inputs does not leak into model
    external_mu = inputs["mu_arith_ann"]
    external_mu[0] = 0.25
    assert model.mu_arith_ann[0] != 0.25


def test_spectral_psd_projection_small_negative_eigenvalue() -> None:
    """Verify spectral projection onto PSD cone when lambda_min is in [-1e-12, 0)."""
    # Construct an orthogonal basis
    rng = np.random.default_rng(42)
    x = rng.standard_normal((3, 3))
    q, _ = np.linalg.qr(x)

    # Eigenvalues with a tiny negative eigenvalue within tolerance
    tiny_neg = -5.0e-13
    diag_eigs = np.array([0.04, 0.02, tiny_neg], dtype=np.float64)
    cov_with_tiny_neg = q @ np.diag(diag_eigs) @ q.T
    cov_with_tiny_neg = 0.5 * (cov_with_tiny_neg + cov_with_tiny_neg.T)

    inputs = make_valid_model_inputs(m=3, cash_idx=None)
    inputs["cov_ann"] = cov_with_tiny_neg
    inputs["cov_monthly"] = cov_with_tiny_neg / 12.0

    # Instantiation must succeed via spectral clipping
    model = PreparedModel(**inputs)

    # Minimum eigenvalue of projected covariance must be non-negative
    evals = np.linalg.eigh(model.cov_ann)[0]
    assert np.min(evals) >= 0.0

    # cov_monthly must match the projected cov_ann
    assert np.allclose(model.cov_monthly, model.cov_ann / 12.0, atol=1e-12)


def test_fatal_structural_negative_eigenvalue() -> None:
    """Verify fatal ModelSpecificationError when lambda_min < -1e-12."""
    rng = np.random.default_rng(42)
    x = rng.standard_normal((3, 3))
    q, _ = np.linalg.qr(x)

    structural_neg = -1.05e-12
    diag_eigs = np.array([0.04, 0.02, structural_neg], dtype=np.float64)
    cov_corrupt = q @ np.diag(diag_eigs) @ q.T
    cov_corrupt = 0.5 * (cov_corrupt + cov_corrupt.T)

    inputs = make_valid_model_inputs(m=3, cash_idx=None)
    inputs["cov_ann"] = cov_corrupt
    inputs["cov_monthly"] = cov_corrupt / 12.0

    with pytest.raises(ModelSpecificationError, match="Fatal non-positive semi-definite covariance matrix"):
        PreparedModel(**inputs)


def test_non_symmetric_covariance_error() -> None:
    """Verify ModelSpecificationError when covariance matrix is not symmetric within 1e-12."""
    inputs = make_valid_model_inputs(m=3, cash_idx=None)
    asymmetric_cov = inputs["cov_ann"].copy()
    asymmetric_cov[0, 1] += 1e-6
    inputs["cov_ann"] = asymmetric_cov
    inputs["cov_monthly"] = asymmetric_cov / 12.0

    with pytest.raises(ModelSpecificationError, match="cov_ann is not symmetric"):
        PreparedModel(**inputs)


def test_cash_anchor_volatility_enforcement() -> None:
    """Verify cash asset requires exact zero price volatility in cov_ann."""
    inputs = make_valid_model_inputs(m=3, cash_idx=2)
    # Violate cash anchor by adding non-zero volatility to asset 2
    inputs["cov_ann"][2, 2] = 0.0001
    inputs["cov_monthly"] = inputs["cov_ann"] / 12.0

    with pytest.raises(ModelSpecificationError, match="Cash anchor at index 2 must have exact 0 price volatility"):
        PreparedModel(**inputs)

    # When cash has exact 0 volatility, it passes
    inputs["cov_ann"][2, 2] = 0.0
    inputs["cov_monthly"] = inputs["cov_ann"] / 12.0
    model = PreparedModel(**inputs)
    assert np.all(model.cov_ann[2, :] == 0.0)


def test_quote_currency_normalization_enforcement() -> None:
    """Verify that quote currencies must all be normalized to GBP."""
    inputs = make_valid_model_inputs(m=3, cash_idx=2)
    inputs["quote_currency"] = ["GBP", "GBx", "GBP"]

    with pytest.raises(ModelSpecificationError, match="normalized to 'GBP'"):
        PreparedModel(**inputs)


def test_mu_arith_bounds_and_finite_checks() -> None:
    """Verify ||mu||_inf < 1.0 and finiteness invariants."""
    inputs = make_valid_model_inputs(m=3, cash_idx=2)
    inputs["mu_arith_ann"][0] = 1.05

    with pytest.raises(ModelSpecificationError, match=r"\|\|mu\|\|_inf < 1\.0"):
        PreparedModel(**inputs)

    inputs = make_valid_model_inputs(m=3, cash_idx=2)
    inputs["mu_arith_ann"][0] = np.nan
    with pytest.raises(ModelSpecificationError, match="finite numbers"):
        PreparedModel(**inputs)


def test_sleeve_masks_shape_and_dtype() -> None:
    """Verify sleeve_masks shape must be (64, M) bool."""
    inputs = make_valid_model_inputs(m=3, cash_idx=2)
    inputs["sleeve_masks"] = np.ones((32, 3), dtype=bool)

    with pytest.raises(ModelSpecificationError, match=r"sleeve_masks must have shape \(64, 3\)"):
        PreparedModel(**inputs)


def test_dist_policy_validation() -> None:
    """Verify dividend yields must be in [0, 1) and non-distributing assets must have 0 yield."""
    inputs = make_valid_model_inputs(m=3, cash_idx=2)
    is_dist = np.array([False, False, False], dtype=bool)
    d_yield = np.array([0.0, 0.03, 0.0], dtype=np.float64)  # Asset 1 has yield but is_dist is False
    inputs["dist_policy"] = (is_dist, d_yield)

    with pytest.raises(ModelSpecificationError, match="Non-distributing assets"):
        PreparedModel(**inputs)

    is_dist = np.array([False, True, False], dtype=bool)
    d_yield = np.array([0.0, 1.2, 0.0], dtype=np.float64)  # >= 1.0
    inputs["dist_policy"] = (is_dist, d_yield)

    with pytest.raises(ModelSpecificationError, match=r"\[0, 1\)"):
        PreparedModel(**inputs)


def test_prepare_model_entry_point_and_routing() -> None:
    """Verify canonical prepare_model signature, invalid method gate, and routing stubs."""
    inputs = make_valid_model_inputs(m=3, cash_idx=2)
    model = PreparedModel(**inputs)

    # Invalid method gate
    with pytest.raises(ModelSpecificationError, match="Invalid preparation method"):
        prepare_model(model, method="unsupported_route")  # type: ignore[arg-type]

    # Passing PreparedModel returns itself
    res_holdings = prepare_model(model, method="holdings")
    assert res_holdings is model

    res_etf = prepare_model(model, method="etf")
    assert res_etf is model

    # Passing dict of prepared inputs constructs PreparedModel
    res_from_dict = prepare_model(inputs, method="holdings")
    assert isinstance(res_from_dict, PreparedModel)
    assert res_from_dict.num_assets == 3

    # Passing raw snapshot raises descriptive NotImplementedError for stubs
    with pytest.raises(NotImplementedError, match="Company-Characteristics Route"):
        prepare_model("raw_snapshot_object", method="holdings")

    with pytest.raises(NotImplementedError, match="ETF-Return Route"):
        prepare_model("raw_snapshot_object", method="etf")
