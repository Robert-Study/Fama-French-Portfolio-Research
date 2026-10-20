"""Deterministic V8 Schema & Mathematical Contract Gate (Stage 01, Stage 02, Stage 04).

Validates:
1. Zero Google Docs backslash escaping or delimiter drift across all V8 fixtures.
2. Synchronization between local `tests/fixtures/` and `G:\\My Drive\\AI-File-Exchange` (when mounted).
3. `01_verified_universe.csv` and `01_listings.csv` completeness, fee bounds, and quote unit locks.
4. `02_product_contracts.json` and `02_assumptions.yaml` structural and unit invariants (zero external deps).
5. `04_validation_cases.json` closed-form mathematical verification within 1e-8 tolerance.
"""

from __future__ import annotations

import ast
import csv
import json
from pathlib import Path
import re
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DRIVE_V8_ROOT = Path(
    r"G:\My Drive\AI-File-Exchange\03 Portfolio Deliverables\V8.0 - Portfolio Construction Lab"
)

FORBIDDEN_ESCAPE_PATTERNS = (
    r"\\_",
    r"\\\[",
    r"\\\]",
    r"\\&",
    r"\\\+",
    r"\\<=",
    r"=== BEGIN FILE",
    r"=== END FILE",
)


def _parse_yaml_scalar(val_str: str) -> Any:
    """Parse a simple YAML scalar or inline list using stdlib only."""
    val_str = val_str.strip()
    if val_str in ("true", "True"):
        return True
    if val_str in ("false", "False"):
        return False
    if val_str in ("null", "None", "~"):
        return None
    if (val_str.startswith('"') and val_str.endswith('"')) or (
        val_str.startswith("'") and val_str.endswith("'")
    ):
        return val_str[1:-1]
    if val_str.startswith("[") and val_str.endswith("]"):
        return ast.literal_eval(val_str)
    try:
        if "." in val_str or "e" in val_str.lower():
            return float(val_str)
        return int(val_str)
    except ValueError:
        return val_str


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Deterministic zero-dependency parser for 02_assumptions.yaml."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        assert indent % 2 == 0, f"Invalid YAML indentation ({indent} spaces): {raw_line!r}"
        stripped = raw_line.strip()

        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]

        if stripped.startswith("- "):
            item_val = _parse_yaml_scalar(stripped[2:])
            assert isinstance(parent, list), f"Unexpected list item under dict: {raw_line!r}"
            parent.append(item_val)
        else:
            key, sep, rest = stripped.partition(":")
            assert sep == ":", f"Malformed YAML line: {raw_line!r}"
            key = key.strip()
            rest = rest.strip()
            if not rest:
                # Peek ahead encoded lazily: create dict, convert to list if first child is '- '
                node: dict[str, Any] = {}
                parent[key] = node
                stack.append((indent, node))
            else:
                parent[key] = _parse_yaml_scalar(rest)
        # Convert empty dict on stack to list if current line is '- '
        if len(stack) >= 2 and stripped.startswith("- ") and isinstance(stack[-1][1], list):
            pass

    return root


def _load_assumptions_yaml(path: Path) -> dict[str, Any]:
    """Parse 02_assumptions.yaml handling block lists cleanly with stdlib only."""
    lines = [
        ln for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    for idx, raw_line in enumerate(lines):
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        assert indent % 2 == 0, f"Invalid YAML indentation ({indent} spaces): {raw_line!r}"
        stripped = raw_line.strip()

        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]

        if stripped.startswith("- "):
            assert isinstance(parent, list), f"Expected list container for {raw_line!r}"
            parent.append(_parse_yaml_scalar(stripped[2:]))
        else:
            key, sep, rest = stripped.partition(":")
            assert sep == ":", f"Malformed YAML line: {raw_line!r}"
            key = key.strip()
            rest = rest.strip()
            if not rest:
                next_is_list = (
                    idx + 1 < len(lines)
                    and (len(lines[idx + 1]) - len(lines[idx + 1].lstrip(" "))) > indent
                    and lines[idx + 1].strip().startswith("- ")
                )
                container: Any = [] if next_is_list else {}
                parent[key] = container
                stack.append((indent, container))
            else:
                parent[key] = _parse_yaml_scalar(rest)

    return root


