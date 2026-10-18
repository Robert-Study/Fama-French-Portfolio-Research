"""Deterministic tests for V8 Streamlit UI modules and shared contracts."""
from __future__ import annotations

import numpy as np
import pytest

from ui.v8_shared import (
    TOTAL,
    REFERENCE_KEYS,
    checked_weights,
    as_weights,
    copy,
    diagnostics,
    Portfolio,
    release_manifest,
    require_release_path,
)


def test_v8_shared_constants_and_copy():
    assert TOTAL == 10000
    assert "sp500" in REFERENCE_KEYS
    assert "all_cap" in REFERENCE_KEYS

    # Test copy key resolution
    app_title = copy("app.title")
    assert "Portfolio Construction Lab" in app_title
    app_version = copy("app.version")
    assert "V8.0" in app_version

    # Fallback interpolation
    interpolated = copy("app.release.value", release="V8.0-Test")
    assert "V8.0-Test" in interpolated


def test_checked_weights_valid_and_bounds():
    # Valid 68-asset allocation (e.g. 100% in asset 0)
    q = np.zeros(68, dtype=np.int64)
    q[0] = 10000
    res = checked_weights(q)
    assert len(res) == 68
    assert res.sum() == 10000

    # Valid multi-asset allocation satisfying >= 10 bps gate
    q2 = np.zeros(68, dtype=np.int64)
    q2[0] = 6000
    q2[1] = 4000
    res2 = checked_weights(q2)
    assert res2.sum() == 10000

    # Negative allocation fails
    q_neg = q.copy()
    q_neg[0] = 10050
    q_neg[1] = -50
    with pytest.raises(ValueError, match="negative"):
        checked_weights(q_neg)

    # Sum != 10000 fails
    q_bad_sum = q.copy()
    q_bad_sum[0] = 9999
    with pytest.raises(ValueError, match="10000"):
        checked_weights(q_bad_sum)

    # Position < 10 bps fails semi-continuous gate
    q_sub_gate = q.copy()
    q_sub_gate[0] = 9995
    q_sub_gate[1] = 5
    with pytest.raises(ValueError, match="10 bps"):
        checked_weights(q_sub_gate)


def test_as_weights_conversion():
    q = np.zeros(68, dtype=np.int64)
    q[0] = 6000
    q[1] = 4000
    w = as_weights(q)
    assert np.isclose(w[0], 0.60)
    assert np.isclose(w[1], 0.40)
    assert np.isclose(w.sum(), 1.0)


def test_portfolio_dataclass_and_diagnostics():
    q_tuple = tuple([10000] + [0] * 67)
    p = Portfolio(name="Test 100%", q_bps=q_tuple, method="holdings", release_id="V8.0-Test")
    assert p.name == "Test 100%"
    assert p.vector().sum() == 10000

    # Diagnostics mock model
    class MockModel:
        mu_arith_ann = np.array([0.08] + [0.04] * 67)
        cov_ann = np.eye(68) * 0.04

    d = diagnostics(MockModel, p.vector(), leverage=np.ones(68))
    assert np.isclose(d["mu"], 0.08)
    assert np.isclose(d["sigma"], 0.20)
    assert np.isclose(d["gross"], 1.0)


def test_release_manifest_and_require_path():
    manifest = release_manifest()
    assert "release_id" in manifest
    assert "references" in manifest

    # Path resolution returns valid Path object
    target = require_release_path("manifest.json")
    assert target is not None
