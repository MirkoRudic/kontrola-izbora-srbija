# Preuzme aktivne RG-2 zapisnike iz spiska i napravi isečke za čitanje (jpg); PDF briše.
import json, os, re, sys, hashlib, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '/tmp/k22'); from komp import komp, komp20
Y = sys.argv[1]; SP = json.load(open(f'/tmp/arhc/{Y}/spisak.json')); OUT = f'/tmp/k22/{Y}'; os.makedirs(OUT + '/img', exist_ok=True)
IXF = OUT + '/stavke.json'; IX = json.load(open(IXF)) if os.path.exists(IXF) else {}
def rg2(f):
    t = f.get('tip') or ''
    return f['aktivan'] and 'поновљен' not in t and ('РГ-2' in t or (not t and not re.search(r'РГ|RG|PG', f['ime'] or '', re.I)) or (not t and re.search(r'РГ\s*-?\s*2|RG\s*-?\s*2', f['ime'] or '')))
jobs = []
for p in sorted(SP['strane'], key=int):
    for r in SP['strane'][p]:
        fs = [f for f in r['fajlovi'] if rg2(f)]
        if not fs: continue
        f = fs[0]; k = hashlib.md5(f['link'].encode()).hexdigest()[:12]
        if k in IX: continue
        jobs.append((k, r, f))
print('za pripremu', len(jobs), flush=True)
UA = {'User-Agent': 'Mozilla/5.0 (kontrola-izbora)'}
def one(j):
    k, r, f = j
    sp = urllib.parse.urlsplit(f['link']); u = urllib.parse.urlunsplit((sp.scheme, sp.netloc, urllib.parse.quote(urllib.parse.unquote(sp.path)), '', ''))
    for a in range(5):
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()
            if b[:5] == b'%PDF-': break
        except Exception: pass
        time.sleep(3 + 4 * a)
    else: return k, None
    pp = f'/tmp/k22/tmp_{k}.pdf'; open(pp, 'wb').write(b)
    try: o = (komp20 if Y == '2020' else komp)(pp, f'{OUT}/img/{k}.jpg')
    except Exception as e: o = 'greska ' + str(e)[:80]
    os.remove(pp)
    return k, dict(opstina=r['opstina'], n=r['n'], naziv=r['naziv'], link=f['link'], rik=f['rik'], sha=hashlib.sha256(b).hexdigest(), orijentacija=o, img=f'{OUT}/img/{k}.jpg')
done = 0
with ThreadPoolExecutor(8) as ex:
    for k, v in ex.map(one, jobs):
        done += 1
        if v: IX[k] = v
        if done % 200 == 0:
            json.dump(IX, open(IXF + '.t', 'w'), ensure_ascii=False); os.replace(IXF + '.t', IXF); print(done, len(IX), flush=True)
json.dump(IX, open(IXF + '.t', 'w'), ensure_ascii=False); os.replace(IXF + '.t', IXF); print('kraj', len(IX))
