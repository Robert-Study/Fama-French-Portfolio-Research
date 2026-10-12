import numpy as np


def commodity_forecast(cash_monthly, annual_fee, annual_excess_premium=0.0):
    """Neutral excess-premium research prior, not a coupon for physical metals.

    For futures, the supplied history must already include roll/collateral returns.
    """
    if not np.isfinite([cash_monthly, annual_fee, annual_excess_premium]).all() or annual_fee < 0:
        raise ValueError('Invalid commodity prior/cost inputs.')
    return cash_monthly + (annual_excess_premium - annual_fee) / 12
