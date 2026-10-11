from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from zipfile import BadZipFile, ZipFile

import numpy as np
import pandas as pd

from portfolio.data import DataError, monthly_frame


FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
MAX_BYTES = 10 * 1024 * 1024
FILES = {"funds.csv", "returns.csv", "factors.csv", "cash_fx.csv", "manifest.json"}


@dataclass
class ResearchData:
    funds: pd.DataFrame
    returns: pd.DataFrame
    factors: pd.DataFrame
    cash: pd.Series
    manifest: dict
    fingerprint: str


def convert_factors_to_gbp(usd: pd.DataFrame, cash_fx: pd.DataFrame) -> pd.DataFrame:
    if not usd.index.equals(cash_fx.index):
        raise DataError("Factor and cash/FX months must match exactly.")
    fx = cash_fx["USD_GBP"]
    gbp = usd[FACTORS].mul(1 + fx, axis=0)
    gbp["Mkt-RF"] = (1 + usd["Mkt-RF"] + usd["RF"]) * (1 + fx) - 1 - cash_fx["GBP_RF"]
    return gbp


def read_bundle(raw: bytes) -> ResearchData:
    if len(raw) > MAX_BYTES:
        raise DataError("The input bundle must be at most 10 MB.")
    try:
        with ZipFile(BytesIO(raw)) as archive:
            names = archive.namelist()
            if set(names) != FILES or len(names) != len(FILES):
                raise DataError("The ZIP must contain exactly the five files listed in the data contract, without folders.")
            if sum(f.file_size for f in archive.infolist()) > MAX_BYTES:
                raise DataError("The uncompressed input bundle exceeds 10 MB.")
            content = {name: archive.read(name) for name in names}
        manifest = json.loads(content["manifest.json"])
        csv = {name: pd.read_csv(BytesIO(value)) for name, value in content.items() if name.endswith(".csv")}
    except (BadZipFile, UnicodeDecodeError, json.JSONDecodeError, pd.errors.ParserError, RuntimeError) as exc:
        raise DataError("The bundle is not a readable ZIP of UTF-8 CSV and JSON files.") from exc

    required = {"schema_version": 1, "return_currency": "GBP", "return_type": "monthly_simple_net_total",
                "factor_currency": "USD", "factor_region": "Developed", "units": "decimal",
                "fx_definition": "GBP per USD simple return"}
    if not isinstance(manifest, dict) or any(manifest.get(k) != v for k, v in required.items()):
        raise DataError("The manifest does not match the GBP developed-equity FF5 data contract.")
    sources = manifest.get("sources", {})
    if not isinstance(sources, dict) or any(not isinstance(sources.get(k), str) or not sources[k].strip()
                                          for k in ["funds", "returns", "factors", "cash", "fx"]):
        raise DataError("Document sources for funds, returns, factors, GBP cash and FX.")

    funds = csv["funds.csv"]
    columns = {"ETF_ID", "Name", "ISIN", "AssetClass", "Region", "Hedged", "TER", "ReturnKind", "Source"}
    if not columns.issubset(funds.columns) or funds.empty or len(funds) > 50:
        raise DataError("funds.csv needs 1–50 funds and all required identity/source columns.")
    if funds[list(columns)].isna().any().any() or funds.ETF_ID.duplicated().any():
        raise DataError("Fund identities and metadata must be complete and unique.")
    if not funds.AssetClass.eq("Equity").all() or not funds.Region.eq("Developed").all():
        raise DataError("This calibration path currently supports developed-equity funds only.")
    if not funds.Hedged.astype(str).str.lower().isin(["false", "0"]).all():
        raise DataError("Hedged share classes need a separate factor/hedge model.")
    if not funds.ReturnKind.isin(["actual_fund", "documented_index_proxy"]).all():
        raise DataError("Identify each series as actual_fund or documented_index_proxy. Undocumented splices are not accepted.")
    try:
        funds["TER"] = pd.to_numeric(funds["TER"], errors="raise")
    except (ValueError, TypeError) as exc:
        raise DataError("TER must be an annual decimal, for example 0.002 for 0.2%.") from exc
    if not np.isfinite(funds.TER).all() or not funds.TER.between(0, 0.05).all():
        raise DataError("TER must lie between 0 and 0.05; review fees outside this supported range.")
    funds = funds.set_index("ETF_ID")
    returns = monthly_frame(csv["returns.csv"], "Fund returns")
    factors = monthly_frame(csv["factors.csv"], "FF5 factors")
    cash_fx = monthly_frame(csv["cash_fx.csv"], "Cash and FX")
    if set(returns.columns) != set(funds.index) or len(returns) < 72:
        raise DataError("Provide matching fund IDs and at least 72 complete monthly returns.")
    if list(factors.columns) != FACTORS + ["RF"] or set(cash_fx.columns) != {"GBP_RF", "USD_GBP"}:
        raise DataError("Factor or cash/FX columns do not match the data contract.")
    if (returns <= -1).any().any() or (cash_fx <= -1).any().any():
        raise DataError("Simple invested returns must be greater than -1.")
    if ((factors["Mkt-RF"] + factors["RF"]) <= -1).any() or (factors["RF"] <= -1).any():
        raise DataError("Invalid market or risk-free gross returns.")
    if not returns.index.isin(factors.index).all() or factors.index[-1] != returns.index[-1]:
        raise DataError("Factors must cover every return month and end at the same information date.")
    converted = convert_factors_to_gbp(factors, cash_fx)
    if not np.isfinite(converted.to_numpy()).all():
        raise DataError("Currency conversion produced non-finite factors.")
    return ResearchData(funds, returns[funds.index], converted, cash_fx.GBP_RF, manifest, sha256(raw).hexdigest())
