"""Build a bounded evidence packet for STR, LSI and ALTR; no main inputs change."""
from pathlib import Path
import csv
import hashlib
import json

import pandas as pd

WORK = Path('/Users/fighting/Documents/Codex/2026-09-06/co-2/work/v04-identity-actions')
ARCHIVE = WORK.parent / 'v04-remediation-archive' / 'prices'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(name):
    result = json.loads((WORK / name).read_text())
    if result.get('structuredContent'):
        return result['structuredContent']
    return json.loads(next(item['text'] for item in result['content'] if item['type'] == 'text'))


def excerpt(text, term, length=2400):
    index = text.lower().find(term.lower())
    return text[max(0, index - 100):index + length] if index >= 0 else ''


proofs = {
    'str_merger': source('str-merger.search.json')['webResults'][0],
    'str_dividend': source('str-final-dividend.search.json')['webResults'][0],
    'lsi_merger': source('lsi-merger.search.json')['webResults'][1],
    'altr_merger': source('altr-merger.search.json')['webResults'][1],
    'life_storage_rename': source('lsi-rename.search.json')['webResults'][3],
    'str_quarters': source('str-2015-10k.source.json'),
    'lsi_quarters': source('lsi-2013-10k.source.json'),
    'altr_quarters': source('altr-2014-10k.source.json'),
    'altair_new_issuer': source('altr-2018-10k.source.json'),
}
terms = {'str_merger': 'On September 16, 2016', 'str_dividend': 'contingent cash dividend',
    'lsi_merger': 'Completion of Acquisition', 'altr_merger': 'Completion of Acquisition',
    'life_storage_rename': 'Shares of Life Storage', 'str_quarters': 'High price',
    'lsi_quarters': 'high and low sales prices', 'altr_quarters': 'high and low closing sale prices',
    'altair_new_issuer': 'Our Class\u00a0A common stock began trading'}
for key, item in proofs.items():
    text = item.get('content', '')
    found = excerpt(text, terms[key])
    if not found and key == 'altair_new_issuer':
        found = excerpt(text, 'November\u00a01, 2017')
    (WORK / f'{key}.excerpt.txt').write_text(item['title'] + '\n' + item['url'] + '\n\n' + found + '\n')

expected = {
    'STR': {2014: [(24.09, 22.07), (24.89, 22.83), (24.85, 21.49), (26.44, 21.06)],
            2015: [(26.44, 22.47), (24.33, 20.88), (22.29, 18.29), (21.21, 18.02)]},
    'LSI': {2012: [(9.20, 5.99), (8.91, 5.95), (8.10, 5.59), (7.23, 6.26)],
            2013: [(7.66, 6.51), (7.60, 5.99), (8.08, 7.09), (11.04, 7.39)]},
    'ALTR': {2013: [(36.25, 33.27), (34.75, 31.07), (38.80, 32.96), (37.83, 30.83)],
             2014: [(37.04, 31.38), (36.43, 32.08), (37.07, 32.67), (38.27, 30.83)]},
}
frames, comparisons = {}, []
for ticker, years in expected.items():
    frame = pd.read_parquet(ARCHIVE / f'{ticker}.parquet')
    frame['date'] = pd.to_datetime(frame['date'])
    frames[ticker] = frame.sort_values('date')
    for year, quarters in years.items():
        for quarter, (high, low) in enumerate(quarters, start=1):
            subset = frame.loc[frame.date.dt.year.eq(year) & frame.date.dt.quarter.eq(quarter)]
            actual_high = float(subset['close' if ticker == 'ALTR' else 'high'].max())
            actual_low = float(subset['close' if ticker == 'ALTR' else 'low'].min())
            comparisons.append({'ticker': ticker, 'year': year, 'quarter': quarter,
                'comparison_basis': 'raw close max/min' if ticker == 'ALTR' else 'raw daily high max / low min',
                'sec_high': high, 'archive_high': actual_high, 'sec_low': low, 'archive_low': actual_low,
                'high_delta': actual_high - high, 'low_delta': actual_low - low,
                'match_to_report_rounding': abs(actual_high - high) <= .0051 and abs(actual_low - low) <= .0051,
                'sec_url': proofs[ticker.lower() + '_quarters']['url']})
