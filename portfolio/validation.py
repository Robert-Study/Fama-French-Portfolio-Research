"""Admission is computed from evidence, never from a catalogue flag alone."""
from datetime import date
import numpy as np
import pandas as pd

CATEGORIES = ['Instant-access savings / cash', 'Commodities', 'Bonds', 'ETFs', 'Factor-tilted ETFs', 'Leveraged ETFs / ETPs']
COLOURS = ['#64748b', '#d99a28', '#397cbd', '#198577', '#8b5fc0', '#e77567']
EQUITY_CATEGORIES = CATEGORIES[3:]
BENCHMARKS = {'All-world': {'VWRP': 1.0}, '2× US equities': {'XS2D': 1.0},
              'Bonds': {'VAGS': 1.0}, 'Savings / cash': {'GBP_BANK_SAVINGS': 1.0},
              'Global 60/40': {'VWRP': .6, 'VAGS': .4}}
REGIONS = {'VWRP': ['Developed', 'Emerging'], 'VUSA': ['US'], 'EQQQ': ['US'],
           'VUKE': ['Europe'], 'VMID': ['Europe'], 'VERX': ['Europe'], 'VJPN': ['Japan'],
           'VAPX': ['Asia_Pacific_ex_Japan'], 'EMIM': ['Emerging'], 'IIND': ['Emerging'],
           'IASH': ['Emerging'], 'USSC': ['US'], 'ZPRX': ['Europe'], 'IUVF': ['US'],
           'IEFV': ['Europe'], 'EMVL': ['Emerging']}


def age_days(value, today=None):
    today = date.today() if today is None else today
    try:
        parsed = date.fromisoformat(str(value)[:10])
        days = (today - parsed).days
    except (ValueError, TypeError):
        return 10**9
    return days if days >= 0 else 10**9


