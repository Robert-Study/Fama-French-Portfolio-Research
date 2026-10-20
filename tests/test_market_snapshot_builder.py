"""Synthetic moments exercise serialization only; they are not production data."""
import json
from dataclasses import replace
import subprocess
import sys

import joblib
import numpy as np
import pytest

from scripts import build_market_snapshot as builder
from portfolio.contracts import MarketSnapshot


@pytest.fixture
def calibration(tmp_path):
    catalogue = builder.build_catalogue(builder.DEFAULT_FIXTURES)
    n = len(catalogue)
    covariance = np.eye(n, dtype=np.float64) * 0.002
    covariance[0, :] = covariance[:, 0] = 0.0
    covariance[1, 2] = covariance[2, 1] = -0.0002
    payload = {
        "as_of_date": "2026-10-18", "source_as_of": "2026-09-30",
        "source": "Synthetic unit-test calibration; never publish",
        "method": "etf", "reporting_currency": "GBP",
        "return_basis": "net_total_return", "moment_basis": "monthly_simple_decimal",
        "tickers": catalogue.ticker.tolist(),
        "mu_monthly": np.full(n, 0.003).tolist(),
        "cov_monthly": covariance.tolist(),
        "C_mat": (np.eye(n) * 0.0001).tolist(),
        "U_mat": (np.eye(n) * 0.00001).tolist(),
    }
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


def test_serialization_and_canonical_sleeves(calibration, tmp_path):
    path, payload = calibration
    out = tmp_path / "market_snapshot.joblib"
    assert builder.main(["--calibration", str(path), "--out", str(out)]) == 0
    snapshot = joblib.load(out)
    fresh = subprocess.run(
        [sys.executable, "-c", "import joblib, sys; s = joblib.load(sys.argv[1]); "
         "print('Loaded snapshot:', len(s.tickers), 'tickers, as_of:', s.as_of_date)", str(out)],
        cwd=builder.ROOT, capture_output=True, text=True, check=True,
    )
    assert "Loaded snapshot: 68 tickers, as_of: 2026-10-18" in fresh.stdout
    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.as_of_date == "2026-10-18"
    assert snapshot.tickers == tuple(payload["tickers"])
    assert len(snapshot.tickers) == 68 and snapshot.cash_index == 0
    np.testing.assert_allclose(snapshot.mu_arith_ann, np.array(payload["mu_monthly"]) * 12)
    np.testing.assert_allclose(snapshot.cov_ann, np.array(payload["cov_monthly"]) * 12)
    np.testing.assert_array_equal(snapshot.mu_log_ann,
                                  snapshot.mu_arith_ann - 0.5 * np.diag(snapshot.cov_ann))
    assert not snapshot.cov_ann[0].any() and not snapshot.cov_ann[:, 0].any()
    assert snapshot.sleeve_masks.dtype == bool
    assert not snapshot.sleeve_masks[0].any() and snapshot.sleeve_masks[63].all()
    expected = {"VWRP": 1, "EQQQ": 2, "3QQQ": 2, "IGLT": 4,
                "VAGS": 8, "SGLN": 16, "T212_GBP_CASH": 32}
    for ticker, bit in expected.items():
        index = snapshot.tickers.index(ticker)
        np.testing.assert_array_equal(snapshot.sleeve_masks[:, index],
                                      np.arange(64) & bit != 0)
    for mask in range(64):
        union = np.zeros(68, dtype=bool)
        for bit in (1, 2, 4, 8, 16, 32):
            if mask & bit:
                union |= snapshot.sleeve_masks[bit]
        np.testing.assert_array_equal(snapshot.sleeve_masks[mask], union)
    for matrix in (snapshot.cov_ann, *snapshot.param_uncertainty):
        assert matrix.dtype == np.float64 and matrix.shape == (68, 68)
        assert np.linalg.eigvalsh(matrix).min() >= -1e-12


@pytest.mark.parametrize("field,value,match", [
    ("as_of_date", "2026-10-19", "as_of_date"),
    ("source_as_of", "2026-10-19", "cut-off"),
    ("reporting_currency", "USD", "reporting_currency"),
    ("return_basis", "gross", "return_basis"),
    ("moment_basis", "annual_log", "moment_basis"),
    ("source", "", "source"),
    ("method", "unknown", "method"),
])
def test_reject_wrong_conventions(calibration, tmp_path, field, value, match):
    path, payload = calibration
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        builder.build_snapshot(builder.DEFAULT_FIXTURES, path)


def test_reject_partial_or_reordered_universe(calibration):
    path, payload = calibration
    payload["tickers"] = payload["tickers"][::-1]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical order"):
        builder.build_snapshot(builder.DEFAULT_FIXTURES, path)


@pytest.mark.parametrize("fault", ["cash", "psd", "nan", "uncertainty", "log", "dtype"])
def test_reject_bad_moments(calibration, fault):
    snapshot = builder.build_snapshot(builder.DEFAULT_FIXTURES, calibration[0])
    changes = {}
    if fault in ("cash", "psd", "nan"):
        cov = snapshot.cov_ann.copy()
        cov[0 if fault == "cash" else 1, 0 if fault == "cash" else 1] = {
            "cash": 0.001, "psd": -0.1, "nan": np.nan}[fault]
        changes["cov_ann"] = cov
    elif fault == "uncertainty":
        changes["param_uncertainty"] = (-np.eye(68), np.eye(68))
    elif fault == "log":
        changes["mu_log_ann"] = snapshot.mu_log_ann + 0.01
    else:
        changes["mu_arith_ann"] = snapshot.mu_arith_ann.astype(np.float32)
    with pytest.raises(ValueError):
        replace(snapshot, **changes)


def test_missing_input_does_not_publish(tmp_path):
    out = tmp_path / "market_snapshot.joblib"
    assert builder.main(["--calibration", str(tmp_path / "missing.json"),
                         "--out", str(out)]) == 2
    assert not out.exists()


def test_existing_output_is_preserved(calibration, tmp_path):
    out = tmp_path / "market_snapshot.joblib"
    out.write_bytes(b"existing artifact")
    assert builder.main(["--calibration", str(calibration[0]), "--out", str(out)]) == 2
    assert out.read_bytes() == b"existing artifact"


def test_failed_write_is_not_published(calibration, tmp_path, monkeypatch):
    out = tmp_path / "market_snapshot.joblib"

    def fail_dump(snapshot, path, compress):
        path.write_bytes(b"partial")
        raise OSError("simulated storage failure")

    monkeypatch.setattr(builder.joblib, "dump", fail_dump)
    assert builder.main(["--calibration", str(calibration[0]), "--out", str(out)]) == 2
    assert not out.exists()
    assert not list(tmp_path.glob(".market-snapshot-*"))


def test_release_references_use_snapshot_order(calibration):
    from scripts.build_v8_release import _reference_weights

    snapshot = builder.build_snapshot(builder.DEFAULT_FIXTURES, calibration[0])
    refs = _reference_weights(builder.ROOT / "data/release_inputs/reference_portfolios.json",
                              snapshot.tickers)
    assert len(refs) == 6
