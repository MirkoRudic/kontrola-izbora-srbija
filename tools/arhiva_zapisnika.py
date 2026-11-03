# Arhiva zapisnika i rešenja sa RIK-a za ranije parlamentarne izbore (dodato 3.11.2026).
#   python tools/arhiva_zapisnika.py --izbori 2022 --dir D:\VAJB\kontrolaizbora\arhiva
#   python tools/arhiva_zapisnika.py --izbori 2020 --dir D:\VAJB\kontrolaizbora\arhiva
# Čita RIK-ovu bazu zapisnika (www.rik.parlament.gov.rs/zapisnici/<parent>), sve vrste dokumenata za sva BM,
# i preuzima svaki fajl (zapisnik RG-2, RG-7, RG-8, RG-9, ponovljeno glasanje, posmatrači…), uključujući starije verzije.
# Može da se prekine i ponovo pokrene: nastavlja gde je stao. Svako preuzimanje beleži i u revizioni dnevnik.
# Struktura: <dir>/<izbori>/spisak.json (sva BM i fajlovi sa RIK-a), <dir>/<izbori>/index.json (preuzeto), <dir>/<izbori>/pdf/<opština>/bmNNN_<tip>_<sha10>.pdf
# Samo standardna biblioteka Pythona.
import sys, os
if os.name == 'nt' and not sys.flags.utf8_mode:
    os.execv(sys.executable, [sys.executable, '-X', 'utf8'] + sys.argv)
import json, re, time, html, hashlib, argparse, datetime, threading, urllib.request, urllib.parse, http.cookiejar
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
IZB = {
    "2022": dict(parent="288966", round="42729", type=1, pet=0, url="/get-election", naziv="Parlamentarni izbori 3. 4. 2022"),
    "2020": dict(parent="8799", round="8796", type=0, pet=0, url="/get-election-archived", naziv="Parlamentarni izbori 21. 6. 2020"),
}
ap = argparse.ArgumentParser()
ap.add_argument('--izbori', required=True, choices=sorted(IZB))
ap.add_argument('--dir', required=True)
ap.add_argument('--threads', type=int, default=4)
ap.add_argument('--samo-spisak', action='store_true', help='samo spisak sa RIK-a, bez preuzimanja')
ap.add_argument('--strana-do', type=int, default=0, help='proba: samo prvih N strana spiska')
A = ap.parse_args()
C = IZB[A.izbori]; R = "https://www.rik.parlament.gov.rs"
D = os.path.join(A.dir, A.izbori); os.makedirs(os.path.join(D, "pdf"), exist_ok=True)
SPF, IXF, LOGF = os.path.join(D, "spisak.json"), os.path.join(D, "index.json"), os.path.join(D, "log.txt")
POSAO = "arhiva" + A.izbori
try:
    import revizija as REV
    REV.LOCAL = os.path.join(os.path.dirname(os.path.abspath(A.dir)), "revizija")
except Exception: REV = None
LOCK = threading.Lock()
def now(): return datetime.datetime.now().strftime("%d.%m. %H:%M:%S")
def log(*a):
    line = now() + " " + " ".join(str(x) for x in a); print(line, flush=True)
    with LOCK, open(LOGF, "a", encoding="utf-8") as f: f.write(line + "\n")
def rev(tip, **k):
    if REV:
        try: REV.zapisi(POSAO, tip, **k)
        except Exception: pass
def save(path, obj):
    with LOCK:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, path)
cj = http.cookiejar.CookieJar(); OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
OP.addheaders = [("User-Agent", "Mozilla/5.0 (kontrola-izbora)")]
def post(path, data, tries=6):
    for a in range(tries):
        try:
            rq = urllib.request.Request(R + path, data=urllib.parse.urlencode(data).encode(), headers={"X-Requested-With": "XMLHttpRequest"})
            return json.loads(OP.open(rq, timeout=90).read())
        except Exception as e:
            time.sleep(3 + a * 5)
    return None
def getbin(url, tries=5):
    sp = urllib.parse.urlsplit(url)
    u = urllib.parse.urlunsplit((sp.scheme, sp.netloc, urllib.parse.quote(urllib.parse.unquote(sp.path)), sp.query, ""))
    for a in range(tries):
        try:
            b = OP.open(urllib.request.Request(u), timeout=180).read()
            if b[:5] == b"%PDF-" or len(b) > 1000: return b
        except Exception: pass
        time.sleep(3 + a * 5)
    return None
# fajl: <div class=''><span>NASLOV</span></div> (samo 2022+) pa <div class='table-file [active]'><a href='LINK'>IME…</a><span>DATUM</span></div>
FRE = re.compile(r"(?:<span>([^<]*)</span></div>\s*)?<div class='table-file\s*(active)?\s*'>\s*<a href='([^']+)'[^>]*>([^<]*)(?:<span[^>]*></span>)?</a>\s*<span>([^<]*)</span>", re.S)
def files_of(rec):
    ex = rec.get("extfiles") or ""
    h = "".join(x.get("extfile", "") for x in ex) if isinstance(ex, list) else str(ex)
    out = []
    for t, act, l, nm, dt in FRE.findall(h):
        out.append(dict(tip=html.unescape(t).strip() or None, aktivan=bool(act), link=R + html.unescape(l), ime=html.unescape(nm).strip(), rik=dt.strip()))
    return out
