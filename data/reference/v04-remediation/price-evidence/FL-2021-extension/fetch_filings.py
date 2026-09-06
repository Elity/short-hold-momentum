from pathlib import Path
import concurrent.futures
import hashlib
import json
import urllib.request
import urllib.error
from bs4 import BeautifulSoup

DEST = Path(__file__).parent
URLS = {
    '04-FL-2020-10K': 'https://www.sec.gov/Archives/edgar/data/850209/000085020921000003/fl-20210130x10k.htm',
    '05-FL-2021-10K': 'https://www.sec.gov/Archives/edgar/data/850209/000085020922000003/fl-20220129x10k.htm',
}
def fetch(item):
    name,url=item
    req=urllib.request.Request(url, headers={'User-Agent': 'SHM research document retrieval'})
    try:
        with urllib.request.urlopen(req,timeout=40) as response:
            body=response.read();status=response.status
    except urllib.error.HTTPError as exc:
        body=exc.read();status=exc.code
    (DEST/(name+'.html')).write_bytes(body)
    record={'name':name,'url':url,'status':status,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
    if status==200:
        soup=BeautifulSoup(body,'html.parser')
        for node in soup.select('script,style,ix\\:hidden'):
            node.decompose()
        text=' '.join(soup.stripped_strings)
        (DEST/(name+'.txt')).write_text(text)
    return record
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    rows=list(pool.map(fetch,URLS.items()))
(DEST/'filings-retrieval.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
