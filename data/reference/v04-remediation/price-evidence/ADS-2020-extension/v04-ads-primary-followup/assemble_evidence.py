"""Assemble ADS issuer evidence from four completed, preserved search responses."""
from pathlib import Path
import csv
import hashlib
import json
import re

OUT=Path(__file__).resolve().parent
PRE=OUT.parent/'v04-ads-bounded-preflight'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def normalize(text):return re.sub(r'\s+',' ',text.replace('\u200b',' ')).strip()
def response(number):
    name={1:'01-2017-annual-search.json',2:'02-2019-annual-search.json',3:'03-2020-q2-search.json',4:'04-2020-half-year-search.json'}[number]
    wrapper=json.loads((OUT/name).read_text());value=wrapper['result']
    if 'webResults' not in value:value=json.loads(value['content'][0]['text'])
    return name,value

sources=[];texts={}
def extract(source_id,number,url_fragment,name,grade,**extra):
    response_name,value=response(number)
    row=next(r for r in value['webResults'] if url_fragment in r['url'])
    path=OUT/name;path.write_text(row['content']);texts[source_id]=normalize(row['content'])
    sources.append(dict(source_id=source_id,file=name,url=row['url'],title=row.get('title'),
                        request_number=number,response_file=response_name,source_grade=grade,
                        characters=len(row['content']),sha256=sha(path),**extra))

extract('P17M',1,'content.edgar-online.com','2017-10K.edgar-online.indexed.txt',
        'Issuer 2017 Form10-K content mirrored by EDGAR Online, retrieved via search index; capped partial text, not original full SEC HTML download',
        accession='0001101215-18-000066',cik='0001101215',report_period='2017-12-31')
extract('P18Q1',1,'/000110121518000014/exhibit_99-1.htm','2018-01-25-results.SEC-indexed.txt',
        'Issuer earnings release in SEC exhibit, indexed text; supports common dividend increase to0.57 beginning2018Q1')
extract('P17Q1_RELEASE',1,'marketscreener.com','2017-01-26-dividend.issuer-repost.indexed.txt',
        'Contemporaneous issuer PRNewswire release reposted by MarketScreener; use historical announcement only, not current profile/price/news')
extract('S17Q1_EX',1,'dividendinvestor.com','2017-01-26-dividend.secondary.indexed.txt',
        'Secondary contemporaneous dividend announcement; explicitly labels ex-date2017-02-13; later current-news widgets excluded')
extract('P19M',2,'content.edgar-online.com','2019-10K.edgar-online.indexed.txt',
        'Issuer 2019 Form10-K content mirrored by EDGAR Online, retrieved via search index; partial text, not full original filing; includes Item5 quarterly paid cash table',
        accession='0001101215-20-000049',cik='0001101215',report_period='2019-12-31')
extract('P19Q2_RELEASE',2,'prnewswire.com','2019-04-25-dividend.issuer-release.indexed.txt',
        'Issuer PRNewswire announcement indexed text; individual0.63 common declaration and stated record/payable dates')
extract('P20Q2_SEC',3,'/1101215/000110121520000078/form_8k.htm','2020-04-23-dividend.SEC-indexed.txt',
        'Issuer SEC8-K indexed text; ordinary ADS stock identity and declared0.21, record/payable dates; not proof actual cash was paid')
extract('P20Q2_RELEASE',4,'301045591','2020-04-23-dividend.issuer-release.indexed.txt',
        'Issuer PRNewswire announcement indexed text; same declaration as SEC8-K, not an independent cash-payment event')

save('source-index.json',sources)
excerpts=[]
def excerpt(source_id,key,quote,scope):
    quote=normalize(quote);assert quote in texts[source_id],(source_id,key,quote)
    excerpts.append(dict(id=key,source_id=source_id,quote=quote,scope=scope,
                         normalization='Whitespace collapsed and zero-width layout characters removed; original indexed text preserved unchanged'))

