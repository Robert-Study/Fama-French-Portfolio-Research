import numpy as np
import pandas as pd


def lookthrough(holdings, securities, weights: pd.Series):
    rows = holdings.loc[holdings.ETF_ID.isin(weights.index)].copy()
    rows["PortfolioWeight"] = rows.Weight * rows.ETF_ID.map(weights)
    positions = rows.groupby("HOLDING_ID").PortfolioWeight.sum().to_frame().join(securities, how="left")
    positions = positions.loc[positions.PortfolioWeight.abs() > 1e-12]
    countries = positions.groupby(positions.Country.fillna("Unknown")).PortfolioWeight.sum().sort_values(ascending=False)
    sectors = positions.groupby(positions.Sector.fillna("Unknown")).PortfolioWeight.sum().sort_values(ascending=False)
    return positions.sort_values("PortfolioWeight", ascending=False), countries, sectors


def matched_overlap(holdings, securities, fund_ids):
    equity_ids = securities.index[securities.AssetClass.eq("Equity")]
    rows = holdings.loc[holdings.ETF_ID.isin(fund_ids) & holdings.HOLDING_ID.isin(equity_ids)]
    matrix = rows.pivot_table(index="HOLDING_ID", columns="ETF_ID", values="Weight", aggfunc="sum", fill_value=0)
    h = matrix.reindex(columns=fund_ids, fill_value=0).to_numpy().clip(min=0)
    overlap = np.empty((len(fund_ids), len(fund_ids)))
    for i in range(len(fund_ids)):
        for j in range(i, len(fund_ids)):
            overlap[i, j] = overlap[j, i] = np.minimum(h[:, i], h[:, j]).sum()
    return pd.DataFrame(overlap, index=fund_ids, columns=fund_ids)


def effective_companies(holdings, weights, equity_ids, leverage=None):
    """Reviewed company_id merges listings/share classes. Coverage is economic equity.

    holdings columns: instrument, company_id, weight, as_of. Unmapped rows retain
    blank company_id. Rows must already be recursively expanded to companies.
    """
    leverage = {} if leverage is None else leverage
    equity_weights = {i: float(weights.get(i, 0)) * float(leverage.get(i, 1)) for i in equity_ids}
    denominator = sum(equity_weights.values())
    if denominator <= 1e-12:
        return {'effective_companies': None, 'coverage': None, 'status': 'N/A — no equity sleeve', 'as_of': None}, pd.Series(dtype=float)
    if holdings.empty:
        return {'effective_companies': None, 'coverage': 0.0, 'status': 'Insufficient coverage', 'as_of': None}, pd.Series(dtype=float)
    required = {'instrument', 'company_id', 'weight', 'as_of'}
    if not required.issubset(holdings):
        raise ValueError('Reviewed company IDs, economic weights and dates required.')
    rows = holdings[holdings.instrument.isin(equity_weights)].copy()
    if not np.isfinite(rows.weight).all() or (rows.weight < 0).any() or (rows.groupby('instrument').weight.sum() > 1 + 1e-6).any():
        raise ValueError('Company weights must be nonnegative and cannot exceed 100% of a sleeve.')
    rows['exposure'] = rows.weight * rows.instrument.map(equity_weights)
    mapped = rows[rows.company_id.notna() & rows.company_id.astype(str).ne('')]
    exposure = mapped.groupby('company_id').exposure.sum()
    coverage = float(exposure.sum() / denominator)
    sufficient = coverage >= .95 - 1e-12
    dates = rows.loc[rows.exposure > 1e-12, 'as_of']
    from portfolio.validation import age_days
    stale = dates.empty or any(age_days(d) > 90 for d in dates)
    status = 'Insufficient coverage' if not sufficient else ('Stale holdings' if stale else ('Partial-coverage estimate' if coverage < 1 - 1e-6 else 'Mapped equity sleeve'))
    count = None if not sufficient or stale else float(1 / np.square(exposure / exposure.sum()).sum())
    return {'effective_companies': count, 'coverage': coverage, 'status': status,
            'as_of': None if dates.empty else str(dates.min()), 'unmapped_equity_exposure': denominator - float(exposure.sum())}, exposure


def expand_company_holdings(root_ids, fund_holdings, company_map, as_of):
    """Recursively expand reviewed fund/security graphs without inventing issuers.

    fund_holdings maps fund IDs to {child_id: fractional exposure}; company_map
    maps reviewed security/share-class IDs to company IDs. Unknown residuals are
    retained unmapped. Outer product leverage is applied by effective_companies.
    """
    output = []
    def descend(root, node, exposure, stack):
        if node in stack or len(stack) >= 16:
            raise ValueError('Cyclic or excessively nested holdings graph.')
        if node in fund_holdings:
            children = fund_holdings[node]
            values = np.asarray(list(children.values()), float)
            if not np.isfinite(values).all() or (values < 0).any() or values.sum() > 1 + 1e-6:
                raise ValueError('Invalid reviewed fund holding fractions.')
            for child, fraction in children.items():
                descend(root, child, exposure * fraction, stack + (node,))
            missing = max(0.0, 1 - float(values.sum()))
            if missing:
                output.append({'instrument': root, 'company_id': None, 'weight': exposure * missing, 'as_of': as_of})
        else:
            output.append({'instrument': root, 'company_id': company_map.get(node), 'weight': exposure, 'as_of': as_of})
    for root in root_ids:
        descend(root, root, 1.0, ())
    rows = pd.DataFrame(output)
    return rows.groupby(['instrument', 'company_id', 'as_of'], dropna=False, as_index=False).weight.sum()
