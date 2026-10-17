"""Explicit unit, dividend and currency conventions for issuer histories."""
import numpy as np
import pandas as pd

from portfolio.data import DataError


def total_returns(nav, distributions, split_ratio=None, unit='GBP'):
    """NAV/distributions are in the same unit. Split ratios apply on the ex-date.

    Distribution is per post-split share, reinvested at ex-date closing NAV.
    No generic close-price source is accepted as adjusted total-return evidence.
    """
    nav, distributions = nav.astype(float), distributions.astype(float)
    split = pd.Series(1.0, index=nav.index) if split_ratio is None else split_ratio.astype(float)
    if unit not in ('GBP', 'GBX', 'USD', 'EUR'):
        raise DataError('Unknown price unit.')
    if not nav.index.equals(distributions.index) or not nav.index.equals(split.index):
        raise DataError('NAV, distributions and splits need identical dates.')
    if not np.isfinite(np.column_stack([nav, distributions, split])).all() or (nav <= 0).any() or (distributions < 0).any() or (split <= 0).any():
        raise DataError('Invalid NAV/distribution/split observations.')
    scale = 0.01 if unit == 'GBX' else 1.0
    price, income = nav * scale, distributions * scale
    return ((price + income) * split / price.shift(1) - 1).iloc[1:]


def to_gbp(returns, currency, fx_returns=None):
    if currency in ('GBP', 'GBX'):
        if fx_returns is not None:
            raise DataError('GBP/GBX listing must not be converted twice.')
        return returns.copy()
    if currency not in ('USD', 'EUR') or fx_returns is None or not returns.index.equals(fx_returns.index):
        raise DataError('Verified GBP-per-native-currency FX returns required.')
    if not np.isfinite(fx_returns).all() or (fx_returns <= -1).any():
        raise DataError('Invalid FX returns.')
    return (1 + returns) * (1 + fx_returns) - 1


def monthly_returns(daily):
    if not isinstance(daily.index, pd.DatetimeIndex) or daily.index.has_duplicates or not daily.index.is_monotonic_increasing:
        raise DataError('Daily observations need unique ordered dates.')
    if not np.isfinite(daily.to_numpy()).all() or (daily < -1).any().any():
        raise DataError('Daily returns contain invalid or missing values.')
    out = (1 + daily).groupby(daily.index.to_period('M')).prod() - 1
    out.index.name = 'Month'
    return out


def compounded_sonia(daily_rates, calendar_days):
    """SONIA annual decimal rates accrue actual/365, including non-business days."""
    if not daily_rates.index.equals(calendar_days.index) or (calendar_days <= 0).any():
        raise DataError('SONIA accrual days must be explicit and aligned.')
    return monthly_returns((daily_rates * calendar_days / 365).to_frame('GBP_RF')).GBP_RF