excerpt('P17M','2017_quarter_amounts_and_2016_initial_quarter',
 'We declared and paid cash dividends per share during the periods presented as follows: Dividends Per Share Amount (in millions) Year Ended December 31, 2017 First quarter 0.52 29.0 Second quarter 0.52 29.0 Third quarter 0.52 28.8 Fourth quarter 0.52 28.7 Total cash dividends declared and paid 2.08 115.5 Year Ended December 31, 2016 First quarter Second quarter Third quarter Fourth quarter 0.52 30.0 Total cash dividends declared and paid 0.52 30.0',
 '2016Q4 and each2017 quarter per-share declared-and-paid amounts; blank earlier2016 rows are not invented event dates')
excerpt('P17M','dividend_program_start',
 'Since October 2016, our Board of Directors has declared quarterly cash dividend payments on our outstanding common stock.',
 'Program timing only; exact2016 first declaration/record/pay dates are not supplied by this passage')
quarter2017=[
 ('2017-02-13','January 26, 2017','February 15, 2017','29.0','March 17, 2017'),
 ('2017-05-11','April 20, 2017','May 15, 2017','29.0','June 19, 2017'),
 ('2017-08-10','July 20, 2017','August 14, 2017','28.8','September 19, 2017'),
 ('2017-11-13','October 19, 2017','November 14, 2017','28.7','December 19, 2017'),
]
for observed,declared,record,aggregate,paid in quarter2017:
    quote=f'On {declared}, our Board of Directors declared a quarterly cash dividend of $0.52 per share on our common stock to stockholders of record at the close of business on {record}, resulting in a dividend payment of ${aggregate} million on {paid}.'
    excerpt('P17M','individual_2017_event_'+observed,quote,'Individual common amount and declaration/record/actual payment date; passage does not explicitly state ex-date')
excerpt('P17M','2018Q1_declaration',
 'On January 25, 2018, our Board of Directors declared a quarterly cash dividend of $0.57 per share on our common stock, payable on March 20, 2018 to stockholders of record at the close of business on February 14, 2018.',
 'Individual2018Q1 declared amount and stated payable/record dates')
excerpt('P19M','2018_2019_quarterly_paid_amounts',
 'Dividends Per Share Amount (in millions) Year Ended December 31, 2019 First quarter $ 0.63 $ 33.9 Second quarter 0.63 33.1 Third quarter 0.63 30.4 Fourth quarter 0.63 30.0 Total cash dividends paid $ 2.52 $ 127.4 Year Ended December 31, 2018 First quarter $ 0.57 $ 31.7 Second quarter 0.57 31.6 Third quarter 0.57 31.2 Fourth quarter 0.57 30.7 Total cash dividends paid $ 2.28 $ 125.2',
 'Quarter per-share paid totals. One relevant source event is observed per quarter; this table does not independently supply exact ex/record/pay dates')
excerpt('P19M','2020Q1_declaration',
 'On January 30, 2020 our Board of Directors declared a quarterly cash dividend of $0.63 per share on our common stock, payable on March 19, 2020 to stockholders of record at the close of business on February 14, 2020.',
 '2020Q1 declaration and scheduled dates; actual payment not established by this future-dated statement')
excerpt('P19Q2_RELEASE','2019Q2_issuer_declaration',
 "Alliance Data Systems Corporation (NYSE: ADS), a leading global provider of data-driven marketing and loyalty solutions, today announced that its Board of Directors declared a quarterly cash dividend of $0.63 per share on the Company's common stock, payable on June 18, 2019 to stockholders of record at the close of business on May 14, 2019.",
 'Release is dated April25,2019; individual common declaration and stated payable/record dates')
excerpt('P20Q2_SEC','2020Q2_SEC_declaration',
 'On April 23, 2020, Alliance Data Systems Corporation (the “Company”) issued a press release announcing that the Board of Directors of the Company declared a quarterly cash dividend of $0.21 per share, payable on June 18, 2020 to stockholders of record at the close of business on May 14, 2020.',
 'Individual declared amount and scheduled dates; actual payment/2020Q2 financial statements not retrieved')
excerpt('P20Q2_RELEASE','2020Q2_common_stock_class',
 "today announced that its Board of Directors declared a quarterly cash dividend of $0.21 per share on the Company's common stock, payable on June 18, 2020 to stockholders of record at the close of business on May 14, 2020.",
 'Explicit common-stock class; not preferred distribution')
