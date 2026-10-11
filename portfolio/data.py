from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json

import numpy as np
import pandas as pd


class DataError(ValueError):
    pass


@dataclass
class LegacyData:
    funds: pd.DataFrame
    returns: pd.DataFrame
    holdings: pd.DataFrame
    securities: pd.DataFrame
    inventory: pd.DataFrame
    fingerprint: str


def monthly_frame(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    if "Month" not in frame or frame.empty:
        raise DataError(f"{label}: provide a Month column and monthly observations.")
    try:
        dates = pd.to_datetime(frame["Month"], errors="raise")
        months = pd.PeriodIndex(dates, freq="M")
        values = frame.drop(columns="Month").apply(pd.to_numeric, errors="raise")
    except (ValueError, TypeError) as exc:
        raise DataError(f"{label}: invalid dates or non-numeric observations.") from exc
    if months.hasnans or months.has_duplicates or not months.is_monotonic_increasing:
        raise DataError(f"{label}: months must be unique and increasing.")
    if not months.equals(pd.period_range(months[0], months[-1], freq="M")):
        raise DataError(f"{label}: missing months; do not fill gaps with zero returns.")
    if values.empty or not np.isfinite(values.to_numpy()).all():
        raise DataError(f"{label}: missing or non-finite values.")
    values.index = months
    values.index.name = "Month"
    return values.astype(float)


def legacy_fingerprint(folder: Path) -> str:
    digest = sha256()
    for path in sorted(folder.glob("*")):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def load_legacy(folder: Path) -> LegacyData:
    manifest = json.loads((folder / "source_manifest.json").read_text())
    for record in manifest:
        path = folder / record["file"]
        if path.parent != folder or not path.is_file():
            raise DataError("The V5 manifest refers to a missing or invalid file.")
        raw = path.read_bytes()
        if len(raw) != record["bytes"] or sha256(raw).hexdigest() != record["sha256"]:
            raise DataError(f"{path.name}: the original V5 checksum does not match.")

    funds = pd.read_csv(folder / "fund_master.csv").set_index("ETF_ID")
    returns = monthly_frame(pd.read_csv(folder / "monthly_returns.csv"), "V5 returns")
    holdings = pd.read_csv(folder / "holdings.csv")
    securities = pd.read_csv(folder / "securities.csv").set_index("HOLDING_ID")
    if funds.index.has_duplicates or securities.index.has_duplicates:
        raise DataError("Duplicate fund or security keys in the V5 files.")
    if set(returns.columns) != set(funds.index) or (returns <= -1).any().any():
        raise DataError("V5 return identities or simple-return bounds are invalid.")
    if not holdings["HOLDING_ID"].isin(securities.index).all():
        raise DataError("Some V5 holdings have no security record.")
    if not holdings["ETF_ID"].isin(funds.index).all():
        raise DataError("Some V5 holdings have no fund record.")
    if not np.isfinite(holdings["Weight"]).all():
        raise DataError("V5 holdings include missing weights.")
    inventory = pd.DataFrame(manifest)
    inventory["status"] = "LEGACY / UNVERIFIED"
    inventory["checksum_matches"] = True
    return LegacyData(funds, returns, holdings, securities, inventory, legacy_fingerprint(folder))
