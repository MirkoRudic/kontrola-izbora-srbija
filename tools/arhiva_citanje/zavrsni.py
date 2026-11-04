# Završno čitanje 2020: stavke bez valjanog čitanja -> svaka strana PDF-a kao posebna slika
import json, os, sys, time, threading, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
import pypdfium2 as P
B='/tmp/k22/2020'; D=B+'/zavrsna'; S=json.load(open(B+'/stavke.json')); T=json.load(open('/tmp/k22/zavrsni.json'))
UA={'User-Agent':'Mozilla/5.0 (kontrola-izbora)'}; LK=threading.Lock()
def get(k):
    sp=urllib.parse.urlsplit(S[k]['link']); u=urllib.parse.urlunsplit((sp.scheme,sp.netloc,urllib.parse.quote(urllib.parse.unquote(sp.path)),'',''))
    for a in range(5):
        try:
            b=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=120).read()
            if b[:5]==b'%PDF-': return b
        except Exception: pass
        time.sleep(3+4*a)
def one(k):
    b=get(k)
    if not b: return k,[]
    out=[]
    with LK:
        pdf=P.PdfDocument(b)
        for i in range(min(len(pdf),8)):
            im=pdf[i].render(scale=150/72).to_pil(); im.thumbnail((2000,2000)); f=f'{D}/img/{k}_{i+1}.jpg'; im.convert('L').save(f,quality=75); out.append(f)
        pdf.close()
    return k,out
OUT=[]
with ThreadPoolExecutor(6) as ex:
    for k,o in ex.map(one,T):
        if o: OUT.append(dict(id=k,opstina=S[k]['opstina'],n=S[k]['n'],slike=o))
OUT.sort(key=lambda x:(x['opstina'],x['n']))
for i in range(0,len(OUT),12): json.dump(OUT[i:i+12],open(f'{D}/serijaZ_{i//12+1:03d}.json','w'),ensure_ascii=False)
print('kraj',len(OUT),'od',len(T),'serija',(len(OUT)+11)//12)