def page(p):
    data = {"page": p, "election_type": 2, **{f"data[{k}]": v for k, v in dict(type=C["type"], parent=C["parent"], election_round=C["round"], property_election_type=C["pet"]).items()}}
    return post(C["url"], data)
# ---------- 1. spisak ----------
SP = json.load(open(SPF, encoding="utf-8")) if os.path.exists(SPF) else {"meta": {}, "strane": {}}
d = page(1)
if not d: log("RIK ne odgovara"); sys.exit(1)
N = max([int(x) for x in re.findall(r'data-page="(\d+)"', d.get("pagination") or "")] + [1])
if A.strana_do: N = min(N, A.strana_do)
SP["meta"] = dict(izbori=C["naziv"], parent=C["parent"], round=C["round"], strana=N, izvor=R + "/zapisnici/" + C["parent"])
log(f"{C['naziv']}: {N} strana spiska na RIK-u, već imam {len(SP['strane'])}")
rev("start", strana=N, imam=len(SP["strane"]))
def one_page(p):
    if str(p) in SP["strane"]: return 0
    x = d if p == 1 else page(p)
    if not x: return None
    recs = [dict(opstina=r.get("municipality"), n=str(r.get("election_station_number", "")).strip(), naziv=r.get("election_station_name"),
                 uid=r.get("uid"), datum=r.get("date_create"), fajlovi=files_of(r)) for r in (x.get("records") or [])]
    with LOCK: SP["strane"][str(p)] = recs
    return len(recs)
done = 0
with ThreadPoolExecutor(A.threads) as ex:
    for i, r in enumerate(ex.map(one_page, range(1, N + 1))):
        if r is None: log("strana", i + 1, "nije pročitana (pokušaću ponovo pri sledećem pokretanju)")
        done += 1
        if done % 50 == 0: save(SPF, SP); log(f"spisak: {len(SP['strane'])}/{N} strana")
save(SPF, SP)
BM = [r for p in sorted(SP["strane"], key=int) for r in SP["strane"][p]]
NF = sum(len(r["fajlovi"]) for r in BM)
log(f"spisak gotov: {len(SP['strane'])}/{N} strana, {len(BM)} BM, {NF} fajlova")
rev("spisak", strana=len(SP["strane"]), od=N, bm=len(BM), fajlova=NF)
if A.samo_spisak: sys.exit(0)
# ---------- 2. preuzimanje ----------
IX = json.load(open(IXF, encoding="utf-8")) if os.path.exists(IXF) else {}
slug = lambda s: re.sub(r"\W+", "_", s or "").strip("_")[:60] or "x"
def kind(t, ime):
    s = (t or "") + " " + (ime or "")
    m = re.search(r"РГ\s*-?\s*(\d+(?:-\d)?)", s)
    if "поновљен" in s or "поновн" in s: return "pon" + ("_rg" + m.group(1) if m else "")
    return ("rg" + m.group(1)) if m else ("rg2" if not t else "dok")
todo = [(r, f) for r in BM for f in r["fajlovi"] if f["link"] not in IX]
log(f"za preuzimanje: {len(todo)} fajlova (već preuzeto {len(IX)})")
t0 = time.time(); cnt = [0, 0, 0]
def dl(rf):
    r, f = rf
    b = getbin(f["link"])
    if not b: return rf, None
    sha = hashlib.sha256(b).hexdigest()
    n = re.sub(r"\D", "", r["n"]) or "0"
    rel = os.path.join("pdf", slug(r["opstina"]), f"bm{int(n):03d}_{kind(f['tip'], f['ime'])}{'' if f['aktivan'] else '_stari'}_{sha[:10]}.pdf")
    p = os.path.join(D, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh: fh.write(b)
    return rf, dict(sha=sha, fajl=rel.replace("\\", "/"), bajtova=len(b), at=now())
with ThreadPoolExecutor(A.threads) as ex:
    for (r, f), res in ex.map(dl, todo):
        if not res: cnt[1] += 1; log("NIJE preuzeto:", r["opstina"], "BM", r["n"], f["link"]); continue
        cnt[0] += 1; cnt[2] += res["bajtova"]
        IX[f["link"]] = dict(res, opstina=r["opstina"], n=r["n"], tip=f["tip"], aktivan=f["aktivan"], rik=f["rik"])
        rev("preuzet", opstina=r["opstina"], bm=r["n"], vrsta=f["tip"], aktivan=f["aktivan"], rik_vreme=f["rik"], link=f["link"], sha256=res["sha"], bajtova=res["bajtova"], fajl=res["fajl"])
        if cnt[0] % 100 == 0:
            save(IXF, IX)
            el = time.time() - t0; ost = (len(todo) - cnt[0] - cnt[1]) * el / max(1, cnt[0] + cnt[1])
            log(f"preuzeto {cnt[0]}/{len(todo)}, neuspelo {cnt[1]}, {cnt[2]/1e9:.1f} GB, još oko {ost/60:.0f} min")
            if REV: REV.posalji()
save(IXF, IX)
log(f"kraj: preuzeto {cnt[0]}, neuspelo {cnt[1]}, ukupno u arhivi {len(IX)} fajlova")
rev("kraj", preuzeto=cnt[0], neuspelo=cnt[1], ukupno=len(IX))
if REV: REV.posalji(True)
