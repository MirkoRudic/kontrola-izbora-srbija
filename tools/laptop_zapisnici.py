# Laptop (Windows), izborna noć: nezavisno prati RIK i čuva ORIGINALNE zapisnike 2026 na disk.
#   python tools\laptop_zapisnici.py --dir D:\VAJB\kontrolaizbora\zapisnici [--until 2026-10-26T09:00] [--sim]
# Samo standardna biblioteka Pythona (bez pip). Ne objavljuje ništa – to radi GitHub posao (rik_live.py).
# Struktura: <dir>\2026\<opstina_id>\bm<NNN>_<sha10>.pdf  +  <dir>\index.json  +  <dir>\log.txt
import sys, os
if os.name == 'nt' and not sys.flags.utf8_mode:  # Windows: naša slova u fajlovima
    os.execv(sys.executable, [sys.executable, '-X', 'utf8'] + sys.argv)
import json, os, sys, time, re, hashlib, argparse, datetime, threading, random
import urllib.request, urllib.parse, http.cookiejar
from concurrent.futures import ThreadPoolExecutor
ap = argparse.ArgumentParser()
ap.add_argument('--dir', required=True)
ap.add_argument('--until', default='2026-10-26T09:00')
ap.add_argument('--sim', action='store_true', help='proba na izborima 2023')
ap.add_argument('--threads', type=int, default=6)
ap.add_argument('--mirror', default=None, help='druga kopija (npr. Google Drive); ako nije data, čita se iz <dir>/../zadaci/mirror.txt')
ap.add_argument('--site', default='https://kontrola-izbora-srbija.pages.dev')
# RIK baza zapisnika (www.rik.parlament.gov.rs/zapisnici/<parent>): zapisnici se tu pojavljuju PRE rezultata (25.10. prvi u 20:38, rezultati tek posle 21:07)
ap.add_argument('--zap-parent', default='779676', help='ID strane „Записници” za ove izbore (prazno = ne koristi bazu)')
ap.add_argument('--zap-round', default='680072')
ap.add_argument('--proba-baza', type=int, default=0, help='samo proba: pročitaj bazu za prvih N opština, ništa ne preuzimaj, izađi')
A = ap.parse_args()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dnevnik as _DN
if not _DN.jedini("zapisnici" + ("-proba" if A.sim else "")): print("arhiva već radi – izlazim"); sys.exit(0)
R = "https://www.rik.parlament.gov.rs"; ROUND = "341140" if A.sim else "680072"
D = A.dir; os.makedirs(D, exist_ok=True)
import revizija as REV  # revizioni dnevnik: kad je šta pročitano/preuzeto (lokalno odmah + zaštićena grana 'revizija')
REV.LOCAL = os.path.join(os.path.dirname(os.path.abspath(D)), "revizija")
POSAO = "zapisnici" + ("-proba" if A.sim else "")
def _tz():
    n = datetime.datetime.utcnow()
    return datetime.timezone(datetime.timedelta(hours=1 if n >= datetime.datetime(2026, 10, 25, 1, 0) else 2))  # CEST->CET 25.10. u 03:00
TZ = _tz()
def now(): return datetime.datetime.now(TZ)
UNTIL = datetime.datetime.fromisoformat(A.until).replace(tzinfo=TZ)
LOCK = threading.Lock()
def log(*a):
    line = now().strftime("%d.%m. %H:%M:%S") + " " + " ".join(str(x) for x in a)
    print(line, flush=True)
    with LOCK, open(os.path.join(D, "log.txt"), "a", encoding="utf-8") as f: f.write(line + "\n")
    with LOCK: LOGBUF.append(" ".join(str(x) for x in a))
LOGBUF = []; _LASTLOG = [0.0]
def flush_logs(force=False):
    """Dnevnik na GitHub (grana uzivo, logovi/laptop-zapisnici.log) na 10 min."""
    if not LOGBUF or (not force and time.time() - _LASTLOG[0] < 600): return
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import dnevnik as DN
        lines = LOGBUF[:]
        if DN.push_logs({"laptop-zapisnici": lines}): del LOGBUF[:len(lines)]
    except Exception as e: print("dnevnik greška:", e)
    _LASTLOG[0] = time.time()

