# Izborna noć: prati RIK i objavljuje rezultate po BM za celu Srbiju.
#   python3 tools/rik_live.py [--minutes 55] [--sim] [--out public/data/live] [--no-push]
# Svaki krug: 191 upit za zbir po opštini (broj obrađenih + vreme ažuriranja) -> detaljno samo nova BM
# + spora rotacija već obrađenih BM (provera izmena rezultata / zamenjenog zapisnika).
# Objava: svaka promena (najviše na 2 min) na granu 'uzivo'; na main (Cloudflare) 21-02 h na 15 min, inače na sat.
# Interval: start 5 min; ima novih -> pola (min 1); nema -> x1.5 (max 15); sve obrađeno -> 30.
# --sim: proba na izborima 2023 (stanica 2026 -> uparena stanica 2023), BM se "otkrivaju" postepeno.
import sys, os
if os.name == 'nt' and not sys.flags.utf8_mode:  # Windows: naša slova u fajlovima
    os.execv(sys.executable, [sys.executable, '-X', 'utf8'] + sys.argv)
import json, os, sys, time, re, subprocess, random, datetime, argparse, hashlib, tempfile
from concurrent.futures import ThreadPoolExecutor
try:
    from zoneinfo import ZoneInfo; _TZ = ZoneInfo("Europe/Belgrade")
except Exception:  # Windows bez tzdata
    _TZ = None
def _tz():
    if _TZ: return _TZ
    n = datetime.datetime.utcnow()
    return datetime.timezone(datetime.timedelta(hours=1 if n >= datetime.datetime(2026, 10, 25, 1, 0) else 2))
ap = argparse.ArgumentParser()
ap.add_argument('--minutes', type=float, default=55)
ap.add_argument('--sim', action='store_true')
ap.add_argument('--out', default='public/data/live')
ap.add_argument('--no-push', action='store_true')
ap.add_argument('--threads', type=int, default=8)
ap.add_argument('--standby', action='store_true', help='rezerva (laptop): radi samo ako GitHub posao kasni > 3 min')
ap.add_argument('--reset', action='store_true', help='kreni od nule (obriši prethodno stanje, ne nastavljaj sa grane uzivo)')
ap.add_argument('--tg-demo', action='store_true', help='pošalji probne Telegram poruke i izađi')
ap.add_argument('--fast', action='store_true', help='kratki intervali (za test)')
A = ap.parse_args()
if A.reset:
    import shutil; shutil.rmtree(A.out, ignore_errors=True)
R = "https://www.rik.parlament.gov.rs"; CK = os.path.join(tempfile.gettempdir(), "rik_ck")
ROUND = "341140" if A.sim else "680072"
OUT = A.out; os.makedirs(OUT + "/u", exist_ok=True)
now = lambda: datetime.datetime.now(_tz())
stamp = lambda: now().strftime("%d.%m. %H:%M")
LOGBUF = []
def log(*a):
    t = " ".join(str(x) for x in a)
    print(now().strftime("%H:%M:%S"), t, flush=True)
    LOGBUF.append(t)
    if len(LOGBUF) > 3000: del LOGBUF[:1000]

def curl(args, t=40):
    return subprocess.run(["curl", "-sS", "--http1.1", "--max-time", str(t)] + args, capture_output=True, text=True).stdout
def cookie(): curl(["--retry", "5", "--retry-all-errors", "-c", CK, "-o", "/dev/null", R + "/542645/rezultati/"])
def post(path, data, tries=5):
    args = ["-b", CK, "-X", "POST", "-H", "X-Requested-With: XMLHttpRequest", "-H", "Referer: " + R + "/542645/rezultati/"]
    for k, v in data.items(): args += ["--data-urlencode", f"{k}={v}"]
    for a in range(tries):
        o = curl(args + [R + path])
        try: return json.loads(o)
        except Exception:
            time.sleep(2 + a * 3)
            if a == 2: cookie()
    return None
