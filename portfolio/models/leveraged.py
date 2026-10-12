"""Daily native-currency reset engine. Admission requires separately verified terms."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class LeverageTerms:
    leverage: float
    annual_fee: float
    day_basis: int
    funding_embedded: bool = False
    annual_other_drag: float = 0.0
    termination_return: float = -1.0
    intraday_reset: bool = False
    input_kind: str = 'unlevered_underlying'


def daily_leverage(underlying, funding, terms: LeverageTerms, fx=None):
    """Time is the last axis. Loss of NAV is absorbing for the whole path.

    Underlying is net where a wrapper inherits underlying fund fees. No extra
    underlying TER is charged. Intraday-reset products need actual intraday data.
    """
    r = np.asarray(underlying, float)
    f = np.broadcast_to(np.asarray(funding, float), r.shape)
    if r.ndim < 1 or not np.isfinite(r).all() or not np.isfinite(f).all() or (r < -1).any():
        raise ValueError('Finite actual daily paths and aligned funding required.')
    if terms.intraday_reset:
        raise ValueError('Intraday reset requires intraday evidence; daily engine cannot admit this product.')
    if not np.isfinite([terms.leverage, terms.annual_fee, terms.annual_other_drag, terms.termination_return]).all() or terms.leverage <= 1 or min(terms.annual_fee, terms.annual_other_drag) < 0 or terms.day_basis not in (252, 360, 365):
        raise ValueError('Invalid documented leverage terms.')
    if terms.funding_embedded and np.any(f != 0):
        raise ValueError('Funding already embedded; do not charge twice.')
    if terms.input_kind not in ('unlevered_underlying', 'leveraged_index_net_funding'):
        raise ValueError('Unknown documented native benchmark return definition.')
    if terms.funding_embedded != (terms.input_kind == 'leveraged_index_net_funding'):
        raise ValueError('Embedded funding requires a documented already-leveraged net-funding index.')
    if not -1 <= terms.termination_return < 0:
        raise ValueError('Invalid issuer termination threshold.')
    native = r if terms.input_kind == 'leveraged_index_net_funding' else terms.leverage * r - (terms.leverage - 1) * f
    native = native - (terms.annual_fee + terms.annual_other_drag) / terms.day_basis
    dead = np.maximum.accumulate(native <= terms.termination_return, axis=-1)
    previous_dead = np.concatenate([np.zeros_like(dead[..., :1]), dead[..., :-1]], axis=-1)
    out = np.where(previous_dead, 0.0, np.where(dead, -1.0, native))
    if fx is not None:
        fx = np.broadcast_to(np.asarray(fx, float), r.shape)
        if not np.isfinite(fx).all() or (fx <= -1).any():
            raise ValueError('Invalid GBP-per-native FX path.')
        out = np.where(previous_dead, 0, (1 + out) * (1 + fx) - 1)
    return out


def overlap_error(model, actual):
    model, actual = map(np.asarray, (model, actual))
    if model.shape != actual.shape or len(model) < 60 or not np.isfinite([model, actual]).all():
        raise ValueError('At least 60 aligned actual daily observations required.')
    return {'daily_rmse': float(np.sqrt(np.mean((model - actual)**2))),
            'cumulative_tracking_difference': float(np.prod(1 + model) - np.prod(1 + actual))}
