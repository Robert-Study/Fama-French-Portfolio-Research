"""Fixed actual historical references, independent of forward-model admission."""
import numpy as np
import pandas as pd
from portfolio.validation import BENCHMARKS


def reference_returns(snapshot, allocation):
    missing=[i for i in allocation if i not in snapshot.returns or not
             snapshot.evidence.get(i,{}).get('distribution_split_reconciled')]
    if missing:
        return None,'Reconciled actual history unavailable: '+', '.join(missing)
    panel=snapshot.returns[list(allocation)].dropna()
    if len(panel)<36 or not panel.index.equals(pd.period_range(panel.index[0],panel.index[-1],freq='M')):
        return None,'Need 36 contiguous common actual GBP months'
    return panel @ pd.Series(allocation),'Fixed weights, rebalanced monthly; actual net GBP returns'


def historical_references(snapshot):
    result={}
    for label,allocation in BENCHMARKS.items():
        returns,basis=reference_returns(snapshot,allocation)
        if returns is None:
            result[label]=dict(available=False,reason=basis);continue
        levels=np.r_[100,100*np.cumprod(1+returns.to_numpy())]
        drawdown=levels/np.maximum.accumulate(levels)-1
        result[label]=dict(available=True,basis=basis,start=str(returns.index[0]),end=str(returns.index[-1]),
                           months=len(returns),annual_arithmetic_mean=float(returns.mean()*12),
                           annual_volatility=float(returns.std(ddof=1)*np.sqrt(12)),
                           terminal_index=float(levels[-1]),max_drawdown=float(drawdown.min()),
                           limitations=[snapshot.evidence[i]['reconciliation_warning'] for i in allocation if snapshot.evidence[i].get('reconciliation_warning')])
    return result
