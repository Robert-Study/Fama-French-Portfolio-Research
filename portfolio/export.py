from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pandas as pd

from portfolio import __version__
from portfolio.projection import buy_and_hold_projection
from portfolio.risk import portfolio_metrics


def export_tables(run, point, investment=None):
    ids = run.funds.index
    weights = run.frontier.weights[point]
    _, _, risk = portfolio_metrics(weights, run.mean, run.covariance)
    portfolio = run.funds[["Name", "TER"]].copy()
    portfolio["Weight"] = weights
    portfolio["Annual volatility contribution"] = risk * np.sqrt(12)
    frontier = pd.DataFrame(run.frontier.weights, columns=ids)
    frontier.insert(0, "Point", np.arange(len(frontier)))
    frontier["Annualised arithmetic return"] = run.frontier.returns * 12
    frontier["Annualised monthly volatility"] = run.frontier.volatilities * np.sqrt(12)
    metadata = {"version": __version__, "run_id": run.run_id, "created_utc": run.created, "mode": run.mode,
                "data_sha256": run.fingerprint, "selected_point": point, "settings": run.settings,
                "solver_max_constraint_violation": run.frontier.max_violation,
                "solvers": sorted(set(run.frontier.solvers)),
                "limitations": "Conditional estimates; input source claims are not independently verified. No holdings-characteristic calibration."}
    tables = {"Portfolio": portfolio, "Frontier": frontier, "ETFs": run.etfs,
              "Monthly covariance": pd.DataFrame(run.covariance, index=ids, columns=ids),
              "Diagnostics": run.diagnostics}
    if investment is not None:
        metadata["projection"] = {"initial_gbp": investment, "years": 20, "rebalancing": "none",
                                  "assumption": "IID monthly vectors, constant moments; approximate lognormal quantiles"}
        tables["Wealth illustration"] = buy_and_hold_projection(weights, run.mean, run.covariance, investment)
    return metadata, tables


def workbook_bytes(run, point, investment=None):
    metadata, tables = export_tables(run, point, investment)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame({"Item": metadata.keys(), "Value": [json.dumps(v, ensure_ascii=False) for v in metadata.values()]}).to_excel(
            writer, sheet_name="Run and assumptions", index=False)
        for name, frame in tables.items():
            frame.to_excel(writer, sheet_name=name)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "B2"
            sheet.auto_filter.ref = sheet.dimensions
            for row in sheet:
                for cell in row:
                    if isinstance(cell.value, str):
                        cell.data_type = "s"
            for column in sheet.columns:
                letter = column[0].column_letter
                sheet.column_dimensions[letter].width = min(55, max(14, max(len(str(c.value or "")) for c in column) + 2))
    return output.getvalue()


def diagnostic_bytes(run, point, investment=None):
    metadata, tables = export_tables(run, point, investment)
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("run.json", json.dumps(metadata, indent=2, allow_nan=False))
        for name, frame in tables.items():
            safe = frame.copy()
            def text_cell(value):
                return "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
            safe = safe.map(text_cell)
            safe.index = safe.index.map(text_cell)
            safe.columns = safe.columns.map(text_cell)
            archive.writestr(name.lower().replace(" ", "_") + ".csv", safe.to_csv())
    return output.getvalue()
