"""Explicit carry and yield stresses; current inputs are never historical backfills."""
import numpy as np


def bond_forecast(yield_value, fee, *, yield_kind='nominal', inflation=None,
                  expected_loss=0.0, hedge_cost=0.0, hedge_embedded=False):
    values = [yield_value, fee, expected_loss, hedge_cost]
    if not np.isfinite(values).all() or min(fee, expected_loss) < 0:
        raise ValueError('Bond inputs must be finite; product fees/default losses nonnegative. Hedge carry can have either sign.')
    if yield_kind not in ('nominal', 'real', 'yield_to_worst'):
        raise ValueError('Explicit nominal, real or yield-to-worst convention required.')
    carry = yield_value
    if yield_kind == 'real':
        if inflation is None or not np.isfinite(inflation):
            raise ValueError('Real yields require an explicit inflation assumption.')
        carry = (1 + yield_value) * (1 + inflation) - 1
    if hedge_embedded and hedge_cost:
        raise ValueError('Hedge cost already embedded in carry; do not charge twice.')
    return (carry - fee - expected_loss - hedge_cost) / 12


def bond_stress(duration, yield_change, convexity=0.0, *, spread_duration=0.0, spread_change=0.0):
    if not np.isfinite([duration, yield_change, convexity, spread_duration, spread_change]).all() or min(duration, convexity, spread_duration) < 0:
        raise ValueError('Invalid dated duration/convexity inputs.')
    return -duration * yield_change + 0.5 * convexity * yield_change**2 - spread_duration * spread_change
