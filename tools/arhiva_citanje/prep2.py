# Druga runda: zapisnici čiji zbir ne odgovara (ili ima nečitkih polja) – veće slike za ponovno čitanje.
#   python3 prep2.py 2022  -> /tmp/k22/<Y>/druga/stavke2.json + slike, serije2_NNN.json po 25
import json, glob, os, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
import pypdfium2 as P
from PIL import Image
sys.path.insert(0, '/tmp/k22'); from komp import komp20
Y = sys.argv[1]; B = f'/tmp/k22/{Y}'; D = B + '/druga'; os.makedirs(D + '/img', exist_ok=True)
S = json.load(open(B + '/stavke.json'))
R = {}
for f in sorted(glob.glob(B + '/rez_*.json')):
    ids = {x['id'] for x in json.load(open(f.replace('rez_', 'serija_')))}
    for r in json.load(open(f)):
        if r['id'] in ids: R[r['id']] = r
def los(r):
    if r.get('nije_procitano'): return False
    L = r.get('liste') or []
    if r.get('vazeci') is None or not L or any(x is None for x in L): return True
    if sum(int(x or 0) for x in L) != r['vazeci']: return True
    uk, iv = r.get('u_kutiji'), r.get('nevazeci')
    return uk is not None and iv is not None and uk != iv + r['vazeci']
P2 = [k for k, r in R.items() if los(r)]
print('druga runda', len(P2), flush=True)
UA = {'User-Agent': 'Mozilla/5.0 (kontrola-izbora)'}
def get(k):
    v = S[k]; sp = urllib.parse.urlsplit(v['link']); u = urllib.parse.urlunsplit((sp.scheme, sp.netloc, urllib.parse.quote(urllib.parse.unquote(sp.path)), '', ''))
    for a in range(5):
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()
            if b[:5] == b'%PDF-': return b
        except Exception: pass
        time.sleep(3 + 4 * a)
def one(k):
    b = get(k)
    if not b: return k, None
    pp = f'/tmp/k22/tmp2_{k}.pdf'; open(pp, 'wb').write(b); out = []
    try:
        if Y == '2020':
            komp20(pp, f'{D}/img/{k}_a.jpg', dpi=190); out = [f'{D}/img/{k}_a.jpg']
        else:
            pdf = P.PdfDocument(pp); im = pdf[0].render(scale=200 / 72).to_pil(); W, H = im.size
            if W < H:
                for i in range(min(2, len(pdf))):
                    p_ = pdf[i].render(scale=170 / 72).to_pil(); f = f'{D}/img/{k}_{"ab"[i]}.jpg'; p_.convert('L').save(f, quality=78); out.append(f)
            else:
                A = im.crop((0, int(H*.10), int(W*.50), int(H*.42))); Bc = im.crop((0, int(H*.62), int(W*.50), int(H*.90)))
                c = Image.new('RGB', (A.width, A.height + Bc.height + 20), 'white'); c.paste(A, (0, 0)); c.paste(Bc, (0, A.height + 20))
                c.convert('L').save(f'{D}/img/{k}_a.jpg', quality=78)
                im.crop((int(W*.5), int(H*.03), W, int(H*.76))).convert('L').save(f'{D}/img/{k}_b.jpg', quality=78)
                out = [f'{D}/img/{k}_a.jpg', f'{D}/img/{k}_b.jpg']
            pdf.close()
    except Exception as e: out = []
    os.remove(pp); return k, out
OUT = {}
with ThreadPoolExecutor(8) as ex:
    for k, o in ex.map(one, P2):
        if o: OUT[k] = dict(id=k, opstina=S[k]['opstina'], n=S[k]['n'], slike=o, prvo=R[k])
json.dump(OUT, open(D + '/stavke2.json', 'w'), ensure_ascii=False)
ks = sorted(OUT, key=lambda k: (OUT[k]['opstina'], OUT[k]['n']))
for i in range(0, len(ks), 25):
    json.dump([OUT[k] for k in ks[i:i + 25]], open(f'{D}/serija2_{i // 25 + 1:03d}.json', 'w'), ensure_ascii=False)
print('kraj', len(OUT), 'serija', (len(ks) + 24) // 25)
