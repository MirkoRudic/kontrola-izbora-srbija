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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    mf = r.get("minute_from_election_station") or ""
    m = re.search(r"href='([^']+)'", mf)
    # 27.10.: uz zapisnik RIK kači i dodatne fajlove (RG-7 rešenje o ispravci, RG-11 posmatrači) – beležimo sve
    import html as _h
    dz = [dict(link=R + _h.unescape(l), naziv=_h.unescape(nm).strip(), t=dt.strip())
          for l, nm, dt in re.findall(r"href='([^']+)'[^>]*>([^<]*)<span[^>]*></span></a><span>([^<]*)", mf)]
    return dict(processed=True, voters=num(s.get("total_voters", 0)), out=num(s.get("available", 0)), valid=v, invalid=iv, lists=lists,
                zlink=(R + m.group(1)) if m else None, dz=[x for x in dz if m and x["link"] != R + m.group(1)])

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
# 27.10.: „Rešenje o odbacivanju/odbijanju zahteva za poništavanje“ greškom je bilo upisano kao poništeno – čistimo pri pokretanju
_NEPON = re.compile(r"ОДБАЦ|одбац|ОДБИ[ЈJ]|одби[јj]|НЕОСНОВАН|неоснован")
OCISCENO = set()
def ocisti():
    """Briše pogrešno upisano „poništeno“ za rešenja o odbacivanju/odbijanju zahteva (poziva se i posle sync_from_uzivo)."""
    for _uid, _u in LU.items():
        for _sid, _b in _u.get("bm", {}).items():
            _st = _b.get("status") or {}
            if _st.get("oboreno") and _NEPON.search(_st.get("napomena") or ""):
                _b.pop("status", None); _b["alerts"] = [x for x in _b.get("alerts", []) if not (x.get("type") == "oboreno" and _NEPON.search(x.get("detail") or ""))]
                OCISCENO.add(_uid)
    LOG[:] = [e for e in LOG if not (e.get("type") == "oboreno" and _NEPON.search(e.get("detail") or ""))]
    import html as _h
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from translit import lat as _lat
    _L = lambda x: _lat(_h.unescape(x)) if x and re.search("[\u0400-\u04FF]|&#", x) else x
    for _uid, _u in LU.items():
        for _b in _u.get("bm", {}).values():
            _st = _b.get("status") or {}
            if _st.get("oboreno") and _L(_st.get("napomena")) != _st.get("napomena"): _st["napomena"] = _L(_st["napomena"]); OCISCENO.add(_uid)
            for x in _b.get("alerts", []):
                if x.get("type") == "oboreno": x["detail"] = _L(x.get("detail"))
    for e in LOG:
        if e.get("type") == "oboreno": e["detail"] = _L(e.get("detail"))
    # 27.10. 22:20: „ispravka“ upisana pri prvom viđenju starih RG-7 fajlova (pogrešno vreme) – briše se; fajlovi ostaju u b["dz"]
    _n0 = len(LOG); LOG[:] = [e for e in LOG if not (e.get("type") == "ispravka" and not e.get("v"))]
    for _uid, _u in LU.items():
        for _b in _u.get("bm", {}).values():
            _a = _b.get("alerts") or []
            if any(x.get("type") == "ispravka" and not x.get("v") for x in _a):
                _b["alerts"] = [x for x in _a if not (x.get("type") == "ispravka" and not x.get("v"))]; OCISCENO.add(_uid)
    _seen = set(); LOG[:] = [e for e in LOG if not (e.get("type") == "oboreno" and ((e.get("u"), e.get("s")) in _seen or _seen.add((e.get("u"), e.get("s")))))]
