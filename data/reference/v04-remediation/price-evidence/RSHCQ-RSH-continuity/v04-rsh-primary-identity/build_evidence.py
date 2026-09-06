"""Extract already-returned public source text and compare finite quarterly prices."""
from pathlib import Path
import json, re, hashlib
import pandas as pd

BASE=Path('/Users/fighting/Documents/Codex/2026-09-06/co-2/work/v04-rsh-primary-identity')
documents=[]
for path in sorted(BASE.glob('0[1-4]-*.json')):
    data=json.loads(path.read_text()); response=data['response']
    payload=response.get('structuredContent') or json.loads(next(c['text'] for c in response['content'] if c['type']=='text'))
    documents.extend({'request':data['request_number'],'response_file':path.name,**item} for item in payload['webResults'])
selected=[
    ('SEC-2015-delisting.indexed.txt', 'form8k020615.htm', 'SEC primary filing text retrieved through search index'),
    ('NYSE-2015-RSH-delisting.indexed.txt', 'ir.theice.com', 'Exchange primary announcement text retrieved through search index'),
    ('OCC-RSH-to-RSHC-36153.indexed.txt', 'RSH_Symbol_Change_36153.pdf', 'OCC memo hosted by MIAX, indexed text; underlying identity only, not a settlement price'),
    ('2010-SEC-10K.indexed.txt', 'form10k123110.htm', 'SEC 2010 annual filing indexed excerpt capped at130000 chars; not full original HTML download'),
    ('2010-issuer-dividend.indexed.txt', 'declares-dividend-106915723', 'Issuer release via PRNewswire indexed text'),
    ('Hilco-RSHCQ-sale.indexed.txt', 'RadioShack-Intellectual-Property-Sells-For-Over-26MM', 'Contemporaneous liquidator GlobeNewswire release republished by MarketScreener'),
    ('GeneralWireless-brand-purchase.indexed.txt', 'general-wireless-acquires-the-radioshack-brand-300107296', 'Buyer-issued PRNewswire release indexed text'),
    ('MarketBeat-RSHCQ-profile.indexed.txt', 'marketbeat.com/stocks/OTCMKTS/RSHCQ/', 'Secondary current profile; only historical-symbol and CIK fields used'),
    ('GeneralWireless-asset-contract.mirror.txt', 'contracts.justia.com', 'Asset purchase agreement exhibit mirrored by Justia; site summary not used'),
]
index=[]
for filename,needle,level in selected:
    item=next(x for x in documents if needle in x['url'])
    path=BASE/filename; path.write_text(item['content'])
    index.append({'file':filename,'url':item['url'],'title':item['title'],'source_level':level,
                  'request_number':item['request'],'response_file':item['response_file'],
                  'chars':len(item['content']),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(BASE/'source-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
text=(BASE/'2010-SEC-10K.indexed.txt').read_text()
start=text.index('PRICE RANGE OF COMMON STOCK'); end=text.index('HOLDERS OF RECORD',start)
section=text[start:end]
(BASE/'2010-SEC-quarter-price-table.excerpt.txt').write_text(section+'\n')
pattern=r'(December 31|September 30|June 30|March 31), (2009|2010)\s+\$?\s*([\d.]+)\s+\$?\s*([\d.]+)\s+(?:\$?\s*([\d.]+)|--)'
parsed=re.findall(pattern,section)
wiki=pd.read_parquet(BASE.parent/'v04-rsh-identity-preflight/RSH-WIKI-source.parquet')
wiki['date']=pd.to_datetime(wiki.date)
rows=[]
for monthday,year,high,low,dividend in parsed:
    end=pd.Timestamp(f'{monthday}, {year}'); start=end.to_period('Q').start_time
    block=wiki[wiki.date.between(start,end)]
    wh=float(block.high.max()); wl=float(block.low.min())
    rows.append({'quarter':str(end.to_period('Q')),'SEC_high':float(high),'SEC_low':float(low),
                 'SEC_declared_dividend_for_quarter':float(dividend or 0),
                 'WIKI_high':wh,'WIKI_low':wl,'high_difference':wh-float(high),'low_difference':wl-float(low),
                 'match_within_cent':abs(wh-float(high))<.011 and abs(wl-float(low))<.011})
pd.DataFrame(rows).to_csv(BASE/'SEC-2009-2010-quarter-price-check.csv',index=False)
print(pd.DataFrame(rows).to_string(index=False))
print('Matched',sum(row['match_within_cent'] for row in rows),'/',len(rows))