num = lambda x: int(str(x).replace('.', '') or 0)
def rec(r):
    s = (r or {}).get("stat_sum_numbers") or {}
    if num(s.get("processed_stations", 0)) == 0: return None
    try: v, iv = [int(x) for x in r["sum_config"]["data"]["datasets"][0]["data"][:2]]
    except Exception: v = iv = None
    lists = [0] * 18
    for l in r.get("table_data") or []:
        i = int(l["count_number"]) - 1
        if 0 <= i < 18: lists[i] = num(l["won_number"])
    m = re.search(r"href='([^']+)'", r.get("minute_from_election_station") or "")
    return dict(processed=True, voters=num(s.get("total_voters", 0)), out=num(s.get("available", 0)), valid=v, invalid=iv, lists=lists,
                zlink=(R + m.group(1)) if m else None)

# ---------- statični podaci ----------
IDX = json.load(open("public/data/index.json"))
UNITS = {}
for uid, u in IDX["units"].items():
    uf = json.load(open(f"public/data/u/{uid}.json"))
    UNITS[uid] = dict(region=u["region"], st={s["sid"]: s for s in uf["stations"]})
log("jedinica", len(UNITS), "BM", sum(len(u["st"]) for u in UNITS.values()), "SIM" if A.sim else "")

# ---------- stanje (nastavlja iz postojećih fajlova) ----------
LU = {}
for uid in UNITS:
    f = f"{OUT}/u/{uid}.json"
    LU[uid] = json.load(open(f)) if os.path.exists(f) else {"bm": {}}
LOGF = f"{OUT}/log.json"
LOG = json.load(open(LOGF)) if os.path.exists(LOGF) else []
def addlog(uid, sid, typ, detail, t):
    LOG.append(dict(at=t, u=uid, s=sid, n=UNITS[uid]['st'][sid]['n'], type=typ, detail=detail))
AGG = {}  # uid -> (processed, datetime) iz poslednjeg kruga
CHECKED = {}  # (uid,sid) -> vreme poslednje provere
SIMT0 = time.time()

def unit_agg(uid):
    if A.sim:  # u simulaciji: "obrađeno" raste linearno ~ 40 min do kraja
        frac = min(1.0, (time.time() - SIMT0) / (40 * 60 if not A.fast else 6 * 60))
        st = list(UNITS[uid]["st"].values()); random.Random(int(uid)).shuffle(st)
        k = int(len(st) * frac)
        return dict(processed=k, dt=str(k), reveal={s["sid"] for s in st[:k]})
    d = post("/get_results/", dict(should_update_pies=1, type=2, election_round=ROUND, region=UNITS[uid]["region"], municipality=uid, election_station=0))
    if d is None: return None
    s = d.get("stat_sum_numbers") or {}
    return dict(processed=num(s.get("processed_stations", 0)), dt=s.get("datetime"))

def fetch_station(uid, sid):
    s = UNITS[uid]["st"][sid]
    if A.sim:
        if not s.get("m23"): return None
        sid_q = s["m23"]
    else: sid_q = sid
    d = post("/get_results/", dict(should_update_pies=1, type=2, election_round=ROUND, region=UNITS[uid]["region"], municipality=uid, election_station=sid_q))
    return rec(d) if d is not None else "ERR"

def checks(r, y23):
    """Aritmetičke provere – samo za dnevnik, ne za mapu."""
    w = []
    if r["valid"] is not None and r["invalid"] is not None:
        box = r["valid"] + r["invalid"]
        if box - r["out"] >= 3: w.append(f"u kutiji više listića ({box}) nego birača koji su glasali ({r['out']})")
        elif r["out"] - box > max(10, 0.02 * r["out"]): w.append(f"u kutiji {r['out']-box} listića manje nego birača koji su glasali")
    if sum(r["lists"]) != (r["valid"] or 0): w.append(f"zbir po listama ({sum(r['lists'])}) ≠ važeći ({r['valid']})")
    if r["voters"] and r["out"] > r["voters"]: w.append("izašlo više od upisanih")
    if r["voters"] and r["out"] / r["voters"] > 0.92: w.append(f"izlaznost {100*r['out']/r['voters']:.1f} %")
    if y23 and y23.get("voters") and r["voters"]:
        t23 = y23["out"] / y23["voters"]; t26 = r["out"] / r["voters"]
        if abs(t26 - t23) > 0.25: w.append(f"izlaznost {100*t26:.0f} % (2023: {100*t23:.0f} %)")
    return w

