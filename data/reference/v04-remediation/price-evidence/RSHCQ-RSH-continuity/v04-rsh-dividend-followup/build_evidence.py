"""Build the bounded RSH dividend evidence package from saved requests only."""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRIMARY = ROOT.parent / 'v04-rsh-primary-identity'
PREFLIGHT = ROOT.parent / 'v04-rsh-identity-preflight'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save_json(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def response(number):
    saved = json.loads((ROOT / f'{number:02d}-search.json').read_text())
    value = saved['result']
    if value.get('status') == 'fulfilled':
        value = value['value']
    if 'webResults' not in value:
        value = json.loads(value['content'][0]['text'])
    return saved, value

sources = []
texts = {}
def extract(source_id, number, url, name, grade, **extra):
    _, value = response(number)
    row = next(row for row in value['webResults'] if row['url'] == url)
    text = row['content']
    path = ROOT / name
    if path.exists():
        assert path.read_text() == text, name
    else:
        path.write_text(text)
    texts[source_id] = re.sub(r'\s+', ' ', text)
    sources.append(dict(source_id=source_id, file=name, url=url,
                        title=row.get('title'), source_grade=grade,
                        request_number=number, response_file=f'{number:02d}-search.json',
                        characters=len(text), bytes=path.stat().st_size,
                        sha256=sha(path), **extra))

extract('S2004', 3,
        'https://www.sec.gov/Archives/edgar/data/96289/000009628905000016/k123104.txt',
        '2004-SEC-10K.indexed.txt',
        'Issuer SEC filing text obtained through search index; original TXT not downloaded independently')
sec2005 = 'https://www.sec.gov/Archives/edgar/data/96289/000009628906000013/k123105.htm'
extract('S2005_HEADER', 1, sec2005, '2005-SEC-10K.header.indexed.txt',
        'SEC indexed partial filing; issuer identity and filing provenance only; returned text has no dividend amount')
extract('S2005_MIRROR', 4,
        'https://companiesmarketcap.com/radioshack/sec-reports-10k/0000096289-06-000013/',
        '2005-10K.companiesmarketcap.indexed.txt',
        'Issuer SEC filing mirrored by a third party, obtained through search index; dividend passage not independently returned from SEC endpoint',
        original_sec_url=sec2005, accession='0000096289-06-000013',
        excluded_content='Third-party site summary, market value, delisting and last-trade commentary')
extract('SDC', 2, 'https://www.dividendchannel.com/symbol/rsh/',
        'DividendChannel-RSH.indexed.txt',
        'Secondary dividend history; table column is Date, not an explicit Ex-dividend date label',
        caveat='Provider says data may be adjusted for splits and directs readers to verify with the company')

old_index = json.loads((PRIMARY / 'source-index.json').read_text())
for source_id, name in [('S2010', '2010-SEC-10K.indexed.txt'),
                         ('S2010_RELEASE', '2010-issuer-dividend.indexed.txt')]:
    old = next(row for row in old_index if row['file'] == name)
    path = PRIMARY / name
    assert sha(path) == old['sha256']
    texts[source_id] = re.sub(r'\s+', ' ', path.read_text())
    sources.append(dict(source_id=source_id, file=f'../v04-rsh-primary-identity/{name}',
                        url=old['url'], source_grade=old['source_level'],
                        reused_existing_local_evidence=True, request_number=None,
                        characters=len(path.read_text()), bytes=path.stat().st_size,
                        sha256=sha(path)))
vendor_path = PREFLIGHT / 'required-window-vendor-cash-actions.csv'
sources.append(dict(source_id='SWIKI', file='../v04-rsh-identity-preflight/required-window-vendor-cash-actions.csv',
                    source_grade='Existing vendor event fields, not issuer evidence',
                    reused_existing_local_evidence=True, request_number=None, sha256=sha(vendor_path)))
save_json('source-index.json', sources)

excerpts = []
def excerpt(source_id, quote, claim):
    assert quote in texts[source_id], (source_id, quote)
    excerpts.append(dict(source_id=source_id, quote=quote, claim=claim,
                         excerpt_whitespace_normalized=True))

excerpt('S2004',
        'On September 24, 2004, our Board of Directors declared an annual dividend of $0.25 per common share. The dividend was paid on December 20, 2004, to stockholders of record on December 1, 2004.',
        '2004 annual dividend amount, declaration date, record date and actual payment date')
excerpt('S2005_MIRROR',
        'On September 29, 2005, our Board of Directors declared an annual dividend of $0.25 per share. The dividend was paid on December 19, 2005, to stockholders of record on December 1, 2005.',
        '2005 annual dividend amount, declaration date, record date and actual payment date; underlying issuer filing carried by third-party mirror')
excerpt('S2004',
        'The dividend payment of $39.7 million was funded from cash on hand.',
        '2004 financing discussion confirms cash payment; aggregate not used to infer per-share amount')
excerpt('S2005_MIRROR',
        'The dividend payment of $33.7 million was funded from cash on hand.',
        '2005 financing discussion confirms cash payment; aggregate not used to infer per-share amount')
excerpt('S2010',
        '2010 2009 2008 2007 2006 (4)',
        'Column order in Item 6 selected financial data (unaudited)')
excerpt('S2010',
        'Dividends declared per share $ 0.25 $ 0.25 $ 0.25 $ 0.25 $ 0.25',
        'Annual declared per-share totals for 2006 through 2010; not primary proof of every event date')
excerpt('S2010',
        'On November 4, 2010, our Board of Directors declared an annual dividend of $0.25 per share. The dividend was paid on December 16, 2010, to stockholders of record on November 26, 2010.',
        '2010 annual payment amount and declaration/record/actual payment dates')
excerpt('SDC',
        '11/23/10 0.250 11/24/09 0.250 11/25/08 0.250 11/27/07 0.250 11/29/06 0.250 11/29/05 0.250 11/29/04 0.250',
        'All seven secondary Date/Div pairs match WIKI event fields; header does not explicitly identify date semantics')
save_json('primary-and-secondary-excerpts.json', excerpts)

with vendor_path.open() as handle:
    vendor = list(csv.DictReader(handle))
dates = ['2004-11-29', '2005-11-29', '2006-11-29', '2007-11-27', '2008-11-25', '2009-11-24', '2010-11-23']
assert [row['date'] for row in vendor] == dates
known_dates = {
    2004: ('2004-09-24', '2004-12-01', '2004-12-20'),
    2005: ('2005-09-29', '2005-12-01', '2005-12-19'),
    2010: ('2010-11-04', '2010-11-26', '2010-12-16'),
}
rows = []
for row in vendor:
    date = row['date']
    year = int(date[:4])
    secondary = f'{date[5:7]}/{date[8:10]}/{date[2:4]} 0.250'
    assert secondary in texts['SDC']
    assert float(row['ex-dividend']) == 0.25
    declaration, record, paid = known_dates.get(year, ('', '', ''))
    source_id = 'S2004' if year == 2004 else 'S2005_MIRROR' if year == 2005 else 'S2010'
    grade = ('ISSUER_ANNUAL_PAYMENT_IN_SEC_INDEXED_TEXT' if year in (2004, 2010)
             else 'ISSUER_ANNUAL_PAYMENT_IN_THIRD_PARTY_FILING_MIRROR' if year == 2005
             else 'ISSUER_ANNUAL_DECLARED_TOTAL_ONLY_IN_SEC_INDEXED_TEXT')
    rows.append(dict(source_WIKI_ex_date=date, source_WIKI_cash=0.25,
                     issuer_per_share_amount=0.25, issuer_amount_source_id=source_id,
                     issuer_amount_evidence_grade=grade,
                     secondary_date=date, secondary_cash=0.25,
                     secondary_source_id='SDC', secondary_date_column_label='Date',
                     secondary_date_and_amount_match=True,
                     primary_ex_date_explicitly_verified=False,
                     declaration_date=declaration, record_date=record, actual_pay_date=paid,
                     approved_for_application=False))
with (ROOT / 'dividend-evidence.csv').open('w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
save_json('dividend-evidence.json', rows)

requests = []
for number in range(1, 5):
    saved, _ = response(number)
    path = ROOT / f'{number:02d}-search.json'
    requests.append(dict(number=number, request=saved['request'],
                         response_file=path.name, sha256=sha(path)))
save_json('request-log.json', dict(maximum_new_requests=4, used_new_requests=4,
                                  additional_network_requests_during_local_assembly=0,
                                  requests=requests))
save_json('checks.json', dict(
    required_window=['2003-12-19', '2011-07-11'],
    evidence_rows=7, all_source_vendor_cash_amounts_equal_025=True,
    all_secondary_date_amount_pairs_match=True,
    amount_supported_by_issuer_document_content_years=list(range(2004, 2011)),
    third_party_filing_mirror_used_for_years=[2005],
    issuer_primary_explicit_ex_date_count=0,
    primary_actual_payment_detail_years=[2004, 2005, 2010],
    verbatim_excerpts_verified_against_preserved_text=True,
    reused_primary_source_hashes_verified=True,
    new_public_requests=4, request_budget=4,
    generated_price_rows=0, repository_or_manifest_edits=0,
    approved_for_application=False))
print(json.dumps({'rows':len(rows), 'sources':len(sources),
                  'dividend_evidence_sha256':sha(ROOT/'dividend-evidence.csv'),
                  'source_index_sha256':sha(ROOT/'source-index.json')}, indent=2))
