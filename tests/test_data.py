from pathlib import Path

import pandas as pd
import pytest

from portfolio.data import DataError, load_legacy, monthly_frame


ROOT = Path(__file__).resolve().parents[1]


def test_original_files_are_unchanged_and_signed_positions_survive():
    data = load_legacy(ROOT / "data/legacy")
    assert data.returns.shape == (360, 29)
    assert len(data.holdings) == 24724
    assert (data.holdings.Weight < 0).sum() == 30
    assert data.inventory.checksum_matches.all()


@pytest.mark.parametrize("months", [["2020-01-01", "2020-01-31"], ["2020-01-01", "2020-03-01"]])
def test_duplicate_or_missing_months_are_rejected(months):
    with pytest.raises(DataError):
        monthly_frame(pd.DataFrame({"Month": months, "ETF": [0.01, 0.02]}), "test")


def test_missing_values_are_not_filled():
    with pytest.raises(DataError):
        monthly_frame(pd.DataFrame({"Month": ["2020-01-01"], "ETF": [float("nan")]}), "test")
