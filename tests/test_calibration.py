from io import BytesIO
import json
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from portfolio.bundle import FACTORS, convert_factors_to_gbp, read_bundle
from portfolio.calibration import expected_returns, fit_ff5
from portfolio.data import DataError


def sample_bundle(change=None):
    rng = np.random.default_rng(42)
    months = pd.period_range("2010-01", periods=144, freq="M")
    x = rng.normal(0.004, 0.025, (len(months), 5))
    beta = np.array([[1.0, 0.1, 0.4, 0.2, -0.1], [0.8, -0.2, 0.1, 0.3, 0.1]])
    returns = pd.DataFrame(x @ beta.T + 0.001 - 0.0024 / 12, columns=["A", "B"])
    returns.insert(0, "Month", months.astype(str))
    factors = pd.DataFrame(x, columns=FACTORS)
    factors.insert(0, "Month", months.astype(str))
    factors["RF"] = 0.001
    cash = pd.DataFrame({"Month": months.astype(str), "GBP_RF": 0.001, "USD_GBP": 0.0})
    funds = pd.DataFrame({"ETF_ID": ["A", "B"], "Name": ["Test A", "Test B"], "ISIN": ["TEST_A", "TEST_B"],
                          "AssetClass": "Equity", "Region": "Developed", "Hedged": False, "Leverage": 1, "TER": 0.0024,
                          "ReturnKind": "actual_fund", "Source": "Synthetic test fixture"})
    manifest = {"schema_version": 1, "return_currency": "GBP", "return_type": "monthly_simple_net_total",
                "factor_currency": "USD", "factor_region": "Developed", "units": "decimal",
                "fx_definition": "GBP per USD simple return",
                "sources": {k: "Synthetic test fixture" for k in ["funds", "returns", "factors", "cash", "fx"]}}
    if change:
        change(manifest)
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, frame in [("funds", funds), ("returns", returns), ("factors", factors), ("cash_fx", cash)]:
            archive.writestr(name + ".csv", frame.to_csv(index=False))
        archive.writestr("manifest.json", json.dumps(manifest))
    return output.getvalue(), beta


def test_currency_conversion_distinguishes_market_and_long_short_factors():
    index = pd.period_range("2020-01", periods=1, freq="M")
    usd = pd.DataFrame([[0.02, 0.01, -0.01, 0.0, 0.015, 0.001]], index=index, columns=FACTORS + ["RF"])
    cash = pd.DataFrame({"GBP_RF": [0.002], "USD_GBP": [0.10]}, index=index)
    converted = convert_factors_to_gbp(usd, cash)
    assert converted.iloc[0]["Mkt-RF"] == pytest.approx(1.021 * 1.10 - 1 - 0.002)
    assert converted.iloc[0]["SMB"] == pytest.approx(0.011)
    assert converted.iloc[0]["RMW"] == 0


def test_known_betas_are_recovered_without_carrying_net_alpha_into_forecast():
    raw, beta = sample_bundle()
    data = read_bundle(raw)
    fit = fit_ff5(data.returns, data.factors, data.cash)
    np.testing.assert_allclose(fit.betas, beta, atol=1e-10)
    assert fit.diagnostics.holdout_rmse.max() < 1e-10
    np.testing.assert_allclose(fit.diagnostics.fitted_net_alpha_monthly, -0.0024 / 12)
    premium = np.array([0.005, 0.001, 0.002, 0.001, 0.0])
    result = expected_returns(fit.betas, premium, 0.002, data.funds.TER)
    np.testing.assert_allclose(result, 0.002 + beta @ premium - 0.0024 / 12)
    higher_fee = expected_returns(fit.betas, premium, 0.002, data.funds.TER + 0.0012)
    np.testing.assert_allclose(result - higher_fee, 0.0012 / 12)


def test_holdout_is_not_used_to_select_penalty():
    raw, _ = sample_bundle()
    data = read_bundle(raw)
    original = fit_ff5(data.returns, data.factors, data.cash)
    altered = data.returns.copy()
    altered.iloc[-12:] += 0.20
    stressed = fit_ff5(altered, data.factors, data.cash)
    np.testing.assert_array_equal(original.diagnostics.ridge_penalty, stressed.diagnostics.ridge_penalty)
    assert stressed.diagnostics.holdout_rmse.min() > 0.19


def test_undeclared_currency_or_percent_units_are_rejected():
    raw, _ = sample_bundle(lambda m: m.update(units="percent"))
    with pytest.raises(DataError, match="contract"):
        read_bundle(raw)


def test_unknown_files_are_rejected_without_extraction():
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("../outside.csv", "test")
    with pytest.raises(DataError, match="exactly"):
        read_bundle(output.getvalue())
