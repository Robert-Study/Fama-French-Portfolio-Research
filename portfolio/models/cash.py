import numpy as np


def cash_monthly(aer):
    if not np.isfinite(aer) or aer <= -1:
        raise ValueError('Applicable cash AER must be finite and greater than -100%.')
    return float(np.expm1(np.log1p(aer) / 12))