ocisti()
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
    if r is None:
        # 27.10.: RIK ume da skine već objavljen rezultat (Kuršumlija BM 30) – proveri još jednom, pa zabeleži
        if old and old.get("processed") and not A.sim:
            time.sleep(3); r2 = fetch_station(uid, sid)
            if r2 is None:
                bf = {k: old.get(k) for k in ("voters", "out", "valid", "invalid", "lists")}
                old.setdefault("alerts", []).append(dict(type="skinuto", at=t, detail="RIK skinuo objavljeni rezultat sa sajta", before=bf))
                addlog(uid, sid, "skinuto", "RIK skinuo objavljeni rezultat (bilo: izašlo %s, važećih %s)" % (bf["out"], bf["valid"]), t)
                old["processed"] = False; old["skinuto"] = t; return True
        return False
    new = {k: r[k] for k in ("processed", "voters", "out", "valid", "invalid", "lists")}
    if old is None or not old.get("processed"):
        rec_ = dict(new, at=t, zap=[], alerts=[], chk=checks(r, y23))
        if old and old.get("skinuto"):  # rezultat ponovo objavljen – zadrži istoriju
            rec_["zap"] = old.get("zap", []); rec_["alerts"] = old.get("alerts", []) + [dict(type="vraceno", at=t, detail="RIK ponovo objavio rezultat")]
            addlog(uid, sid, "vraceno", "RIK ponovo objavio rezultat (izašlo %s, važećih %s)" % (new["out"], new["valid"]), t)
        if r["zlink"] and (not rec_["zap"] or rec_["zap"][-1]["link"] != r["zlink"]): rec_["zap"].append(dict(link=r["zlink"], at=t))
        if r.get("dz"): rec_["dz"] = r["dz"]
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
    if r.get("dz") is not None and ("dz" not in old or r["dz"] != old["dz"]):
        # 27.10. 22:20: pri prvom viđenju (stari fajlovi) bez upisa u dnevnik; vreme = vreme kačenja na RIK-u
        if "dz" in old:
            had = {x["link"] for x in old["dz"]}
            for x in r["dz"]:
                if x["link"] not in had and re.search(r"(?:РГ|RG|PG|ПГ)\s*-?\s*(?:8-)?7(?!\d)|исправ|ispravk", x["naziv"], re.I):
                    m_ = re.match(r"(\d+)-(\d+)-\d{4}\s*(\d+:\d+)", x.get("t") or ""); ta = f"{m_[1]}.{m_[2]}. {m_[3]}" if m_ else t
                    old["alerts"].append(dict(type="ispravka", at=ta, v=2, detail="Uz zapisnik okačeno rešenje o ispravci zapisnika (RG-7)", link=x["link"]))
                    LOG.append(dict(at=ta, u=uid, s=sid, n=UNITS[uid]['st'][sid]['n'], type="ispravka", v=2, detail="Uz zapisnik okačeno rešenje o ispravci zapisnika (RG-7)"))
        old["dz"] = r["dz"]; changed = True
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
    prvi = LAST_DOCS == 0
    LAST_DOCS = time.time(); changed = set()
    for p in range(1, 26 if prvi else 4):  # prvi put u krugu: sve od dana izbora (~18 strana), posle samo najnovije
        o = curl(["-G", R + "/get-additional-documents", "--data-urlencode", f"page={p}", "--data-urlencode", "filters[document-type]=1",
                  "--data-urlencode", f"filters[election-round]={ROUND}", "--data-urlencode", "filters[municipality-id]=0",
                  "--data-urlencode", "filters[election_station]=0", "--data-urlencode", "filters[additional-document]=0",
                  "--data-urlencode", "order=0", "--data-urlencode", "sort=0", "--data-urlencode", "election_type=-1"], 60)
        try: recs = json.loads(o)["records"]
        except Exception: break
        if not recs: break
        for d in recs:
            name = (d.get("document_name") or "") + " " + (d.get("election_board_decision") or "")
            links = re.findall(r'href="([^"]+)"', str(d.get("extfiles_link")))
            key = links[0] if links else name
            if key in SEEN_DOCS: continue
            SEEN_DOCS.add(key)
            if not re.search(r"ПОНИШТ|НЕ\s+МОГУ\s+(СЕ\s+)?УТВРДИТИ", name, re.I): continue  # i „rezultati se ne mogu utvrditi“ (Koceljeva, 27.10.)
            if _NEPON.search(name): log("rešenje o odbacivanju/odbijanju zahteva – nije poništeno:", name[:120]); continue
            uids = UCORE.get(_core(d.get("municipality_display_name") or ""), [])
            m = re.match(r"\s*(\d+)", d.get("election_station_title") or "") or re.search(r"(?:БМ|Б\.\s?М\.|BM|бирачк\w*\s+мест\w*|biračk\w*\s+mest\w*)\s*(?:бр\.?|број|br\.?|broj)?\s*(\d+)", name, re.I)  # 27.10.: i VELIKIM slovima (Ljig BM 20, Kanjiža BM 4 su bili promašeni)
            if not uids or not m: log("rešenje o poništavanju bez BM:", name[:120]); continue
            uid = uids[0]; n = int(m.group(1))
            sid = next((s for s, x in UNITS[uid]["st"].items() if x["n"] == n), None)
            if not sid: continue
            b = LU[uid]["bm"].setdefault(sid, {"processed": False, "zap": [], "alerts": []})
            doc = (R + links[0]) if links else None
            if (b.get("status") or {}).get("oboreno") and (b["status"].get("doc") == doc or not doc): continue  # već upisano (SEEN_DOCS važi samo u jednom krugu)
            import html as _html
            b["status"] = dict(oboreno=True, napomena="RIK: " + lat(_html.unescape(re.sub(r"\s+", " ", name).strip()))[:160], at=t, doc=doc)
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
    ocisti()

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
        elif a["processed"] < known and not A.sim:  # RIK ima manje obrađenih nego mi – proveri sva obrađena BM te jedinice
            todo += [(uid, sid) for sid, r in LU[uid]["bm"].items() if r.get("processed")]
        AGG[uid] = a
    # spora rotacija obrađenih (izmene rezultata/zapisnika): najstarije proverena, do 150 po krugu
    done_list = [(uid, sid) for uid in UNITS for sid, r in LU[uid]["bm"].items() if r.get("processed")]
    # 27.10.: prvo obrađena BM bez linka na zapisnik (bilo ih je 1.282), pa najdavnije proverena; slučajan redosled među jednakima (CHECKED se ne pamti između krugova posla)
    done_list.sort(key=lambda k: (bool(LU[k[0]]["bm"][k[1]].get("zap")), CHECKED.get(k, 0), random.random()))
    vec = set(todo); nz = [k for k in done_list if not LU[k[0]]["bm"][k[1]].get("zap")][:400]; vec |= set(nz)
    todo += nz + [k for k in done_list[:150] if k not in vec]
    changed = set(); new = 0; err = 0
    # rezultati se upisuju čim stignu; tokom dugog kruga međuobjava na ~3 min (da aplikacija ne čeka kraj kruga)
    part = set(); tpart = time.time()
    with ThreadPoolExecutor(A.threads) as ex:
        futs = {ex.submit(fetch_station, *k): k for k in todo}
        for fu in as_completed(futs):
            uid, sid = futs[fu]
            try: r = fu.result()
            except Exception: r = "ERR"
            CHECKED[(uid, sid)] = time.time()
            if r == "ERR": err += 1; continue
            was = (LU[uid]["bm"].get(sid) or {}).get("processed")
            if apply(uid, sid, r, t):
                changed.add(uid); part.add(uid)
                if not was and r: new += 1
            if part and time.time() - tpart >= 180:
                try:
                    tp = stamp(); sp = write(part, tp)
                    if push(f"Uživo: obrađeno {sp['meta']['processed']}/{total} BM ({tp}, u toku kruga)"): LASTPUSH = time.time()
                    log(f"međuobjava: obrađeno {sp['meta']['processed']}/{total}")
                except Exception as e: log("međuobjava greška:", e)
                part = set(); tpart = time.time()
    changed |= annulments(t)
    if OCISCENO: changed |= OCISCENO; OCISCENO.clear()
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
    else: interval = min(5.0, interval * 1.5)
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
