"""Verify a standard UK bank savings quote from its official summary box."""
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import json
import re
from portfolio.data import DataError
from portfolio.providers.cache import fetch

URL = 'https://www.htb.co.uk/personal-savings/variable-rate-accounts/'
CHARTER_URL = 'https://www.chartersavingsbank.co.uk/Products/EasyAccess'


class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = False

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def parse_htb(raw, quote_date):
    parser = Text(); parser.feed(raw.decode('utf-8'))
    text = ' '.join(parser.parts)
    match = re.search(r'Easy Access Online Saver \(Issue (\d+)\).*?AER\s+([\d.]+)\s*%.*?Min investment\s+£\s*([\d,]+).*?Max investment\s+£\s*([\d,]+)', text)
    if match is None:
        raise DataError('Official HTB summary-box schema changed; retain last verified quote.')
    start = match.start()
    # Limit parsing to the selected account; never confuse notice/ISA rates.
    end = text.find('95 Day Online Notice', start)
    if end < 0:
        raise DataError('Cannot delimit the easy-access product summary.')
    summary = text[start:end]
    required = ['Unlimited withdrawals', 'managed variable rate', 'permanent resident of the United Kingdom',
                'minimum balance', 'nominated bank account', 'Financial Services Compensation Scheme']
    if any(term not in summary for term in required) or 'bonus' in summary.lower():
        raise DataError('Standard no-bonus bank savings terms require review.')
    return {'provider':'Hampshire Trust Bank', 'product':f'Easy Access Online Saver (Issue {match[1]})',
            'facility_type':'uk_bank_deposit', 'aer':float(match[2])/100, 'quote_date':quote_date,
            'minimum_balance':float(match[3].replace(',','')), 'maximum_balance':float(match[4].replace(',','')),
            'instant_access':True, 'unlimited_withdrawals':True, 'introductory_bonus':False,
            'linked_current_account_required':False, 'nominated_transfer_account_required':True,
            'eligibility':'UK permanent residents aged 18+, no overseas tax reporting for this account; email/mobile and nominated UK bank account; subject to bank checks',
            'withdrawal_timing':'Before 1pm working day: same day; later: next working day',
            'rate_policy':'Variable; 14-day notice before reductions; no future-rate guarantee',
            'protection':'Eligible deposits subject to FSCS per-person banking-licence limit; no amount/headroom check in this app',
            'terms_source':'bank:HTB', 'rate_source':'bank:HTB',
            'selection_claim':'Highest official no-bonus/unlimited-withdrawal quote successfully verified in the checked set; not a whole-market best-rate claim'}


def refresh_quote(root):
    root=Path(root)
    sources, quotes, failures = [], [], []
    today=datetime.now(timezone.utc).date().isoformat()
    for url, ident, parser in [(URL,'bank:HTB',parse_htb),(CHARTER_URL,'bank:Charter',parse_charter)]:
        try:
            raw, source=fetch(url, root/'.cache/raw', 'Public factual rate/eligibility metadata; full page redistribution not established',False)
            source['id']=ident
            quote=parser(raw,today)
            sources.append(source);quotes.append(quote)
        except Exception as exc:
            failures.append({'url':url,'error':str(exc)})
    if not quotes:
        raise DataError('No official standard bank quote could be verified; last good quote retained.')
    quote=max(quotes,key=lambda q:q['aer'])
    data={'evidence':quote,'sources':sources,'checked_quotes':quotes,'source_failures':failures}
    # Derived public factual quote is reviewable and can accompany a Git checkout.
    path=root/'bank-quote.json'; tmp=root/'bank-quote.tmp'
    tmp.write_text(json.dumps(data,indent=2));tmp.replace(path)
    return data


def parse_charter(raw,quote_date):
    parser=Text();parser.feed(raw.decode('utf-8'))
    text=' '.join(parser.parts)
    match=re.search(r'Easy Access - Issue\s+(\d+)\s+AER\*\s+([\d.]+)%.*?Balance\s+£([\d,]+)\s*-\s*£([\d,]+)',text,re.S)
    if match is None:
        raise DataError('Charter official product summary schema changed.')
    summary=text[match.start():]
    required=['You must be aged 18 or over and reside in the UK','You can make withdrawals from your Account at any time',
              'interest rate is variable','Nominated Account','Financial Services Compensation Scheme']
    if any(v not in summary for v in required) or 'bonus' in summary.lower():
        raise DataError('Charter standard easy-access terms need review.')
    return {'provider':'Charter Savings Bank','product':f'Easy Access (Issue {match[1]})',
            'facility_type':'uk_bank_deposit','aer':float(match[2])/100,'quote_date':quote_date,
            'minimum_balance':float(match[3].replace(',','')),'maximum_balance':float(match[4].replace(',','')),
            'instant_access':True,'unlimited_withdrawals':True,'introductory_bonus':False,
            'linked_current_account_required':False,'nominated_transfer_account_required':True,
            'eligibility':'UK residents aged 18+, individual savings; nominated UK bank/building-society transfer account; subject to bank checks',
            'withdrawal_timing':'No notice; transfers to nominated account subject to bank processing times',
            'rate_policy':'Managed variable rate; no future-rate guarantee or introductory bonus',
            'protection':'Eligible deposits subject to FSCS per-person banking-licence limit; no amount/headroom check in this app',
            'terms_source':'bank:Charter','rate_source':'bank:Charter',
            'selection_claim':'Highest successfully verified official no-bonus/unlimited-withdrawal quote among checked established banks; not a whole-market best-rate claim'}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',default='data/research')
    print(json.dumps(refresh_quote(parser.parse_args().root),indent=2))