def admission(row, evidence, returns, source_ids, today=None, provisional=False):
    reasons = []
    category = row.category
    cash = category == CATEGORIES[0]
    required = ['legal_structure', 'currency', 'price_unit', 'inception', 'hedge', 'fee', 'fee_source', 'identity_source']
    if not cash:
        for field in required:
            if field not in evidence or evidence[field] in ('', None):
                reasons.append('Missing ' + field)
        for field in ('fee_source', 'identity_source'):
            if evidence.get(field) not in source_ids:
                reasons.append('Unverified source: ' + field)
        fee = evidence.get('fee')
        if not isinstance(fee, (int, float)) or not np.isfinite(fee) or not 0 <= fee <= .1:
            reasons.append('Unknown/invalid ongoing charge')
        native_proxy = provisional and evidence.get('provisional_native_risk') is True and evidence.get('currency') == 'USD'
        if not native_proxy and (evidence.get('currency') != 'GBP' or evidence.get('price_unit') not in ('GBP', 'GBX')):
            reasons.append('Normalised GBP total-return evidence required')
        if row.ticker not in returns:
            reasons.append('Actual net total-return history unavailable')
        else:
            history = returns[row.ticker].dropna()
            needed = 72 if category in CATEGORIES[3:5] else 36
            if len(history) < needed:
                reasons.append(f'Need {needed} compatible actual monthly observations')
            if not history.empty:
                if not history.index.equals(pd.period_range(history.index[0], history.index[-1], freq='M')):
                    reasons.append('Interior history gaps')
                if age_days(history.index[-1].end_time.date().isoformat(), today) > 90:
                    reasons.append('Return month older than 90 days')
                try:
                    # A partial inception month is not a complete monthly total return.
                    inception = pd.Period(evidence.get('inception'), freq='M')
                    if history.index[0] <= inception:
                        reasons.append('Pre-inception/partial-inception-month actual observations')
                except (ValueError, TypeError):
                    reasons.append('Unknown inception')
            if evidence.get('return_source') not in source_ids or evidence.get('return_type') != 'actual_share_class_net_total':
                reasons.append('Unreconciled total-return provenance')
            provisional_index = provisional and evidence.get('reconciliation_status') == 'issuer_total_return_index_provisional' and bool(evidence.get('reconciliation_warning'))
            if evidence.get('distribution_split_reconciled') is not True and not provisional_index:
                reasons.append('Distribution/split reconciliation missing')
    else:
        bank = row.model == 'variable_rate_bank_savings'
        if bank:
            required_terms = {'facility_type': 'uk_bank_deposit', 'instant_access': True,
                              'unlimited_withdrawals': True, 'introductory_bonus': False,
                              'linked_current_account_required': False}
            if any(evidence.get(k) != v for k, v in required_terms.items()):
                reasons.append('Standard UK bank instant-access/no-bonus terms not verified')
            if not evidence.get('provider') or not evidence.get('eligibility') or evidence.get('rate_source') not in source_ids:
                reasons.append('Public bank/provider/rate/eligibility evidence unavailable')
        elif evidence.get('account_type') != 'Invest' or evidence.get('applicable_to_account') is not True:
            reasons.append('Applicable Invest account cash rate/terms not confirmed')
        if age_days(evidence.get('quote_date'), today) > 30:
            reasons.append('Cash quote missing or older than 30 days')
        if not isinstance(evidence.get('aer'), (int, float)) or not np.isfinite(evidence.get('aer', np.nan)) or evidence.get('aer', -2) <= -1:
            reasons.append('Applicable cash AER missing')
        if evidence.get('terms_source') not in source_ids:
            reasons.append('Cash facility terms evidence unavailable')
    if category == 'Bonds':
        assumed_carry = provisional and evidence.get('forecast_policy') == 'cash_plus_zero_term_premium'
        if assumed_carry:
            if evidence.get('forecast_source') not in source_ids or age_days(evidence.get('forecast_assumption_date'), today) > 90 or not np.isfinite(evidence.get('term_premium_annual', np.nan)):
                reasons.append('Dated, sourced provisional bond carry prior required')
        for field in ([] if assumed_carry else ['yield', 'yield_kind', 'duration', 'bond_date', 'bond_source']):
            if field not in evidence:
                reasons.append('Missing bond ' + field)
        if not assumed_carry and (age_days(evidence.get('bond_date'), today) > 90 or evidence.get('bond_source') not in source_ids):
            reasons.append('Stale/unverified bond characteristics')
        if 'credit' in row.model and ('expected_loss' not in evidence or 'spread_duration' not in evidence):
            reasons.append('Credit loss/spread evidence missing')
        if 'inflation' in row.model and (evidence.get('yield_kind') != 'real' or 'inflation' not in evidence):
            reasons.append('Explicit real yield and inflation assumption required')
        if 'hedged' in row.model and evidence.get('hedge_reconciled') is not True:
            reasons.append('Hedge costs/history not reconciled')
    if row.model == 'commodity_futures' and evidence.get('roll_collateral_reconciled') is not True:
        reasons.append('Futures index variant/roll/collateral evidence missing')
    if category == CATEGORIES[-1]:
        for field in ['terms', 'terms_source', 'underlying', 'funding', 'daily_source', 'actual_daily_column', 'overlap_tolerance', 'annual_financing']:
            if field not in evidence:
                reasons.append('Missing leverage ' + field)
        if evidence.get('terms_source') not in source_ids or evidence.get('daily_source') not in source_ids:
            reasons.append('Issuer reset/funding/termination evidence unavailable')
        if evidence.get('intraday_evidence_required', True):
            reasons.append('Intraday reset/barrier evidence gate unresolved')
    return list(dict.fromkeys(reasons))


def check_covariance(covariance):
    c = np.asarray(covariance, float)
    if c.ndim != 2 or c.shape[0] != c.shape[1] or not np.isfinite(c).all() or not np.allclose(c, c.T, atol=1e-12) or np.linalg.eigvalsh(c).min() < -1e-10:
        raise ValueError('Covariance must be finite, symmetric and positive semidefinite.')