excerpt('S17Q1_EX','secondary_explicit_ex_date_2017Q1',
 'Dividend Declaration Date: January 26, 2017 Dividend Ex Date: February 13, 2017 Dividend Record Date: February 15, 2017 Dividend Payment Date: March 17, 2017 Dividend Amount: $ 0.5200',
 'Only explicitly labelled independent secondary ex-date obtained in these four requests')
save('issuer-and-date-excerpts.json',excerpts)

known={
 '2017-02-13':('2017-01-26','2017-02-15','2017-03-17','ACTUAL_PAYMENT_DATE_STATED_IN_ANNUAL_REPORT'),
 '2017-05-11':('2017-04-20','2017-05-15','2017-06-19','ACTUAL_PAYMENT_DATE_STATED_IN_ANNUAL_REPORT'),
 '2017-08-10':('2017-07-20','2017-08-14','2017-09-19','ACTUAL_PAYMENT_DATE_STATED_IN_ANNUAL_REPORT'),
 '2017-11-13':('2017-10-19','2017-11-14','2017-12-19','ACTUAL_PAYMENT_DATE_STATED_IN_ANNUAL_REPORT'),
 '2018-02-13':('2018-01-25','2018-02-14','2018-03-20','STATED_PAYABLE_DATE_QUARTER_AMOUNT_LATER_CONFIRMED_PAID'),
 '2019-05-13':('2019-04-25','2019-05-14','2019-06-18','STATED_PAYABLE_DATE_QUARTER_AMOUNT_LATER_CONFIRMED_PAID'),
 '2020-02-13':('2020-01-30','2020-02-14','2020-03-19','STATED_PAYABLE_DATE_ACTUAL_PAYMENT_NOT_OBTAINED'),
 '2020-05-13':('2020-04-23','2020-05-14','2020-06-18','STATED_PAYABLE_DATE_ACTUAL_PAYMENT_NOT_OBTAINED'),
}
with (PRE/'ADS-factor-event-observations.csv').open() as handle:observed=list(csv.DictReader(handle))
assert len(observed)==15
ledger=[]
for source in observed:
    day=source['date'];year=int(day[:4]);quarter=(int(day[5:7])-1)//3+1
    amount=0.52 if year<=2017 else 0.57 if year==2018 else 0.63
    if day=='2020-05-13':amount=0.21
    primary='P17M' if year<=2017 else 'P19M'
    scope='ISSUER_QUARTER_PER_SHARE_TOTAL_MATCHING_ONE_OBSERVED_EVENT'
    refs=[primary]
    if day in {r[0] for r in quarter2017}:scope='INDIVIDUAL_COMMON_DECLARATION_AND_ACTUAL_PAYMENT_STATED'
    if day=='2018-02-13':refs=['P17M','P18Q1','P19M'];scope='INDIVIDUAL_COMMON_DECLARATION_AND_LATER_QUARTER_PAID_TOTAL'
    if day=='2019-05-13':refs=['P19M','P19Q2_RELEASE'];scope='INDIVIDUAL_COMMON_DECLARATION_AND_QUARTER_PAID_TOTAL'
    if day=='2020-02-13':scope='INDIVIDUAL_COMMON_DECLARATION_ONLY_ACTUAL_PAYMENT_NOT_OBTAINED'
    if day=='2020-05-13':refs=['P20Q2_SEC','P20Q2_RELEASE'];scope='INDIVIDUAL_COMMON_DECLARATION_ONLY_ACTUAL_PAYMENT_NOT_OBTAINED'
    declared,record,payment,payment_grade=known.get(day,(None,None,None,'EXACT_PAYMENT_DATE_NOT_OBTAINED'))
    is_tail=day>'2018-03-27'
    wiki_value=None if is_tail else float(source['wiki_ex_dividend_observed'])
    role='tail_event' if is_tail else 'old_WIKI_recorded_cash' if wiki_value else 'old_prefix_unrecorded_event'
    ledger.append(dict(ticker='ADS',security_class='Alliance Data Systems Corporation ordinary common stock',
        source_observed_date=day,observed_date_semantics=('WIKI_ex_dividend_field_and_SheepB_factor_step' if role=='old_WIKI_recorded_cash' else 'SheepB_factor_step_date_NOT_independently_confirmed_ex_date'),
        event_role=role,source_observed_quarter=f'{year}Q{quarter}',wiki_cash_observation=wiki_value,
        issuer_confirmed_amount=amount,amount_currency='USD_per_nominal_common_share',
        issuer_amount_evidence_scope=scope,amount_source_ids=refs,
        issuer_declaration_date=declared,issuer_record_date=record,issuer_payment_date=payment,
        issuer_payment_date_evidence_scope=payment_grade,
        actual_paid_per_share_quarter_supported=(year<=2019),
        primary_ex_date=None,primary_ex_date_explicitly_verified=False,
        secondary_explicit_ex_date=day if day=='2017-02-13' else None,
        secondary_ex_date_source_ids=['S17Q1_EX'] if day=='2017-02-13' else [],
        date_inferred_from_factor_or_record_date=False,amount_inferred_from_factor=False,
        proposed_application_amount=None,approved_for_application=False))
