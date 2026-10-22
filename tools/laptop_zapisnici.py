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
ap.add_argument('--site', default='https://kontrola-izbora-srbija.pages.dev')
A = ap.parse_args()
R = "https://www.rik.parlament.gov.rs"; ROUND = "341140" if A.sim else "680072"
D = A.dir; os.makedirs(D, exist_ok=True)
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
    except Exception as e: log("cookie greška", e)
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
IXF = os.path.join(D, "index.json")
INDEX = json.load(open(IXF, encoding="utf-8")) if os.path.exists(IXF) else {}
def save_index():
    tmp = IXF + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(INDEX, f, ensure_ascii=False)
    os.replace(tmp, IXF)

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

def save_pdf(uid, sid, link):
    s = UNITS[uid]["st"][sid]; hist = INDEX.setdefault(uid, {}).setdefault(sid, [])
    if hist and hist[-1]["link"] == link: return False
    b = getbin(link)
    if not b: log("PDF nije preuzet", UNITS[uid]["name"], "BM", s["n"]); return False
    sha = hashlib.sha256(b).hexdigest()
    if hist and hist[-1]["sha"] == sha: hist[-1]["link"] = link; return False
    fd = os.path.join(D, "2026", uid); os.makedirs(fd, exist_ok=True)
    fn = f"bm{s['n']:03d}_{sha[:10]}.pdf"
    with open(os.path.join(fd, fn), "wb") as f: f.write(b)
    hist.append(dict(link=link, sha=sha, file=f"2026/{uid}/{fn}", at=now().strftime("%d.%m. %H:%M"), bytes=len(b)))
    if len(hist) > 1: log("!!! ZAMENJEN ZAPISNIK:", UNITS[uid]["name"], "BM", s["n"], fn)
    return True

KNOWN = {uid: 0 for uid in UNITS}
interval = 5.0; recheck = []
while now() < UNTIL:
    t0 = time.time()
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
    new = 0
    def job(k):
        link = station(*k)
        return k, link
    with ThreadPoolExecutor(A.threads) as ex:
        for (uid, sid), link in ex.map(job, todo):
            if link and link != "ERR" and save_pdf(uid, sid, link): new += 1
    save_index()
    total = sum(len(v) for v in INDEX.values())
    interval = 30.0 if total >= sum(len(u["st"]) for u in UNITS.values()) else (max(1.0, interval / 2) if new else min(10.0, interval * 1.5))
    log(f"krug: upita {len(todo)}, novih zapisnika {new}, ukupno sačuvano {total}, sledeći za {interval:.1f} min")
    flush_logs()
    time.sleep(max(5, t0 + interval * 60 - time.time()))
log("kraj"); flush_logs(True)
