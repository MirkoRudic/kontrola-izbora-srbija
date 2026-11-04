# Završna popravka 2020 (posle prep.py): proveri broj strana jednog zapisnika u SVAKOJ opštini; za opštine sa >=4 strane
# ponovo pripremi sve nepročitane stavke (osim onih u obradi).
import json, glob, os, sys, time, urllib.request, urllib.parse, collections
from concurrent.futures import ThreadPoolExecutor
import pypdfium2 as P
sys.path.insert(0, '/tmp/k22'); from komp import komp20
B = '/tmp/k22/2020'; S = json.load(open(B + '/stavke.json'))
done = set()
for f in glob.glob(B + '/rez_*.json'):
    R = json.load(open(f)); keep = [r for r in R if not r.get('nije_procitano')]
    if len(keep) != len(R): json.dump(keep, open(f, 'w'), ensure_ascii=False)
    done |= {r['id'] for r in keep}
busy = set()
for f in glob.glob(B + '/serija_*.json'):
    if not os.path.exists(f.replace('serija_', 'rez_')): busy |= {x['id'] for x in json.load(open(f))}
UA = {'User-Agent': 'Mozilla/5.0 (kontrola-izbora)'}
def get(k):
    v = S[k]; sp = urllib.parse.urlsplit(v['link']); u = urllib.parse.urlunsplit((sp.scheme, sp.netloc, urllib.parse.quote(urllib.parse.unquote(sp.path)), '', ''))
    for a in range(5):
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()
            if b[:5] == b'%PDF-': return b
        except Exception: pass
        time.sleep(3 + 4 * a)
T = os.path.getmtime('/tmp/k22/komp.py')
redo = sorted(k for k, v in S.items() if k not in done and k not in busy and (not os.path.exists(v['img']) or os.path.getmtime(v['img']) < T))
print('ponovo', len(redo), flush=True)
def one(k):
    b = get(k)
    if not b: return k, None
    pp = f'/tmp/k22/tmp_{k}.pdf'; open(pp, 'wb').write(b)
    try: o = komp20(pp, S[k]['img'])
    except Exception as e: o = 'greska ' + str(e)[:80]
    os.remove(pp); return k, o
c = collections.Counter()
with ThreadPoolExecutor(8) as ex:
    for i, (k, o) in enumerate(ex.map(one, redo)):
        if o: S[k]['orijentacija'] = o; c[o] += 1
        if i % 200 == 0:
            print(i, flush=True); json.dump(S, open(B + '/stavke.json.t', 'w'), ensure_ascii=False); os.replace(B + '/stavke.json.t', B + '/stavke.json')
json.dump(S, open(B + '/stavke.json.t', 'w'), ensure_ascii=False); os.replace(B + '/stavke.json.t', B + '/stavke.json'); print('kraj', c, flush=True)
