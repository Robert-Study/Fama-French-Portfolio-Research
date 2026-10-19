"""Build the dated 68-asset planning calibration from pinned local fixtures.

This is an assumption-based forward model, not an empirical calibration.
The JSON carries every prior and per-instrument return component. Equity ERP,
factor risk, FX risk and residual risk are explicit modelling assumptions.
No historical NAV returns are used or charged fees again. Both snapshot routes
can consume these moments; this does not estimate a holdings-based model.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_market_snapshot import AS_OF_DATE, DEFAULT_FIXTURES, build_snapshot
from scripts.build_stress_and_benchmarks import build_catalogue

# These are planning priors, not observed market estimates. Loadings are annual
# return standard deviations on independent unit-variance factors. B @ B.T is
# PSD by construction and preserves shared-factor cross-covariances.
FACTORS = ('equity', 'rates', 'credit', 'commodity', 'fx', 'value', 'size',
           'momentum', 'quality', 'us', 'uk', 'europe', 'japan', 'asia', 'em')
REGIONS = {
    'global': 'VWRP SWDA IWDP IWFV IWFM IWFQ MVOL IWSZ WLDS JPGL GGRG AVCG AVSG ACWI VALL VSML HWWA IFSW VHVG XDEV',
    'us': 'VUSA EQQQ USSC IUVF', 'uk': 'VUKE VMID',
    'europe': 'VERX ZPRX IEFV VGER ISFR', 'japan': 'VJPN',
    'asia': 'VAPX VDPG', 'em': 'EMIM IIND IASH EMVL ICHN FRIN LTAM HIDR HCHA AVEG',
}
STYLE_GROUPS = {
    'value': 'IWFV USSC ZPRX IUVF IEFV EMVL JPGL AVCG AVSG XDEV HWWA IFSW AVEG',
    'size': 'IWSZ WLDS USSC ZPRX AVSG VSML',
    'momentum': 'IWFM JPGL HWWA IFSW',
    'quality': 'IWFQ JPGL GGRG AVCG HWWA IFSW AVEG',
}
STYLE_PREMIA = {'value': .005, 'size': .005, 'momentum': .005, 'quality': .0025}
COMMODITY_RISK = {'SGLN': (.12, .10), 'SSLN': (.20, .16),
                  'CMOP': (.12, .06), 'COPA': (.18, .14),
                  'AIGA': (.12, .12), 'CRUD': (.24, .22)}
UNDERLYINGS = {'XS2D': 'VUSA', 'LQQ': 'EQQQ', '3LUS': 'VUSA', '3QQQ': 'EQQQ'}


def _number(notes: str, pattern: str, ticker: str) -> float:
    match = re.search(pattern, notes, re.IGNORECASE)
    if match is None:
        raise ValueError(f'{ticker}: missing fixture yield/duration: {pattern}')
    return float(match.group(1))


def _assumption(text: str, *path: str) -> float:
    """Read a unique numeric scalar in the pinned indentation-only YAML subset.

    This is intentionally not a general YAML loader. No optional dependencies,
    aliases or executable constructors are accepted for these numeric inputs.
    """
    stack = []
    values = []
    for line in text.splitlines():
        match = re.fullmatch(r'( *)(\w+):\s*(.*)', line)
        if match is None:
            continue
        indent, key, value = len(match[1]), match[2], match[3]
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        if tuple(k for _, k in stack) == path:
            values.append(float(value))
    if len(values) != 1 or not np.isfinite(values[0]):
        raise ValueError(f'Expected one finite numeric assumption: {path}')
    return values[0]


def build_calibration(fixtures: Path = DEFAULT_FIXTURES) -> dict:
    fixtures = Path(fixtures)
    catalogue = build_catalogue(fixtures)
    with (fixtures / '01_verified_universe.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    contracts = json.loads((fixtures / '02_product_contracts.json').read_text(encoding='utf-8-sig'))['contracts']
    assumptions = (fixtures / '02_assumptions.yaml').read_text(encoding='utf-8-sig')
    tickers = [r['display_ticker'] for r in rows]
    if tickers != catalogue.ticker.tolist() or tickers[0] != 'T212_GBP_CASH':
        raise ValueError('Expected canonical fixture order with cash at index zero')
    def rate(name):
        return _assumption(assumptions, 'short_rates_and_financing', 'benchmarks', name, 'rate_pct') / 100
    inflation = _assumption(assumptions, 'inflation_assumptions', 'developed_market_long_run_inflation', 'default_pct') / 100
    cash_aer = .038  # User override of the fixture's 4.25% planning regime.
    risk_free = 12 * np.expm1(np.log1p(cash_aer) / 12)
    equity_erp = .04
    loadings = np.zeros((68, len(FACTORS)), dtype=np.float64)
    residual = np.zeros(68, dtype=np.float64)
    mu = np.zeros(68, dtype=np.float64)
    audit = {}
    regions = {t: r for r, names in REGIONS.items() for t in names.split()}

    def set_loading(i, name, value):
        loadings[i, FACTORS.index(name)] = value

    def equity(ticker):
        region = regions[ticker]  # Fail closed for an unmapped new instrument.
        beta = .75 if ticker == 'MVOL' else 1.0
        if ticker in ('EQQQ', 'IWDP'):
            beta = 1.15
        styles = {s: 1.0 for s, names in STYLE_GROUPS.items() if ticker in names.split()}
        if ticker in ('JPGL', 'HWWA', 'IFSW', 'AVCG', 'AVEG'):
            styles = {s: .5 for s in styles}
        gross = risk_free + equity_erp * beta + sum(STYLE_PREMIA[s] * b for s, b in styles.items())
        b = np.zeros(len(FACTORS), dtype=np.float64)
        b[FACTORS.index('equity')] = .14 * beta
        b[FACTORS.index('fx')] = 0 if region == 'uk' else .06
        if region != 'global':
            b[FACTORS.index(region)] = .08 if region == 'em' else .05
        for s, exposure in styles.items():
            b[FACTORS.index(s)] = .04 * exposure
        idio = .10 if region == 'em' or ticker in ('EQQQ', 'IWDP') else .06
        return gross, b, idio, styles

    for i, row in enumerate(rows):
        ticker, category = row['display_ticker'], row['asset_class']
        contract = contracts.get(row['canonical_id'], {})
        ocf = float(row['ocf_ter_pct']) / 100
        swap = float(contract.get('additional_swap_fee_pct', row['additional_swap_fee_pct'] or 0)) / 100
        components = {'ocf_ann': ocf, 'additional_swap_fee_ann': swap}
        if category == 'Cash':
            mu[i] = risk_free
            components['aer'] = cash_aer
        elif category == 'Bonds':
            notes = row['notes']
            ytm = _number(notes, r'YT[MW]\s+([\d.]+)%', ticker) / 100
            duration = _number(notes, r'(?:Eff|Avg) Dur\s+([\d.]+)y', ticker)
            real_yield = None
            if contract.get('inflation_linked'):
                real_yield = _number(notes, r'Real Yield\s+([\d.]+)%', ticker) / 100
                ytm = real_yield + inflation
            loss = float(contract['expected_credit_loss_pct']) / 100
            hedge = 0.0
            if contract['currency_hedging'] == 'GBP_HEDGED':
                # Basket currency weights are absent. SOFR is an explicit proxy
                # for foreign short rates in VAGS/GHYS, not a verified basket rate.
                hedge = rate('GBP_SONIA_OVERNIGHT') - rate('USD_SOFR_OVERNIGHT') - float(contract['funding_spread_pct']) / 100
            mu[i] = ytm - loss + hedge - ocf - swap
            set_loading(i, 'rates', duration * .01)
            credit_risk = {'SOVEREIGN_DM': 0., 'GLOBAL_AGG_IG': .01, 'IG_CORP': .025,
                           'EM_SOVEREIGN': .07, 'HY_CORP': .07}[contract['credit_loss_bucket']]
            set_loading(i, 'credit', credit_risk)
            set_loading(i, 'equity', credit_risk * .4)
            if contract['currency_hedging'] == 'UNHEDGED':
                set_loading(i, 'fx', .06)
            residual[i] = .01
            components.update(yield_before_costs_ann=ytm, real_yield_ann=real_yield,
                              duration_years=duration, credit_loss_ann=loss, hedge_carry_ann=hedge,
                              roll_down_ann=0.0)
        elif category == 'Commodities':
            physical = ticker in ('SGLN', 'SSLN')
            spot = inflation + _assumption(assumptions, 'commodity_priors', 'physical_precious_metals', 'expected_real_return_pct') / 100 if physical else 0.0
            roll = 0.0 if physical else _assumption(assumptions, 'commodity_priors', 'collateralised_futures', 'expected_futures_excess_return_pct') / 100
            # No forward curve or T-bill quote exists locally. Zero spot+roll
            # excess return and SOFR collateral proxy are explicit priors.
            collateral = 0.0 if physical else rate('USD_SOFR_OVERNIGHT')
            mu[i] = spot + roll + collateral - ocf - swap
            systematic, residual[i] = COMMODITY_RISK[ticker]
            set_loading(i, 'commodity', systematic)
            set_loading(i, 'fx', .06)
            components.update(spot_ann=spot, roll_ann=roll, collateral_ann=collateral)
        elif ticker in UNDERLYINGS:
            gross, b, idio, styles = equity(UNDERLYINGS[ticker])
            leverage = float(contract['leverage_factor'])
            borrowed = float(contract['borrowed_notional_multiple'])
            spread = float(contract.get('provisional_funding_spread_fallback_pct', contract['funding_spread_pct'])) / 100
            # Respect the residual audit's ACT/365 correction for WisdomTree.
            basis = 365 if ticker == '3LUS' else int(contract['day_count'].split('/')[1])
            funding = borrowed * (rate(contract['funding_benchmark']) + spread) * 365 / basis
            embedded = leverage * float(contract['embedded_underlying_fee_pct']) / 100
            mu[i] = leverage * gross - funding - ocf - swap - embedded
            loadings[i] = leverage * b
            loadings[i, FACTORS.index('fx')] = b[FACTORS.index('fx')]
            residual[i] = leverage * idio
            components.update(gross_underlying_ann=gross, leverage=leverage,
                              financing_ann=funding, financing_day_basis=basis,
                              embedded_underlying_cost_ann=embedded, factor_exposures=styles)
        elif category in ('ETFs', 'Factor-tilted ETFs'):
            gross, loadings[i], residual[i], styles = equity(ticker)
            mu[i] = gross - ocf - swap
            components.update(gross_underlying_ann=gross, factor_exposures=styles)
        else:
            raise ValueError(f'Unsupported instrument: {ticker} ({category})')
        components['net_arith_ann'] = float(mu[i])
        audit[ticker] = components

    # Independent residual priors are disclosed; there is no invented empirical
    # residual matrix or overlap surcharge. Shared factors supply cross-covariance.
    cov_ann = loadings @ loadings.T + np.diag(residual ** 2)
    cov_ann = (cov_ann + cov_ann.T) * .5
    cov_ann[0, :] = cov_ann[:, 0] = 0.0
    return {
        'as_of_date': AS_OF_DATE, 'source_as_of': AS_OF_DATE, 'method': 'etf',
        'reporting_currency': 'GBP', 'return_basis': 'net_total_return',
        'moment_basis': 'monthly_simple_decimal', 'calibration_status': 'assumption_based',
        'source': 'Pinned 2026-10-18 universe, product contracts and assumptions; explicit planning priors in scripts/build_market_calibration.py. Not an empirical or independently fitted holdings calibration.',
        'tickers': tickers, 'mu_monthly': (mu / 12).tolist(),
        'cov_monthly': (cov_ann / 12).tolist(), 'C_mat': (cov_ann / 60).tolist(),
        'U_mat': (1e-4 * np.diag(np.diag(cov_ann))).tolist(),
        'calibration_details': {
            'equity_erp_ann': equity_erp, 'equity_risk_free_ann': float(risk_free),
            'factor_premia_ann': STYLE_PREMIA, 'factor_names': FACTORS,
            'annual_factor_loadings': loadings.tolist(), 'annual_residual_volatility': residual.tolist(),
            'instruments': audit,
            'limitations': [
                'Factor exposures, volatilities and premia are planning priors; no return history was fitted.',
                'Zero FX drift, bond roll-down and inflation wedge; no return premium for country concentration.',
                'SOFR proxies unavailable T-bill collateral and foreign basket short rates.',
                'Physical metals earn no collateral; futures spot+roll is the zero excess-return prior.',
                'Daily leverage is a diffusion approximation, not pathwise reset or default simulation.',
                'Distribution yields are unavailable; snapshot preparation defaults to reinvested total returns.',
                'C=cov_ann/60 and U=1e-4*diag(diag(cov_ann)) are requested uncertainty conventions.',
                'Cash uses 3.80% AER, overriding the 4.25% fixture planning default.',
            ],
            'fixture_sha256': {name: sha256((fixtures / name).read_bytes()).hexdigest()
                               for name in ('01_verified_universe.csv', '02_product_contracts.json', '02_assumptions.yaml')},
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument('--out', type=Path, default=ROOT / 'data/release_inputs/market_calibration.json')
    args = parser.parse_args(argv)
    try:
        if args.out.exists():
            raise ValueError(f'Refusing to overwrite existing calibration: {args.out}')
        payload = build_calibration(args.fixtures)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.market-calibration-', dir=args.out.parent) as staging:
            path = Path(staging) / 'market_calibration.json'
            path.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n', encoding='utf-8')
            build_snapshot(args.fixtures, path)  # Validate the consumer contract before publishing.
            path.rename(args.out)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f'Market calibration blocked: {exc}', file=sys.stderr)
        return 2
    print(f'Built assumption-based calibration: {len(payload["tickers"])} tickers, as_of: {AS_OF_DATE}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
