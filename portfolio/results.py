from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json

import numpy as np
import pandas as pd

from portfolio import __version__
from portfolio.calibration import expected_returns
from portfolio.optimise import Frontier, efficient_frontier
from portfolio.risk import shrunk_covariance


@dataclass
class Run:
    run_id: str
    created: str
    mode: str
    fingerprint: str
    settings: dict
    funds: pd.DataFrame
    mean: np.ndarray
    covariance: np.ndarray
    frontier: Frontier
    etfs: pd.DataFrame
    diagnostics: pd.DataFrame
    betas: pd.DataFrame | None
    reference: dict


def assemble_run(mode, fingerprint, settings, funds, mean, covariance, diagnostics, betas=None):
    ids = settings["funds"]
    indices = funds.index.get_indexer(ids)
    if (indices < 0).any() or len(set(ids)) != len(ids):
        raise ValueError("The selected universe includes unknown or duplicate funds.")
    chosen_mean = mean[indices]
    chosen_covariance = covariance[np.ix_(indices, indices)]
    frontier = efficient_frontier(chosen_mean, chosen_covariance, cap=settings["cap"])
    etfs = funds[["Name", "TER"]].copy()
    etfs["Annualised arithmetic return"] = 12 * mean
    etfs["Annualised monthly volatility"] = np.sqrt(12 * np.diag(covariance))
    if betas is not None:
        etfs = etfs.join(betas)
    reference_id = "ACWI" if "ACWI" in funds.index else str(funds.index[0])
    j = funds.index.get_loc(reference_id)
    reference = {"ETF_ID": reference_id, "return": float(mean[j]), "volatility": float(np.sqrt(covariance[j, j]))}
    identity = {"version": __version__, "mode": mode, "data": fingerprint, "settings": settings}
    run_id = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12]
    return Run(run_id, datetime.now(timezone.utc).isoformat(), mode, fingerprint, settings,
               funds.loc[ids], chosen_mean, chosen_covariance, frontier, etfs, diagnostics,
               None if betas is None else betas.loc[ids], reference)


def legacy_run(data, ids, window, cap):
    funds = data.funds.loc[data.funds.AssetClass.eq("Equity")]
    returns = data.returns[funds.index].tail(window)
    covariance, shrinkage = shrunk_covariance(returns.to_numpy())
    settings = {"funds": list(ids), "window": len(returns), "cap": cap,
                "start": str(returns.index[0]), "end": str(returns.index[-1]),
                "return_basis": "Legacy sample arithmetic mean; treated as net of fees; unverified GBP",
                "covariance": "Ledoit-Wolf covariance of legacy monthly simple returns",
                "shrinkage": shrinkage, "status": "LEGACY / UNVERIFIED"}
    diagnostics = pd.DataFrame({"Check": ["Return provenance", "GBP treatment", "Company fundamentals", "Factor calibration"],
                                "Status": ["Unverified", "Unverified", "Missing", "Not used in legacy mode"]})
    return assemble_run("Legacy demonstration", data.fingerprint, settings, funds,
                        returns.mean().to_numpy(), covariance, diagnostics)


def research_run(data, fit, ids, cap, premiums_annual, cash_annual, style_multiplier):
    premiums = np.asarray(premiums_annual, dtype=float).copy() / 12
    premiums[1:] *= style_multiplier
    mean = expected_returns(fit.betas.to_numpy(), premiums, cash_annual / 12, data.funds.TER.to_numpy())
    settings = {"funds": list(ids), "window": fit.months, "cap": cap, "start": fit.sample_start,
                "end": fit.sample_end, "cash_annual_arithmetic": cash_annual,
                "premiums_annual_arithmetic": (premiums * 12).tolist(), "style_multiplier": style_multiplier,
                "return_basis": "Assumed cash + fitted FF5 beta × assumed premiums − TER; gross alpha = 0",
                "covariance": "Joint Ledoit-Wolf factor/residual covariance, including cross terms",
                "shrinkage": fit.joint_shrinkage, "status": "SUPPLIED DATA / RESEARCH ASSUMPTIONS",
                "covariance_difference_frobenius": float(np.linalg.norm(fit.covariance - fit.direct_covariance)),
                "sources": data.manifest["sources"]}
    return assemble_run("Return-based FF5", data.fingerprint, settings, data.funds, mean,
                        fit.covariance, fit.diagnostics, fit.betas)
