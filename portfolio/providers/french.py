"""Published French ZIP parsing. RF is retained; percentage conversion occurs once."""
from io import BytesIO
import re
from zipfile import ZipFile

import numpy as np
import pandas as pd

from portfolio.bundle import FACTORS, convert_factors_to_gbp
from portfolio.data import DataError

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {
    "US": "F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "Developed": "Developed_5_Factors_CSV.zip",
    "North_America": "North_America_5_Factors_CSV.zip",
    "Europe": "Europe_5_Factors_CSV.zip",
    "Japan": "Japan_5_Factors_CSV.zip",
    "Asia_Pacific_ex_Japan": "Asia_Pacific_ex_Japan_5_Factors_CSV.zip",
    "Emerging": "Emerging_5_Factors_CSV.zip",
}
MOM_FILES = {"US": "F-F_Momentum_Factor_CSV.zip", "Developed": "Developed_Mom_Factor_CSV.zip"}


def parse_french(raw: bytes, region: str, momentum=False) -> pd.DataFrame:
    """Parse only the first monthly table; never interpret annual/daily rows as months."""
    with ZipFile(BytesIO(raw)) as z:
        names = [n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(names) != 1 or z.getinfo(names[0]).file_size > 20_000_000:
            raise DataError("Expected one bounded French CSV.")
        lines = z.read(names[0]).decode('utf-8-sig').splitlines()
    columns = ["MOM"] if momentum else FACTORS + ["RF"]
    rows, dates, started = [], [], False
    for line in lines:
        parts = [v.strip() for v in line.split(',')]
        if re.fullmatch(r'\d{6}', parts[0]):
            started = True
            if len(parts) != len(columns) + 1:
                raise DataError("Unexpected monthly French column count.")
            try:
                values = np.asarray(parts[1:], dtype=float)
                date = pd.Period(parts[0][:4] + '-' + parts[0][4:], freq='M')
            except ValueError as exc:
                raise DataError("Invalid French observation.") from exc
            # Early EM -99.99/-999 rows are unavailable, not extremely negative returns.
            if not np.isfinite(values).all() or np.isin(values, [-99.99, -999, -999.99]).any():
                continue
            dates.append(date)
            rows.append(values / 100)
        elif started:
            break
    frame = pd.DataFrame(rows, index=pd.PeriodIndex(dates, freq='M', name='Month'), columns=columns)
    if frame.empty or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise DataError("No unique ordered monthly French observations.")
    if not frame.index.equals(pd.period_range(frame.index[0], frame.index[-1], freq='M')):
        raise DataError("Interior missing-factor months; select a complete factor window explicitly.")
    frame.attrs.update(region=region, currency='USD', units='decimal', published_RF_preserved=True)
    return frame


def regional_gbp(panels: dict, cash_fx: pd.DataFrame) -> pd.DataFrame:
    """Keep regional identifiers rather than summing coefficients across distinct bases."""
    converted = []
    common = cash_fx.index
    for panel in panels.values():
        common = common.intersection(panel.index)
    if common.empty:
        raise DataError("No common verified factor/SONIA/FX period.")
    for region, panel in panels.items():
        result = convert_factors_to_gbp(panel.loc[common], cash_fx.loc[common])
        if 'MOM' in panel:
            result['MOM'] = panel.loc[common, 'MOM'] * (1 + cash_fx.loc[common, 'USD_GBP'])
        converted.append(result.rename(columns=lambda c: region + ':' + c))
    return pd.concat(converted, axis=1)
