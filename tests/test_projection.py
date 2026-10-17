import numpy as np
import pandas as pd
import pytest

from portfolio.holdings import lookthrough, matched_overlap
from portfolio.projection import buy_and_hold_projection


def test_zero_risk_and_single_fund_moments():
    mu, variance = 0.005, 0.002
    result = buy_and_hold_projection([1], [mu], [[variance]], years=1)
    expected = 10000 * (1 + mu)**12
    expected_variance = 10000**2 * ((1 + mu)**2 + variance)**12 - expected**2
    assert result.iloc[-1]["Expected wealth"] == pytest.approx(expected)
    assert result.iloc[-1].Variance == pytest.approx(expected_variance)
    zero = buy_and_hold_projection([1], [mu], [[0]], years=20)
    np.testing.assert_allclose(zero.Median, zero["Expected wealth"])
    np.testing.assert_allclose(zero.P20, zero.P80)


def test_buy_and_hold_allows_weights_to_drift():
    w = np.array([0.5, 0.5])
    result = buy_and_hold_projection(w, [0.00, 0.01], np.zeros((2, 2)), years=2)
    assert result.iloc[-1]["Expected wealth"] == pytest.approx(10000 * (0.5 + 0.5 * 1.01**24))
    assert result.iloc[-1]["Expected wealth"] != pytest.approx(10000 * 1.005**24)


def test_splitting_a_holding_does_not_change_lookthrough_or_overlap():
    securities = pd.DataFrame({"HOLDING_ID": ["X", "Y"], "AssetClass": "Equity", "Country": ["UK", "US"],
                               "Sector": ["Tech", "Health"]}).set_index("HOLDING_ID")
    holdings = pd.DataFrame({"ETF_ID": ["A", "A", "B", "B"], "HOLDING_ID": ["X", "Y", "X", "Y"],
                             "Weight": [0.7, 0.3, 0.6, 0.4]})
    split = pd.concat([holdings.iloc[1:], pd.DataFrame({"ETF_ID": ["A", "A"], "HOLDING_ID": ["X", "X"], "Weight": [0.35, 0.35]})])
    np.testing.assert_allclose(matched_overlap(holdings, securities, ["A", "B"]), matched_overlap(split, securities, ["A", "B"]))
    weights = pd.Series({"A": 0.5, "B": 0.5})
    original, _, _ = lookthrough(holdings, securities, weights)
    copied, _, _ = lookthrough(split, securities, weights)
    pd.testing.assert_frame_equal(original, copied)