cj = http.cookiejar.CookieJar(); OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
OP.addheaders = [("User-Agent", "Mozilla/5.0 (kontrola-izbora)")]
def cookie():
    try: OP.open(R + "/542645/rezultati/", timeout=60).read()
    except Exception as e: log("cookie greška", e); REV.zapisi(POSAO, "greska", gde_u_kodu="cookie", poruka=str(e)[:200])
def post(path, data, tries=5):
    for a in range(tries):
        try:
            rq = urllib.request.Request(R + path, data=urllib.parse.urlencode(data).encode(),
                                        headers={"X-Requested-With": "XMLHttpRequest", "Referer": R + "/542645/rezultati/"})
            return json.loads(OP.open(rq, timeout=60).read())
        except Exception:
            time.sleep(2 + a * 3)
            if a == 2: cookie()
    return None
def getbin(url, tries=4):
    for a in range(tries):
        try:
            b = OP.open(urllib.request.Request(url), timeout=120).read()
            if b[:5] == b"%PDF-": return b
        except Exception: pass
        time.sleep(3 + a * 4)
    return None
def getjson(url):
    if not url.startswith("http"): return json.load(open(url, encoding="utf-8"))
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(url + "?t=" + str(int(time.time())), headers={"User-Agent": "Mozilla/5.0 (kontrola-izbora)"}), timeout=60).read())
    except Exception as e: log("ne mogu da učitam", url, e); return None
num = lambda x: int(str(x).replace('.', '') or 0)

# ---------- spisak BM (sa našeg sajta) ----------
IDX = getjson(A.site + "/data/index.json")
if not IDX: sys.exit("Nema index.json – proveri internet.")
UNITS = {}
for uid, u in IDX["units"].items():
    uf = getjson(f"{A.site}/data/u/{uid}.json")
    if uf: UNITS[uid] = dict(region=u["region"], name=u["short"], st={s["sid"]: s for s in uf["stations"]})
log("BM ukupno", sum(len(u["st"]) for u in UNITS.values()), "jedinica", len(UNITS), "SIM" if A.sim else "")
# druga kopija zapisnika (Google Drive): <mirror>\<ime foldera dir>\..., greške ne zaustavljaju posao
MIR = A.mirror
if not MIR:
    _mf = os.path.join(os.path.dirname(os.path.abspath(D)), "zadaci", "mirror.txt")
    if os.path.exists(_mf): MIR = open(_mf, encoding="utf-8-sig").read().strip() or None