def test_no_markdown_escape_or_delimiter_drift() -> None:
    """Ensure cloud LLM exports contain zero Google Docs backslash escapes or file markers."""
    fixture_files = (
        "01_verified_universe.csv",
        "01_listings.csv",
        "02_product_contracts.json",
        "02_assumptions.yaml",
        "04_validation_cases.json",
    )
    for fname in fixture_files:
        fpath = FIXTURES_DIR / fname
        assert fpath.is_file(), f"Missing required V8 fixture: {fpath}"
        raw = fpath.read_text(encoding="utf-8")
        for pat in FORBIDDEN_ESCAPE_PATTERNS:
            assert not re.search(pat, raw), f"Forbidden escape/marker {pat!r} found in {fname}"


def test_drive_exchange_fixture_sync() -> None:
    """When Google Drive is mounted locally, verify byte parity between Drive and local fixtures."""
    if not DRIVE_V8_ROOT.exists():
        return
    mapping = {
        "01_verified_universe.csv": DRIVE_V8_ROOT / "01 Resources" / "01_verified_universe.csv",
        "01_listings.csv": DRIVE_V8_ROOT / "01 Resources" / "01_listings.csv",
        "02_product_contracts.json": DRIVE_V8_ROOT / "01 Resources" / "02_product_contracts.json",
        "02_assumptions.yaml": DRIVE_V8_ROOT / "01 Resources" / "02_assumptions.yaml",
        "04_validation_cases.json": DRIVE_V8_ROOT / "00 Specifications" / "04_validation_cases.json",
    }
    for local_name, drive_path in mapping.items():
        assert drive_path.is_file(), f"Missing canonical Drive file: {drive_path}"
        local_text = (FIXTURES_DIR / local_name).read_text(encoding="utf-8").strip()
        drive_text = drive_path.read_text(encoding="utf-8").strip()
        assert local_text == drive_text, f"Fixture drift between local {local_name} and {drive_path}"


