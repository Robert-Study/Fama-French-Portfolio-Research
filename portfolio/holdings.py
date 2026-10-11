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