def apply(uid, sid, r, t):
    L = LU[uid]["bm"]; old = L.get(sid); changed = False
    y23 = UNITS[uid]["st"][sid].get("y23")
    if r is None: return False
    new = {k: r[k] for k in ("processed", "voters", "out", "valid", "invalid", "lists")}
    if old is None or not old.get("processed"):
        rec_ = dict(new, at=t, zap=[], alerts=[], chk=checks(r, y23))
        if r["zlink"]: rec_["zap"].append(dict(link=r["zlink"], at=t))
        if rec_["chk"]: addlog(uid, sid, "provera", "; ".join(rec_["chk"]), t)
        L[sid] = rec_; return True
    diffk = [k for k in ("voters", "out", "valid", "invalid", "lists") if old.get(k) != new[k]]
    if diffk:
        old["alerts"].append(dict(type="rezultat", at=t, detail="RIK promenio: " + ", ".join(diffk), before={k: old.get(k) for k in diffk}))
        addlog(uid, sid, "rezultat", "RIK promenio rezultat (" + ", ".join(diffk) + ")", t)
        old.update(new); old["chk"] = checks(r, y23); changed = True
    if r["zlink"] and (not old["zap"] or old["zap"][-1]["link"] != r["zlink"]):
        if old["zap"]:
            old["alerts"].append(dict(type="zapisnik", at=t, detail="Zapisnik na RIK-u zamenjen novim fajlom"))
            addlog(uid, sid, "zapisnik", "Zapisnik na RIK-u zamenjen novim fajlom", t)
        old["zap"].append(dict(link=r["zlink"], at=t)); changed = True
    return changed

# ---------- rešenja o poništavanju glasanja (RIK dokumenti, tip 1) ----------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translit import lat
import telegram as TG
import dnevnik as _DN
if A.standby and not _DN.jedini("rezerva" + ("-proba" if A.sim else "")): print("rezerva već radi – izlazim"); sys.exit(0)
if A.sim: TG.sim_lists(); TG.SITE = "PROBA (rezultati 2023) · " + TG.SITE
if A.tg_demo: TG.demo(print); sys.exit(0)
def _core(x): return re.sub(r'^(gradska opština|grad|opština)\s+', '', lat(x).lower()).strip()
UCORE = {}
for uid, u in IDX["units"].items(): UCORE.setdefault(_core(re.sub(r'\s*\(.*\)', '', u["name"])), []).append(uid)
SEEN_DOCS = set(); LAST_DOCS = 0
def annulments(t):
    global LAST_DOCS
    if A.sim or time.time() - LAST_DOCS < 600: return set()
    LAST_DOCS = time.time(); changed = set()
    for p in (1, 2, 3):
        o = curl(["-G", R + "/get-additional-documents", "--data-urlencode", f"page={p}", "--data-urlencode", "filters[document-type]=1",
                  "--data-urlencode", f"filters[election-round]={ROUND}", "--data-urlencode", "filters[municipality-id]=0",
                  "--data-urlencode", "filters[election_station]=0", "--data-urlencode", "filters[additional-document]=0",
                  "--data-urlencode", "order=0", "--data-urlencode", "sort=0", "--data-urlencode", "election_type=-1"], 60)
        try: recs = json.loads(o)["records"]
        except Exception: break
        for d in recs:
            name = (d.get("document_name") or "") + " " + (d.get("election_board_decision") or "")
            links = re.findall(r'href="([^"]+)"', str(d.get("extfiles_link")))
            key = links[0] if links else name
            if key in SEEN_DOCS: continue
            SEEN_DOCS.add(key)
            if not re.search(r"ПОНИШТ|поништ", name): continue
            uids = UCORE.get(_core(d.get("municipality_display_name") or ""), [])
            m = re.match(r"\s*(\d+)", d.get("election_station_title") or "") or re.search(r"(?:БМ|бирачк\w* мест\w*)\s*(?:бр\.?|број)?\s*(\d+)", name)
            if not uids or not m: log("rešenje o poništavanju bez BM:", name[:120]); continue
            uid = uids[0]; n = int(m.group(1))
            sid = next((s for s, x in UNITS[uid]["st"].items() if x["n"] == n), None)
            if not sid: continue
            b = LU[uid]["bm"].setdefault(sid, {"processed": False, "zap": [], "alerts": []})
            b["status"] = dict(oboreno=True, napomena="RIK: " + re.sub(r"\s+", " ", name).strip()[:160], at=t, doc=(R + links[0]) if links else None)
            b.setdefault("alerts", []).append(dict(type="oboreno", at=t, detail=b["status"]["napomena"]))
            addlog(uid, sid, "oboreno", b["status"]["napomena"], t); changed.add(uid)
    return changed