def test_stage01_verified_universe_and_listings_schema() -> None:
    """Validate all 68 rows of 01_verified_universe.csv and 84 rows of 01_listings.csv."""
    with (FIXTURES_DIR / "01_verified_universe.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 68, f"Expected 68 universe rows, got {len(rows)}"

    by_ticker = {}
    for row in rows:
        cid = row["canonical_id"]
        assert cid, "Empty canonical_id in universe"
        assert row["verification_status"] == "verified_current", f"Unverified row: {cid}"
        assert "verify" not in row["verification_status"].lower()

        ocf = float(row["ocf_ter_pct"])
        # Percentage points check: must be between 0.0% and 2.0% (not decimal 0.0007 or >2%)
        assert 0.0 <= ocf <= 2.0, f"Out-of-bounds ocf_ter_pct={ocf} for {cid}"
        if row["canonical_id"] != "cash:T212_GBP_CASH":
            assert ocf >= 0.03, f"Suspiciously small OCF (decimal vs pct mismatch?) for {cid}: {ocf}"

        pref_ticker = row["preferred_listing_ticker"] or row["display_ticker"]
        by_ticker[pref_ticker] = row

    # Spot-check critical quote unit locks (GBP decimal vs GBx pence)
    expected_gbp = (
        "VWRP", "VUSA", "VUKE", "VMID", "VERX", "VJPN", "VAPX",
        "IGLS", "IGLT", "IBTS", "IBTM", "GHYS", "VAGS", "VEMT",
    )
    expected_gbx = (
        "SWDA", "EQQQ", "SGLN", "SSLN", "CMOP", "COPB",
        "AGAP", "CRUP", "IBTL", "3LUS", "3QQQ", "IWFV",
        "IWDP", "ISFR",
    )
    for t in expected_gbp:
        assert by_ticker[t]["quote_unit"] == "GBP", f"Expected GBP quote unit for {t}"
    for t in expected_gbx:
        assert by_ticker[t]["quote_unit"] == "GBx", f"Expected GBx quote unit for {t}"

    with (FIXTURES_DIR / "01_listings.csv").open(encoding="utf-8", newline="") as f:
        listings = list(csv.DictReader(f))
    assert len(listings) == 84, f"Expected 84 listing rows, got {len(listings)}"
    for lrow in listings:
        assert lrow["quote_unit"] in {"GBP", "GBx", "USD", "EUR"}


def test_stage02_product_contracts_and_assumptions() -> None:
    """Validate 02_product_contracts.json and 02_assumptions.yaml schema and unit locks."""
    contracts_doc = json.loads((FIXTURES_DIR / "02_product_contracts.json").read_text(encoding="utf-8"))
    assert contracts_doc["schema_version"] == "V8.0.0"
    assert contracts_doc["reporting_currency"] == "GBP"
    contracts = contracts_doc["contracts"]
    assert len(contracts) == 24

    for cid, c in contracts.items():
        assert c["canonical_id"] == cid
        qu = c["quote_unit"]
        conv = c["quote_unit_conversion"]
        if qu == "GBx":
            assert conv == 0.01, f"{cid} has quote_unit=GBx but quote_unit_conversion={conv}"
        elif qu in {"GBP", "USD", "EUR"}:
            assert conv == 1.0, f"{cid} has quote_unit={qu} but quote_unit_conversion={conv}"
        else:
            raise AssertionError(f"Unexpected quote_unit={qu} for {cid}")

        if c["asset_class"] == "Leveraged Equity":
            lev = float(c["leverage_factor"])
            borrowed = float(c["borrowed_notional_multiple"])
            assert abs(borrowed - (lev - 1.0)) < 1e-12, f"Invalid borrowed_notional_multiple for {cid}"

    # Verify Stream C bond & commodity audit locks
    assert contracts["IE00B14X4S71"]["quote_unit"] == "GBP"  # IBTS
    assert contracts["IE00B1FZS798"]["quote_unit"] == "GBP"  # IBTM
    assert contracts["IE00BSKRJZ44"]["quote_unit"] == "GBx"  # IBTL
    assert abs(contracts["IE00B8KQFS66"]["published_ytm_pct"] - 7.46) < 1e-9  # GHYS
    assert abs(contracts["cash:T212_GBP_CASH"]["observed_oct_2026_aer_pct"] - 3.80) < 1e-9
    assert contracts["IE00B8KQFS66"]["hedge_inclusion_status"] == "excluded_native_basket_yield_only"
    assert contracts["IE00BG47K971"]["hedge_inclusion_status"] == "excluded_native_basket_yield_only"

    assumptions = _load_assumptions_yaml(FIXTURES_DIR / "02_assumptions.yaml")
    assert assumptions["schema_version"] == "V8.0.0"
    assert assumptions["reporting_currency"] == "GBP"
    benchmarks = assumptions["short_rates_and_financing"]["benchmarks"]
    for bkey in ("USD_SOFR_OVERNIGHT", "USD_FED_FUNDS_EFFECTIVE", "EUR_ESTR_OVERNIGHT", "GBP_SONIA_OVERNIGHT"):
        assert 0.0 < float(benchmarks[bkey]["rate_pct"]) < 15.0
    gates = assumptions["optimisation_and_precision_gates"]
    assert gates["weight_basis_points_total"] == 10000
    assert gates["min_nonzero_position_bps"] == 10
    assert gates["frontier_target_points"] == 1001


def test_stage04_validation_cases_mathematical_consistency() -> None:
    """Verify all 5 deterministic validation vectors in 04_validation_cases.json within 1e-8."""
    doc = json.loads((FIXTURES_DIR / "04_validation_cases.json").read_text(encoding="utf-8"))
    assert doc["schema_version"] == "V8.0.0"
    tol = float(doc["float_tolerance_abs"])
    assert tol == 1e-8
    cases = doc["validation_cases"]

    # Case 1: Leveraged 2-day oscillation
    c1 = cases["case_leverage_two_day_oscillation"]
    r1, r2 = c1["inputs"]["r_u_day1"], c1["inputs"]["r_u_day2"]
    basis = c1["inputs"]["day_count_basis"]
    days = c1["inputs"]["calendar_days_per_step"]
    for param_key, out_key in (
        ("xs2d_params", "xs2d_post_cost"),
        ("three_lus_params", "three_lus_post_cost"),
        ("three_qqq_net_underlying_params", "three_qqq_net_underlying_post_cost"),
        ("three_qqq_gross_underlying_params", "three_qqq_gross_underlying_post_cost"),
    ):
        p = c1["inputs"][param_key]
        out = c1["expected_outputs"][out_key]
        under_mult = p["L"] if p["is_gross_underlying"] else 0.0
        drag = (
            p["B"] * (p["funding_rate"] + p["funding_spread"])
            + p["wrapper_fee"]
            + under_mult * p["embedded_fee"]
        ) * (days / basis)
        d1 = p["L"] * r1 - drag
        d2 = p["L"] * r2 - drag
        w2 = (1.0 + d1) * (1.0 + d2)
        assert abs(drag - out["daily_total_drag"]) <= tol
        assert abs(d1 - out["day1_return"]) <= tol
        assert abs(d2 - out["day2_return"]) <= tol
        assert abs(w2 - out["two_day_wealth_ratio"]) <= tol
        assert abs((w2 - 1.0) - out["two_day_cumulative_return"]) <= tol

    # Case 2: Zero-NAV absorption vs intraday airbag restrike
    c2 = cases["case_zero_nav_absorption"]
    nav0 = c2["inputs"]["initial_nav"]
    lev = c2["inputs"]["leverage_factor"]
    drop_close = c2["inputs"]["day1_underlying_close_return"]
    bounce = c2["inputs"]["day2_underlying_close_return"]
    trig = c2["inputs"]["airbag_trigger_drop"]
    unbuf = c2["expected_outputs"]["unbuffered_no_restrike"]
    assert abs(max(-1.0, lev * drop_close) - unbuf["day1_floored_return"]) <= tol
    assert abs(0.0 - unbuf["day2_closing_nav_after_plus_50pct"]) <= tol

    airbag = c2["expected_outputs"]["single_intraday_airbag_restrike_at_16_67pct"]
    nav_trig = nav0 * (1.0 - lev * trig)
    rem_u = (1.0 + drop_close) / (1.0 - trig) - 1.0
    nav_close1 = nav_trig * (1.0 + lev * rem_u)
    nav_close2 = nav_close1 * (1.0 + lev * bounce)
    assert abs(nav_trig - airbag["intraday_nav_at_trigger"]) <= tol
    assert abs(rem_u - airbag["remaining_underlying_return_from_trigger_to_close"]) <= tol
    assert abs(nav_close1 - airbag["day1_closing_nav"]) <= tol
    assert abs(nav_close2 - airbag["day2_closing_nav_after_plus_50pct"]) <= tol

    # Case 4: GBx normalisation & single FX conversion on 3x product
    c4 = cases["case_gbx_and_fx_conversion"]
    inp4 = c4["inputs"]
    out4 = c4["expected_outputs"]
    gbp0 = inp4["gbx_price_t0"] * 0.01
    gbp1 = inp4["gbx_price_t1"] * 0.01
    fx_ret = inp4["gbp_per_usd_spot_t1"] / inp4["gbp_per_usd_spot_t0"] - 1.0
    usd_3x_ret = (
        inp4["leverage_factor"] * inp4["native_usd_underlying_return"]
        - inp4["native_usd_daily_financing_and_fee_drag"]
    )
    gbp_3x_ret = (1.0 + usd_3x_ret) * (1.0 + fx_ret) - 1.0
    assert abs(gbp0 - out4["gbp_price_t0"]) <= tol
    assert abs(gbp1 - out4["gbp_price_t1"]) <= tol
    assert abs(usd_3x_ret - out4["native_usd_3x_product_return"]) <= tol
    assert abs(gbp_3x_ret - out4["correct_gbp_3x_product_return"]) <= tol

    # Case 5: MIQP minimum position gate (10 bps)
    c5 = cases["case_miqp_minimum_position"]
    out5 = c5["expected_outputs"]
    bps = out5["optimal_miqp_integer_bps"]
    assert sum(bps) == 10000
    assert all(q == 0 or q >= 10 for q in bps)