if MIR: MIR = os.path.join(MIR, os.path.basename(os.path.abspath(D)))
MIR_PEND = []
def mirror(rel):
    if not MIR: return True
    import shutil
    try:
        dst = os.path.join(MIR, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(os.path.join(D, rel)):
            shutil.copy2(os.path.join(D, rel), dst + ".tmp"); os.replace(dst + ".tmp", dst)
        return True
    except Exception as e:
        with LOCK:
            if rel not in MIR_PEND: MIR_PEND.append(rel)
        return False
def mirror_catchup():
    if not MIR: return
    n = bad = 0
    for root, _, fs in os.walk(D):
        for f in fs:
            if f.endswith(".pdf"):
                rel = os.path.relpath(os.path.join(root, f), D); n += 1
                if not mirror(rel): bad += 1
    log("kopija na", MIR, "– proverenih", n, "neuspelih", bad)
if MIR: threading.Thread(target=mirror_catchup, daemon=True).start()
IXF = os.path.join(D, "index.json")
INDEX = json.load(open(IXF, encoding="utf-8")) if os.path.exists(IXF) else {}
def save_index():
    tmp = IXF + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(INDEX, f, ensure_ascii=False)
    os.replace(tmp, IXF)

_LASTIX = [time.time()]
T0 = time.time()
def unit_processed(uid):
    if A.sim:
        frac = min(1.0, (time.time() - T0) / (40 * 60)); return int(len(UNITS[uid]["st"]) * frac)
    d = post("/get_results/", dict(should_update_pies=1, type=2, election_round=ROUND, region=UNITS[uid]["region"], municipality=uid, election_station=0))
    return num(((d or {}).get("stat_sum_numbers") or {}).get("processed_stations", 0)) if d else None

def station(uid, sid):
    s = UNITS[uid]["st"][sid]
    q = s.get("m23") if A.sim else sid
    if not q: return None
    d = post("/get_results/", dict(should_update_pies=1, type=2, election_round=ROUND, region=UNITS[uid]["region"], municipality=uid, election_station=q))
    if not d: return "ERR"
    m = re.search(r"href='([^']+)'", d.get("minute_from_election_station") or "")
    return (R + urllib.parse.quote(m.group(1))) if m else None

def save_pdf(uid, sid, link, b=None, izvor="rezultati", rik_vreme=None):
    s = UNITS[uid]["st"][sid]; hist = INDEX.setdefault(uid, {}).setdefault(sid, [])
    if hist and hist[-1]["link"] == link: return False
    b = b or getbin(link)
    if not b: log("PDF nije preuzet", UNITS[uid]["name"], "BM", s["n"]); return False
    sha = hashlib.sha256(b).hexdigest()
    if hist and hist[-1]["sha"] == sha: hist[-1]["link"] = link; return False
    fd = os.path.join(D, "2026", uid); os.makedirs(fd, exist_ok=True)
    fn = f"bm{s['n']:03d}_{sha[:10]}.pdf"
    with open(os.path.join(fd, fn), "wb") as f: f.write(b)
    mirror(os.path.join("2026", uid, fn))
    hist.append(dict(link=link, sha=sha, file=f"2026/{uid}/{fn}", at=now().strftime("%d.%m. %H:%M"), bytes=len(b)))
    REV.zapisi(POSAO, "preuzet", opstina_id=uid, opstina=UNITS[uid]["name"], bm=s["n"], sid=sid, izvor=izvor, rik_vreme=rik_vreme,
               link=link, sha256=sha, bajtova=len(b), fajl=f"2026/{uid}/{fn}", zamena=len(hist) > 1)
    if len(hist) > 1: log("!!! ZAMENJEN ZAPISNIK:", UNITS[uid]["name"], "BM", s["n"], fn)
    return True

# ---------- RIK baza zapisnika: RG-2 po opštini, nezavisno od rezultata (dodato 1.11.2026) ----------
# 25.10. smo zapisnike tražili samo preko rezultata, pa je prvi preuzet tek u 21:31, a RIK ih je kačio od 20:38.
ZAP = None if (A.sim or not A.zap_parent) else {f"data[{k}]": v for k, v in dict(type=1, parent=A.zap_parent, election_round=A.zap_round, property_election_type=2).items()}
_FREF = re.compile(r"<span>([^<]*)</span></div>\s*<div class='table-file[^']*'><a href='([^']+)'", re.S)
def baza_opstina(uid):
    """[(sid, link)] za sva BM opštine čiji RG-2 postoji u bazi zapisnika; None ako RIK ne odgovori."""
    byn = {int(s["n"]): sid for sid, s in UNITS[uid]["st"].items() if str(s.get("n", "")).isdigit()}
    out, page = [], 1
    while True:
        d = post("/get-election", {"page": page, "election_type": 2, "filters[municipality]": uid, "filters[election_document_type]": 6, **ZAP}, tries=3)
        if d is None: return None
        rec = d.get("records") or []
        for r in rec:
            ex = r.get("extfiles") or []
            h = "".join(x.get("extfile", "") for x in ex) if isinstance(ex, list) else str(ex)
            files = _FREF.findall(h)
            pick = next((l for t, l in files if "РГ-2" in t or "RG-2" in t or "раду бирачког" in t), files[0][1] if files else None)
            try: sid = byn.get(int(str(r.get("election_station_number", "")).strip()))
            except ValueError: sid = None
            if sid and pick:
                rv = next((x.get("date") for x in ex if isinstance(x, dict) and pick in x.get("extfile", "")), None) if isinstance(ex, list) else None
                out.append((sid, R + urllib.parse.quote(pick), rv))
        pages = [int(x) for x in re.findall(r'data-page="(\d+)"', d.get("pagination") or "")]
        if not rec or page >= max(pages + [1]): return out
        page += 1
def baza_krug():
    """Preuzmi RG-2 koje još nemamo, za opštine koje nisu kompletne. Vraća (upita_opština, novih)."""
    units = [u for u in UNITS if len(INDEX.get(u, {})) < len(UNITS[u]["st"])]
    nov = 0
    with ThreadPoolExecutor(A.threads) as ex:
        lists = list(ex.map(baza_opstina, units))
    todo = [(u, sid, l, rv) for u, L in zip(units, lists) if L for sid, l, rv in L if sid not in INDEX.get(u, {})]
    with ThreadPoolExecutor(A.threads) as ex:  # preuzimanje paralelno, upis u INDEX samo ovde (glavna nit)
        for (u, sid, l, rv), b in ex.map(lambda t: (t, getbin(t[2])), todo):
            if b and save_pdf(u, sid, l, b, izvor="baza", rik_vreme=rv):
                nov += 1
                if time.time() - _LASTIX[0] > 30: save_index(); mirror("index.json"); _LASTIX[0] = time.time()
    if None in lists: log("baza zapisnika: bez odgovora za", lists.count(None), "opština")
    REV.zapisi(POSAO, "baza_procitana", opstina=len(units), bez_odgovora=lists.count(None), u_bazi=sum(len(L) for L in lists if L), novih=nov)
    return len(units), nov
if A.proba_baza:
    if not ZAP: sys.exit("baza zapisnika isključena (--sim ili prazan --zap-parent)")
    for uid in list(UNITS)[:A.proba_baza]:
        L = baza_opstina(uid)
        print(UNITS[uid]["name"], "BM", len(UNITS[uid]["st"]), "u bazi", None if L is None else len(L), (L or [("", "")])[0][1][-60:])
    sys.exit(0)

KNOWN = {uid: 0 for uid in UNITS}
interval = 5.0; recheck = []
while now() < UNTIL:
    t0 = time.time()
    bnov = 0
    if ZAP:
        bu, bnov = baza_krug()
        if bnov: log(f"baza zapisnika: {bnov} novih (proverenih opština {bu})")
    with ThreadPoolExecutor(A.threads) as ex: ag = dict(zip(UNITS, ex.map(unit_processed, UNITS)))
    todo = []
    for uid, p in ag.items():
        if p is None: continue
        have = len(INDEX.get(uid, {}))
        if p > have or p > KNOWN[uid]:
            todo += [(uid, sid) for sid in UNITS[uid]["st"] if sid not in INDEX.get(uid, {})]
        KNOWN[uid] = p
    if not recheck: recheck = [(u, s) for u in INDEX for s in INDEX[u]]; random.shuffle(recheck)
    todo += recheck[:120]; recheck = recheck[120:]   # spora provera već sačuvanih (zamenjen zapisnik?)
    new = bnov
    def job(k):
        link = station(*k)
        return k, link
    with ThreadPoolExecutor(A.threads) as ex:
        for (uid, sid), link in ex.map(job, todo):
            if link and link != "ERR" and save_pdf(uid, sid, link):
                new += 1
                if time.time() - _LASTIX[0] > 30:  # čitanje (laptop_citanje) ne sme da čeka kraj dugog kruga
                    save_index(); mirror("index.json"); _LASTIX[0] = time.time()
                    if new % 100 < 5: log(f"  … u toku kruga: novih {new} od {len(todo)} upita")
    save_index(); mirror("index.json")
    if MIR_PEND:
        with LOCK: pend = MIR_PEND[:]; MIR_PEND.clear()
        bad = sum(not mirror(r) for r in pend)
        if bad: log("kopija na Drive: još", bad, "fajlova čeka (Drive nedostupan?)")
    total = sum(len(v) for v in INDEX.values())
    interval = 30.0 if total >= sum(len(u["st"]) for u in UNITS.values()) else (max(1.0, interval / 2) if new else min(5.0, interval * 1.5))
    log(f"krug: upita {len(todo)}, novih zapisnika {new}, ukupno sačuvano {total}, sledeći za {interval:.1f} min")
    REV.zapisi(POSAO, "krug", pocetak=datetime.datetime.fromtimestamp(t0, TZ).isoformat(timespec="seconds"), trajanje_s=round(time.time() - t0),
               opstina_sa_rezultatima=sum(1 for p in ag.values() if p), rik_bez_odgovora=sum(1 for p in ag.values() if p is None),
               upita=len(todo), novih=new, ukupno=total, sledeci_min=interval)
    flush_logs(); REV.posalji()
    time.sleep(max(5, t0 + interval * 60 - time.time()))
log("kraj"); flush_logs(True); REV.zapisi(POSAO, "kraj"); REV.posalji(True)