save('dividend-ledger.json',ledger)
with (OUT/'dividend-ledger.csv').open('w',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=ledger[0]);writer.writeheader()
    for row in ledger:
        writer.writerow({key:json.dumps(value,ensure_ascii=False) if isinstance(value,list) else value for key,value in row.items()})

request_status=json.loads((OUT/'request-status.json').read_text())
assert request_status['new_public_requests_started']==4 and all(r['status']=='returned' for r in request_status['requests'])
excluded=[]
allowed_urls={s['url'] for s in sources}
for number in range(1,5):
    _,value=response(number)
    for row in value['webResults']:
        if row['url'] in allowed_urls:continue
        if any(f'/data/{cik}/' in row['url'] for cik in ['27904','320193','720500','1097149','40729']):reason='Wrong issuer CIK; Delta/Apple/Amtech/Align/Ally materials excluded'
        elif 'last10k.com' in row['url']:reason='Link metadata only; not the actual requested annual/quarterly financial text'
        elif '000110121520000144' in row['url'] or '301162647' in row['url'] or '33777919' in row['url']:reason='Outside required distribution window; not used to establish earlier payment'
        elif 'forbes.com' in row['url']:reason='Contemporaneous secondary repeat of already obtained2020Q2 issuer declaration; not needed as extra independent payment evidence'
        else:reason='Partial or redundant result not used in ledger'
        excluded.append(dict(request_number=number,url=row['url'],reason=reason))
save('excluded-and-insufficient-results.json',excluded)
summary=dict(status='ISSUER_AMOUNTS_SUPPORTED_DATE_AND_PAYMENT_LIMITS_DISCLOSED',
             required_window=['2012-12-12','2020-07-02'],issuer='Alliance Data Systems Corporation',cik='0001101215',
             events=15,amounts_with_issuer_document_support=15,source_event_roles={role:sum(r['event_role']==role for r in ledger) for role in ['old_WIKI_recorded_cash','old_prefix_unrecorded_event','tail_event']},
             total_supported_source_event_amounts=round(sum(r['issuer_confirmed_amount'] for r in ledger),2),
             primary_ex_dates_explicitly_obtained=0,secondary_explicit_ex_dates_obtained=1,
             individual_declaration_record_payment_date_sets_obtained=len(known),
             exact_actual_payment_dates_stated_in_annual_report=4,
             events_with_actual_paid_quarter_amount_support=13,
             declaration_only_2020_events=['2020-02-13','2020-05-13'],
             full_2020_Q2_10Q_financial_text_obtained=False,
             full_2012_2020_corporate_action_census_obtained=False,
             every_amount_was_null_until_issuer_source_obtained=True,
             from_factor_amount_inference_used=False,
             request_budget=4,public_requests_started=4,public_requests_returned=4,pending_requests=0,
             separate_direct_HTTP_requests=0,repo_modified=False,candidate_created=False,
             approved_for_application=False,global_gate_close_approved=False)
save('summary.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
