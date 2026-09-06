from pathlib import Path
import concurrent.futures,hashlib,json,urllib.request,urllib.error
DEST=Path(__file__).parent
sources={
 '09-issuer-2020-annual':'https://www.footlocker-inc.com/content/dam/flincfoundation/footlockerinc_documents/annual-reports/Foot_Locker_2020_Annual_Report%20FINAL%20Post.pdf',
 '10-issuer-2021-annual':'https://investors.footlocker-inc.com/static-files/8293fa73-de5e-4e36-a8be-c5bf476f2bcd',
}
def fetch(item):
 name,url=item
 try:
  with urllib.request.urlopen(url,timeout=40) as r:
   data=r.read();status=r.status;final=r.url
 except urllib.error.HTTPError as e:
  data=e.read();status=e.code;final=e.url
 pdf=data.startswith(b'%PDF-')
 path=DEST/(name+('.pdf' if pdf else '.response'))
 path.write_bytes(data)
 return {'file':path.name,'url':url,'final_url':final,'status':status,'pdf':pdf,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 result=list(pool.map(fetch,sources.items()))
(DEST/'issuer-reports-retrieval.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