def summary(t):
    U = {}; P = 0
    for uid, u in UNITS.items():
        bm = LU[uid]["bm"]; done = 0; m = 0
        s26 = dict(voters=0, out=0, valid=0, invalid=0, lists=[0] * 18); s23 = dict(voters=0, out=0, valid=0, invalid=0, lists=[0] * 18)
        for sid, r in bm.items():
            if not r.get("processed"): continue
            done += 1
            for k in ("voters", "out", "valid", "invalid"): s26[k] += r.get(k) or 0
            s26["lists"] = [a + b for a, b in zip(s26["lists"], r["lists"])]
            y = u["st"].get(sid, {}).get("y23")
            if y:
                m += 1
                for k in ("voters", "out", "valid", "invalid"): s23[k] += y.get(k) or 0
                s23["lists"] = [a + b for a, b in zip(s23["lists"], y["lists"])]
        P += done
        ob = [sid for sid, r in bm.items() if (r.get("status") or {}).get("oboreno")]
        if done or ob: U[uid] = dict(done=done, m=m, s26=s26, s23=s23, dt=(AGG.get(uid) or {}).get("dt"), ob=ob)
    return dict(meta=dict(checked=t, changed=LASTCH[0], processed=P, stations=sum(len(u["st"]) for u in UNITS.values()), sim=A.sim), u=U)