with (WORK / 'quarter-price-comparison.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(comparisons[0])); writer.writeheader(); writer.writerows(comparisons)

segments = [
    {'ticker': 'STR', 'historical_issuer': 'Questar Corporation', 'issuer_cik': '0000751652',
     'identity_status': 'SUPPORTED_BY_PRIMARY_FILINGS_AND_QUARTER_PRICES',
     'accepted_start': '2003-10-01', 'accepted_end': '2016-09-16',
     'acceptance_scope': 'Issuer attribution, not an assertion that every daily bar or all historical corporate actions are independently verified.',
     'excluded_segments': [], 'effective_date': '2016-09-16',
     'trading_timing': 'SEC 8-K says suspend after close of trading on the closing date.',
     'cash_consideration_per_old_share_usd': 25.0,
     'additional_contingent_dividend_per_old_share_usd': .07018,
     'combined_nominal_entitlement_usd': 25.07018,
     'dividend_record_date': '2016-09-16', 'dividend_payment_date': None,
     'payment_note': 'Issuer says payable as soon as practicable after closing; do not invent a broker cash-posting date.',
     'sources': [proofs['str_merger']['url'], proofs['str_dividend']['url'], proofs['str_quarters']['url']],
     'metadata_correction': 'Archive label is an ETF; raw price series is supported as Questar. No post-2016 rows occur in this extracted file.'},
    {'ticker': 'LSI', 'historical_issuer': 'LSI Corporation (formerly LSI Logic)', 'issuer_cik': '0000703360',
     'identity_status': 'REJECT_ARCHIVE_FOR_HISTORICAL_ISSUER',
     'accepted_start': None, 'accepted_end': None,
     'excluded_segments': [{'start': '2003-10-01', 'end': '2018-03-07',
        'reason': 'The archive fails all eight 2012/2013 quarterly price-range checks for LSI Corporation. Do not repair with a constant scale factor or rename it into the historical member.'}],
     'effective_date': '2014-05-06', 'trading_timing': 'Company notified NASDAQ on May 6 that trading should be suspended; exact intraday effective time is not established here.',
     'cash_consideration_per_old_share_usd': 11.15,
     'cash_event_application': 'Terms verified for genuine LSI Corporation old shares only. The wrong archive cannot provide a trustworthy position quantity or last price for this cash event.',
     'later_symbol_issuer': {'name': 'Life Storage, Inc. (formerly Sovran Self Storage, Inc.)',
        'issuer_cik': None, 'old_symbol': 'SSS', 'new_symbol': 'LSI', 'ticker_effective_date': '2016-08-15',
        'scope': 'Primary issuer announcement proves later ticker reuse. The exact entire archive origin as Sovran/Life Storage is not independently proved by this bounded packet.'},
     'sources': [proofs['lsi_merger']['url'], proofs['lsi_quarters']['url'], proofs['life_storage_rename']['url']]},
    {'ticker': 'ALTR', 'historical_issuer': 'Altera Corporation', 'issuer_cik': '0000768251',
     'identity_status': 'PRE_TERMINATION_SEGMENT_SUPPORTED',
     'accepted_start': '2003-10-01', 'accepted_end': '2015-12-24',
     'acceptance_scope': 'Issuer attribution supported by eight quarters of closing-price ranges and cash event; not a guarantee of every daily OHLC value.',
     'excluded_segments': [{'start': '2018-03-01', 'end': '2018-03-07',
        'reason': 'Five rows occur after old Altera shares were cancelled. Altair Engineering separately began public ALTR trading on 2017-11-01; never append this tail to old Altera.'}],
     'effective_date': '2015-12-28', 'trading_timing': 'Merger effective date is confirmed; exact intraday phase not established. Last old-issuer bar in this archive is 2015-12-24.',
     'cash_consideration_per_old_share_usd': 54.0,
     'later_symbol_issuer': {'name': 'Altair Engineering Inc.', 'issuer_cik': '0001701732',
        'first_public_trading_date': '2017-11-01', 'ipo_price_usd': 13.0,
        'scope': 'New issuer and ticker reuse are confirmed; individual tail rows are not independently re-quoted here.'},
     'sources': [proofs['altr_merger']['url'], proofs['altr_quarters']['url'], proofs['altair_new_issuer']['url']]},
]
for entry in segments:
    ticker = entry['ticker']; frame = frames[ticker]
    entry['archive_path'] = str(ARCHIVE / f'{ticker}.parquet')
    entry['archive_sha256'] = sha(ARCHIVE / f'{ticker}.parquet')
    entry['archive_rows'] = len(frame)
    accepted = frame.iloc[:0] if entry['accepted_start'] is None else frame.loc[frame.date.between(entry['accepted_start'], entry['accepted_end'])]
    entry['accepted_rows'] = len(accepted)
    entry['excluded_rows'] = len(frame) - len(accepted)
    entry['quarter_checks_matched'] = sum(r['match_to_report_rounding'] for r in comparisons if r['ticker'] == ticker)
    entry['quarter_checks_total'] = 8
    entry['last_accepted_bar'] = None if accepted.empty else {
        'date': str(accepted.iloc[-1].date.date()),
        **{key: float(accepted.iloc[-1][key]) for key in ['open', 'high', 'low', 'close', 'volume', 'adj_close']}}
    if ticker == 'STR':
        entry['archive_contingent_dividend_present'] = False
        entry['archive_last_dividend_rows'] = [{**r, 'date': str(r['date'].date())} for r in frame.loc[frame['ex-dividend'].ne(0), ['date', 'ex-dividend']].tail(4).to_dict('records')]
packet = {'status': 'BOUNDED_IDENTITY_AND_ACTION_REVIEW', 'runtime_inputs_modified': False,
    'no_new_price_downloads': True, 'reviewed_tickers': ['STR', 'LSI', 'ALTR'], 'segments': segments,
    'source_file_hashes': {p.name: sha(p) for p in sorted(WORK.glob('*.json')) if p.name.endswith(('.source.json', '.search.json'))},
    'limits': ['Quarter checks identify the issuer and reject gross mismatches; they do not verify every daily OHLCV value.',
        'Cash consideration is stated per nominal old share. Existing adjusted-price holdings need the correct share basis; never apply verified cash to an unverified issuer path.',
        'Effective dates identify shareholder entitlement changes, not a fabricated broker cash-payment timestamp.']}
(WORK / 'identity-action-segments.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')

lines = ['# STR / LSI / ALTR 身份与终止事件核对', '',
    '2026-09-07；有界查询与本地归档核对。未修改主代码、主manifest或原始价格。', '',
    '| 代码 | 作为原历史成员可保留的身份区间 | 需排除的归档 | 已确认终止权益 |', '|---|---|---|---|',
    f"| STR | 2003-10-01 → 2016-09-16，{segments[0]['accepted_rows']}行；Questar Corporation | 无2016后行情；ETF名称错误 | 2016-09-16，$25现金 + $0.07018 contingent dividend |",
    '| LSI | 无；现有整段不能代表旧LSI Corporation | 2003-10-01 → 2018-03-07，3420行 | 真正旧LSI于2014-05-06转为每股$11.15现金；不能用错误行情算出的股份量结算 |',
    f"| ALTR | 2003-10-01 → 2015-12-24，{segments[2]['accepted_rows']}行；Altera Corporation | 2018-03-01 → 2018-03-07，5行 | 2015-12-28，旧股每股$54现金 |", '',
    '以上“可保留”指发行人身份区间得到佐证，不是每个日线值和所有公司行动均已通过审计。', '',
    '## STR', '',
    '- SEC 2015年10-K明确注册人为Questar Corporation（CIK 751652）。归档2014/2015八个季度的原始日内高低价，与SEC表中16个极值全部在分位舍入误差内匹配；因此不能因为wiki-stocks.csv叫ETF就删除这条真实Questar序列。',
    '- 2016-09-16 8-K确认完成合并、旧股每股转换为$25现金，并请求NYSE在该日收盘后暂停交易。归档同日终止，最后raw close和adj close都是25.06。',
    '- 2016-09-14双方联合公告另载：每天$0.00242，从8月19日至closing；若9月16日完成则合计$0.07018，record date为closing收盘，随后尽快支付。9月16日完成已经8-K确认，所以条件成立。',
    '- 这笔尾部dividend不在归档的ex-dividend中。应识别总名义权益$25.07018；付款具体日未取得证据，应保留应收/付款时点限制，不擅自创建券商现金到账记录。',
    '- 归档还保留2010-07-01的30.221293272371特殊分配调整，原始价从45.49降至15.22，而复权价连续。它提示Questar/QEP分拆应作为独立公司行动核验，不应把原始价断点直接当错误。', '',
    '## LSI', '',
    '- 真正LSI Corporation（CIK 703360）2013年第一季股价范围是6.51–7.66美元；本地LSI归档是60.29–67.44。2012/2013全部八季均不符，且高低价比例不是固定缩放。因此无法通过乘除一个常数修复这条旧LSI行情。',
    '- 旧LSI的8-K确认2014-05-06被Avago收购，每股$11.15现金。归档2014-05-05却收于76.05，仍说明它不能用于旧LSI的持仓路径和终止结算。',
    '- 2016-08-15 SEC发行人公告确认Sovran Self Storage（SSS）改名Life Storage并以LSI交易。该公告证实后来的ticker复用背景，但本次未取得足够季度原件来独立认定整条归档每个阶段究竟来自Sovran；无需等这一步完成即可拒绝把它当旧LSI。', '',
    '## ALTR', '',
    '- 旧Altera（CIK 768251）2014年10-K列出2013/2014八季的最高/最低收盘价。本地pre-2015段16个原始收盘极值全部在分位舍入误差内吻合；这里必须比较close极值，不能误拿日内high/low去比SEC的closing sale prices。',
    '- 2015-12-28旧Altera的8-K确认合并完成并把每股转为$54现金。归档最后旧股bar为2015-12-24，close53.96；下一段竟直接跳到2018-03-01，间隔798天。',
    '- Altair Engineering（另一CIK 1701732）的2018年10-K确认2017-11-01才首次以ALTR公开交易，之前没有公开市场。故2018五行绝不能拼到旧Altera；本次不把股票代码相同视作连续证券。', '',
    '## 核对文件', '',
    '- identity-action-segments.json：逐段结论、名义对价、生效日、付款时点限制、原始文件哈希。',
    '- quarter-price-comparison.csv：24个季度的SEC与归档极值对照。',
    '- *.excerpt.txt：关键SEC段落及直接URL。',
    '- *.source.json / *.search.json：工具取回的原始证据；无关搜索结果不作为结论依据。', '',
    '## 主要来源', '']
for name, item in proofs.items():
    lines.append(f"- {name}: {item['url']}")
lines.append('')
(WORK / 'identity-action-report.md').write_text('\n'.join(lines))
print(json.dumps([{k: r.get(k) for k in ['ticker', 'identity_status', 'accepted_start', 'accepted_end',
    'accepted_rows', 'excluded_rows', 'effective_date', 'cash_consideration_per_old_share_usd',
    'additional_contingent_dividend_per_old_share_usd', 'quarter_checks_matched']} for r in segments], ensure_ascii=False, indent=2))