def write(changed_units, t):
    for uid in changed_units:
        json.dump(LU[uid], open(f"{OUT}/u/{uid}.json", "w"), ensure_ascii=False, separators=(",", ":"))
    s = summary(t); json.dump(s, open(f"{OUT}/summary.json", "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump(LOG, open(LOGF, "w"), ensure_ascii=False, separators=(",", ":"))
    return s

def main_gap_min():
    """Objava na main (= Cloudflare gradnja, limit 500/mesec): 21-02 h na 15 min, inače na 60 min."""
    h = now().hour
    return 15 if (h >= 21 or h < 2) else 60
def last_main_push():
    try: return int(subprocess.run(["git", "log", "-1", "--format=%ct", "origin/main", "--", OUT], capture_output=True, text=True).stdout.strip() or 0)
    except Exception: return 0
def push_uzivo(msg):
    """Na 'uzivo' ide folder sa rezultatima + dnevnik rada (logovi/), na vrh postojeće grane – bez fajlova iz .github
    (GitHub ne dozvoljava GITHUB_TOKEN-u da menja radne tokove, pa bi push cele grane bio odbijen)."""
    import dnevnik as DN
    def extra(env):
        subprocess.run(["git", "rm", "-r", "-q", "--cached", "--ignore-unmatch", OUT], capture_output=True, env=env)
        subprocess.run(["git", "add", "-f", OUT], capture_output=True, env=env)
    job = "rik_live-" + DN.host() + ("-proba" if A.sim else "")
    lines = LOGBUF[:]
    ok = DN.push(DN.log_changes({job: lines}) if lines else {}, msg, extra)
    if ok: del LOGBUF[:len(lines)]
    else: log("push na uzivo nije uspeo")
    return ok

def push(msg, force_main=False):
    """Svaka promena -> grana 'uzivo' (bez Cloudflare gradnje; aplikacija je čita sa GitHub-a).
    Na 'main' samo po rasporedu (main_gap_min)."""
    global LASTMAIN
    if A.no_push: return True
    subprocess.run(["git", "add", OUT], check=False)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        subprocess.run(["git", "commit", "-qm", msg], check=False)
    ok = push_uzivo(msg)
    if not ok: log("push na uzivo nije uspeo")
    if force_main or time.time() - LASTMAIN >= main_gap_min() * 60:
        for a in range(4):
            if subprocess.run(["git", "push", "-q", "origin", "HEAD:main"]).returncode == 0:
                LASTMAIN = time.time(); log("objavljeno na main (Cloudflare)"); break
            subprocess.run(["git", "pull", "-q", "--rebase", "-X", "theirs", "origin", "main"], check=False)
        else: log("PUSH NA MAIN NIJE USPEO")
    return ok

def sync_from_uzivo():
    """Nastavi od poslednjeg stanja sa grane 'uzivo' (ako je novija od main)."""
    if A.no_push: return
    if subprocess.run(["git", "fetch", "-q", "origin", "uzivo"]).returncode != 0: return
    subprocess.run(["git", "checkout", "FETCH_HEAD", "--", OUT], check=False)
    subprocess.run(["git", "reset", "-q"], check=False)
    for uid in UNITS:
        f = f"{OUT}/u/{uid}.json"
        if os.path.exists(f): LU[uid] = json.load(open(f))
    if os.path.exists(LOGF): LOG[:] = json.load(open(LOGF))

# ---------- glavna petlja ----------
cookie()
deadline = time.time() + A.minutes * 60
interval = 1.0 if A.fast else 5.0
total = sum(len(u["st"]) for u in UNITS.values())
PENDING = False; LASTPUSH = 0
LASTCH = [None]  # vreme poslednje nove/promenjene objave RIK-a (za „RIK objavio novo pre X min” u aplikaciji)
subprocess.run(["git", "fetch", "-q", "origin", "main"], check=False)
LASTMAIN = last_main_push()
if not A.reset: sync_from_uzivo()
try: LASTCH[0] = json.load(open(f"{OUT}/summary.json"))["meta"].get("changed")
except Exception: pass
_GHC = [None, 0]
def gh_alive():
    import urllib.request
    try:
        for st in ("in_progress", "queued"):  # najviše 2 upita; bez tokena GitHub dozvoljava 60/h
            if _GHC[0] and time.time() - _GHC[1] < 240: return _GHC[0]
            d = json.loads(urllib.request.urlopen(f"https://api.github.com/repos/MirkoRudic/kontrola-izbora-srbija/actions/workflows/izborna-noc.yml/runs?status={st}&per_page=1", timeout=20).read())
            if d.get("total_count"): _GHC[:] = [True, time.time()]; return True
        _GHC[:] = [False, time.time()]; return False
    except Exception: return True  # ako ne možemo da proverimo, ne mešamo se (osim ako je objava stara)
def remote_age_min():
    sync_from_uzivo()
    try:
        m = json.load(open(f"{OUT}/summary.json"))["meta"]["checked"]
        d, mo, h, mi = map(int, re.findall(r"\d+", m)[:4]); n = now()
        t = n.replace(month=mo, day=d, hour=h, minute=mi, second=0, microsecond=0)
        return (n - t).total_seconds() / 60
    except Exception: return 999
LASTLOG = time.time()
def flush_logs(force=False):
    """Dnevnik i kad nema novih podataka (na 10 min), da se vidi da posao živi."""
    global LASTLOG
    if A.no_push or not LOGBUF or (not force and time.time() - LASTLOG < 600): return
    import dnevnik as DN
    lines = LOGBUF[:]
    if DN.push_logs({"rik_live-" + DN.host() + ("-proba" if A.sim else ""): lines}): del LOGBUF[:len(lines)]
    LASTLOG = time.time()
def _pad(t, v, tb):
    import traceback
    log("PAD: " + "".join(traceback.format_exception(t, v, tb))[-1500:])
    try: flush_logs(True)
    except Exception: pass
    sys.__excepthook__(t, v, tb)
sys.excepthook = _pad
log(f"start: {'PROBA ' if A.sim else ''}{'rezerva ' if A.standby else ''}minuta {A.minutes}")
while time.time() < deadline:
    if A.standby:
        age = remote_age_min(); alive = gh_alive()
        if (alive and age < 25) or age < 3:  # GitHub upisuje bar na 10 min; starije od 25 min = zaglavio se
            log(f"rezerva čeka: GitHub {'radi' if alive else 'ne radi'}, objava stara {age:.0f} min")
            flush_logs(); time.sleep(120); continue
        log(f"GitHub posao ne radi (objava stara {age:.0f} min) – rezerva preuzima ovaj krug")
    t0 = time.time(); t = stamp()
    with ThreadPoolExecutor(A.threads) as ex:
        ags = dict(zip(UNITS, ex.map(unit_agg, UNITS)))
    todo = []
    for uid, a in ags.items():
        if a is None: continue
        prev = AGG.get(uid)
        known = sum(1 for r in LU[uid]["bm"].values() if r.get("processed"))
        if a["processed"] > known or (prev and prev.get("dt") != a.get("dt")):
            for sid in UNITS[uid]["st"]:
                if not (LU[uid]["bm"].get(sid) or {}).get("processed"):
                    if A.sim and sid not in a["reveal"]: continue
                    todo.append((uid, sid))
        AGG[uid] = a
    # spora rotacija obrađenih (izmene rezultata/zapisnika): najstarije proverena, do 150 po krugu
    done_list = [(uid, sid) for uid in UNITS for sid, r in LU[uid]["bm"].items() if r.get("processed")]
    done_list.sort(key=lambda k: CHECKED.get(k, 0))
    todo += done_list[:150]
    changed = set(); new = 0; err = 0
    with ThreadPoolExecutor(A.threads) as ex:
        res = list(ex.map(lambda k: (k, fetch_station(*k)), todo))
    for (uid, sid), r in res:
        CHECKED[(uid, sid)] = time.time()
        if r == "ERR": err += 1; continue
        was = (LU[uid]["bm"].get(sid) or {}).get("processed")
        if apply(uid, sid, r, t):
            changed.add(uid)
            if not was and r: new += 1
    changed |= annulments(t)
    if changed: LASTCH[0] = t
    s = write(changed, t)
    try:
        T = TG.totals(UNITS, LU)
        TG.maybe_send(T, now(), f"{OUT}/telegram.json", log)
    except Exception as e: log("telegram greška:", e)
    if changed or time.time() - LASTPUSH >= 600: PENDING = True  # i bez promena na 10 min: „ažurirano” u aplikaciji i znak života za rezervu
    if PENDING and time.time() - LASTPUSH >= 120:  # Cloudflare gradi sajt posle svakog push-a (limit gradnji): ne češće od 2 min
        if push(f"Uživo: obrađeno {s['meta']['processed']}/{total} BM ({t})"): PENDING = False; LASTPUSH = time.time()
    # interval
    if s["meta"]["processed"] >= total: interval = 30.0
    elif new: interval = max(1.0, interval / 2)
    else: interval = min(15.0, interval * 1.5)
    if A.fast: interval = min(interval, 1.0)
    log(f"krug: upita {len(todo)} novih {new} greške {err} promenjeno opština {len(changed)} obrađeno {s['meta']['processed']}/{total} trajanje {time.time()-t0:.0f}s sledeći za {interval:.1f} min")
    flush_logs()
    nxt = t0 + interval * 60
    if nxt > deadline: break
    time.sleep(max(5, nxt - time.time()))
if PENDING: push(f"Uživo: obrađeno {summary(stamp())['meta']['processed']}/{total} BM ({stamp()})")
log("kraj kruga (isteklo vreme)")
flush_logs(True)
log("kraj")
