# Laptop, izborna noć: provera sačuvanih zapisnika (RG-2) lokalnim modelom (Ollama, qwen2.5vl).
#   python tools\laptop_citanje.py --dir D:\VAJB\kontrolaizbora\zapisnici [--until 2026-10-28T12:00] [--sim]
#
# Tok (dogovoreno 22.10.):
#  1. Trijaža po broju strana: zapisnik duži od norme opštine (najčešći broj strana) = kandidat za primedbe.
#     Spisak kandidata ide na granu 'uzivo' (public/data/zap/kandidati.json); oblak ih čita detaljno (oblak.json).
#  2. „!” za sve što oblak nije pročitao: isečak 11.1–11.4 (izašli, u kutiji, nevažeći, važeći) poredi se sa RIK-om.
#     „!” se upisuje tek kad: (a) svež upit RIK-u za to BM i dalje daje drugi broj, (b) ponovno, uvećano čitanje
#     isečka daje isti broj kao prvo. Ako se dva čitanja ne slažu – BM ide oblaku (kandidat „nesigurno”), bez „!”.
#     Kad se RIK ispravi, „!” se gasi u sledećem krugu.
#  3. Drugi krug P: isečak polja 15 (primedbe DA/NE) za zapisnike normalne dužine; „DA” -> p15 (P u aplikaciji) i kandidat za oblak.
# Rezultat: <dir>\citanje.json i 'uzivo' -> public/data/zap/citanje.json, logovi/laptop-citanje.log
import sys, os
if os.name == 'nt' and not sys.flags.utf8_mode:
    os.execv(sys.executable, [sys.executable, '-X', 'utf8'] + sys.argv)
import json, time, base64, io, argparse, datetime, urllib.request, urllib.parse, http.cookiejar, collections
import pypdfium2 as P
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import dnevnik as DN
ap = argparse.ArgumentParser()
ap.add_argument('--dir', required=True)
ap.add_argument('--until', default='2026-10-28T12:00')
ap.add_argument('--model', default='qwen2.5vl:7b')
ap.add_argument('--sim', action='store_true')
ap.add_argument('--no-push', action='store_true')
ap.add_argument('--once', action='store_true', help='jedan krug i izlaz (test)')
A = ap.parse_args()
if not DN.jedini("citanje" + ("-proba" if A.sim else "")): print("čitanje već radi – izlazim"); sys.exit(0)
D = A.dir; RES_F = os.path.join(D, "citanje.json"); IXF = os.path.join(D, "index.json"); KF = os.path.join(D, "kandidati.json")
RAWU = "https://raw.githubusercontent.com/MirkoRudic/kontrola-izbora-srbija/uzivo/public/data/"
R = "https://www.rik.parlament.gov.rs"; ROUND = "341140" if A.sim else "680072"
def now(): return datetime.datetime.now()
UNTIL = datetime.datetime.fromisoformat(A.until)
LOGBUF = []
def log(*a):
    s = " ".join(str(x) for x in a); print(now().strftime("%H:%M:%S"), s, flush=True); LOGBUF.append(s)

# ---------- spisak BM iz repoa ----------
PD = os.path.join(HERE, "..", "public", "data")
IDX = json.load(open(os.path.join(PD, "index.json"), encoding="utf-8"))
UNITS = {}
for uid, u in IDX["units"].items():
    try: uf = json.load(open(os.path.join(PD, "u", uid + ".json"), encoding="utf-8"))
    except Exception: continue
    UNITS[uid] = dict(region=u["region"], st={s["sid"]: s for s in uf["stations"]})
NORM23 = json.load(open(os.path.join(HERE, "norme2023.json")))

# ---------- RIK (svež upit za jedno BM) ----------
cj = http.cookiejar.CookieJar(); OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
OP.addheaders = [("User-Agent", "Mozilla/5.0 (kontrola-izbora)")]
def cookie():
    try: OP.open(R + "/542645/rezultati/", timeout=60).read()
    except Exception as e: log("cookie greška", e)
def post(path, data, tries=4):
    for a in range(tries):
        try:
            rq = urllib.request.Request(R + path, data=urllib.parse.urlencode(data).encode(),
                                        headers={"X-Requested-With": "XMLHttpRequest", "Referer": R + "/542645/rezultati/"})
            return json.loads(OP.open(rq, timeout=60).read())
        except Exception:
            time.sleep(2 + a * 3)
            if a == 1: cookie()
    return None
num = lambda x: int(str(x).replace('.', '') or 0)
def rik_fresh(uid, sid):
    s = UNITS[uid]["st"].get(sid) or {}
    q = s.get("m23") if A.sim else sid
    if not q: return None
    d = post("/get_results/", dict(should_update_pies=1, type=2, election_round=ROUND, region=UNITS[uid]["region"], municipality=uid, election_station=q))
    st = (d or {}).get("stat_sum_numbers") or {}
    if not d or num(st.get("processed_stations", 0)) == 0: return None
    try: v, iv = [int(x) for x in d["sum_config"]["data"]["datasets"][0]["data"][:2]]
    except Exception: v = iv = None
    return dict(voters=num(st.get("total_voters", 0)), out=num(st.get("available", 0)), valid=v, invalid=iv)

# ---------- model ----------
def api(path, data=None, t=300):
    req = urllib.request.Request("http://127.0.0.1:11434" + path, data=json.dumps(data).encode() if data else None, headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=t).read())
def b64(im):
    b = io.BytesIO(); im.save(b, "PNG"); return base64.b64encode(b.getvalue()).decode()
def ask(im, prompt):
    r = api("/api/chat", {"model": A.model, "stream": False, "format": "json", "options": {"temperature": 0},
                          "messages": [{"role": "user", "content": prompt, "images": [b64(im)]}]})
    try: return json.loads(r["message"]["content"])
    except Exception: return {}
Q_REZ = ("Isečak srpskog izbornog zapisnika (deo III, tačke 11.1–11.4), rukom popunjen. Vrati SAMO JSON: "
         '{"izasli": broj u 11.1, "u_kutiji": 11.2, "nevazeci": 11.3, "vazeci": 11.4}. Ako je polje prazno, stavi null (ne 0). Crtica = 0.')
Q_P15 = ("Isečak srpskog izbornog zapisnika, tačka 15: da li su članovi biračkog odbora imali primedbe i mišljenja. "
         'Pogledaj koja je reč zaokružena ili podvučena (DA ili NE). Vrati SAMO JSON: {"primedbe": "DA"/"NE"/null}.')
def toint(v):
    try: return int(str(v).replace('.', '').strip())
    except Exception: return None
def page0(path, dpi):
    pdf = P.PdfDocument(path); n = len(pdf); im = pdf[0].render(scale=dpi / 72).to_pil(); pdf.close(); return n, im
def pages_of(path):
    pdf = P.PdfDocument(path); n = len(pdf); pdf.close(); return n
def read_rez(path, dpi=150, pad=0.0):
    n, im = page0(path, dpi); W, H = im.size
    if W < H: r = ask(im, Q_REZ)  # uspravan sken jedne strane
    else: r = ask(im.crop((0, int(H * (.70 - pad)), int(W * (.48 + pad)), int(H * (.89 + pad)))), Q_REZ)
    return {k: toint(r.get(k)) for k in ("izasli", "u_kutiji", "nevazeci", "vazeci")}
def read_p15(path):
    n, im = page0(path, 200); W, H = im.size
    if W < H: r = ask(im.crop((0, int(H * .6), W, H)), Q_P15)
    else: r = ask(im.crop((int(W * .52), int(H * .78), W, int(H * .97))), Q_P15)
    v = r.get("primedbe"); return v if v in ("DA", "NE") else None

# ---------- stanje ----------
RES = json.load(open(RES_F, encoding="utf-8")) if os.path.exists(RES_F) else {}
KAND = json.load(open(KF, encoding="utf-8")) if os.path.exists(KF) else {}
def save():
    for f, o in ((RES_F, RES), (KF, KAND)):
        tmp = f + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh: json.dump(o, fh, ensure_ascii=False)
        os.replace(tmp, f)
LASTPUSH = [0.0]
def publish(force=False):
    if A.no_push or (not force and time.time() - LASTPUSH[0] < 120): return
    st = now().strftime("%d.%m. %H:%M")
    body = json.dumps(dict(meta=dict(at=st, n=sum(len(v) for v in RES.values()), sim=A.sim), u=RES), ensure_ascii=False, separators=(",", ":"))
    kb = json.dumps(dict(meta=dict(at=st, n=sum(len(v) for v in KAND.values()), sim=A.sim), u=KAND), ensure_ascii=False, separators=(",", ":"))
    ch = DN.log_changes({"laptop-citanje" + ("-proba" if A.sim else ""): LOGBUF[:]}) if LOGBUF else {}
    ch["public/data/zap/citanje.json"] = lambda old: body
    ch["public/data/zap/kandidati.json"] = lambda old: kb
    if DN.push(ch, f"Čitanje zapisnika: {sum(len(v) for v in RES.values())} BM, kandidata {sum(len(v) for v in KAND.values())}"): LOGBUF.clear()
    LASTPUSH[0] = time.time()
def getraw(name):
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(RAWU + name + "?t=" + str(int(time.time()) // 60), headers={"User-Agent": "kontrola-izbora"}), timeout=40).read())
    except Exception: return None
LIVE = {}; LIVET = {}
def rik_cached(uid, sid):
    if time.time() - LIVET.get(uid, 0) > 240:
        d = getraw(f"live/u/{uid}.json")
        if d: LIVE[uid] = d; LIVET[uid] = time.time()
    b = ((LIVE.get(uid) or {}).get("bm") or {}).get(sid)
    return b if b and b.get("processed") else None
OBL = {}; OBLT = [0.0]
def oblak_done(uid, sid, sha):
    if time.time() - OBLT[0] > 180:
        d = getraw("zap/oblak.json"); OBLT[0] = time.time()
        if d: OBL.clear(); OBL.update(d.get("u") or {})
    o = (OBL.get(uid) or {}).get(sid)
    return bool(o and (not o.get("sha") or o.get("sha") == sha))

FIELDS = [("izasli", "out", "izašli"), ("vazeci", "valid", "važeći"), ("nevazeci", "invalid", "nevažeći")]
def kand(uid, sid, h, why, extra=None):
    s = UNITS[uid]["st"].get(sid) or {}
    k = KAND.setdefault(uid, {}).get(sid)
    if k and k.get("sha") == h["sha"]:
        if why not in k["why"]: k["why"].append(why)
    else:
        KAND[uid][sid] = dict(n=s.get("n"), sha=h["sha"], link=h.get("link"), why=[why], at=now().strftime("%d.%m. %H:%M"))
    if extra: KAND[uid][sid].update(extra)

def check_ne(uid, sid, h, path, r):
    """Vraća listu neslaganja [oznaka, zapisnik, rik] (potvrđeno) ili None; upisuje r['zap']."""
    rik = rik_cached(uid, sid)
    if not rik: return None
    r["zap"] = dict(out=r.get("izasli"), valid=r.get("vazeci"), invalid=r.get("nevazeci"))
    diff = [f for f in FIELDS if r.get(f[0]) is not None and rik.get(f[1]) is not None and r[f[0]] != rik[f[1]]]
    if not diff: return []
    fresh = rik_fresh(uid, sid)
    if not fresh: log("RIK ne odgovara za", uid, sid); return None
    diff = [f for f in diff if fresh.get(f[1]) is not None and r[f[0]] != fresh[f[1]]]
    if not diff: return []
    r2 = read_rez(path, dpi=220, pad=0.01)
    same = [f for f in diff if r2.get(f[0]) == r[f[0]]]
    if len(same) < len(diff):
        kand(uid, sid, h, "nesigurno", dict(procitano=[r.get(f[0]) for f in diff], drugo=[r2.get(f[0]) for f in diff]))
        log("nesigurno čitanje", uid, sid, [(f[2], r[f[0]], r2.get(f[0]), fresh[f[1]]) for f in diff])
        return None
    return [[f[2], r[f[0]], fresh[f[1]]] for f in diff]

try: api("/api/tags")
except Exception as e: log("OLLAMA NE RADI:", e); publish(True); sys.exit(1)
cookie()
log("start provere zapisnika, model", A.model, "već pročitano", sum(len(v) for v in RES.values()))
PAGES = {}  # sha -> broj strana
while now() < UNTIL:
    try: IX = json.load(open(IXF, encoding="utf-8"))
    except Exception: IX = {}
    # 1) trijaža po broju strana
    per = collections.defaultdict(list); cur = []
    for uid, st in IX.items():
        if uid not in UNITS: continue
        for sid, hist in st.items():
            if not hist: continue
            h = hist[-1]; p = os.path.join(D, h["file"])
            if h["sha"] not in PAGES:
                try: PAGES[h["sha"]] = pages_of(p)
                except Exception: PAGES[h["sha"]] = None
            n = PAGES[h["sha"]]
            if n: per[uid].append(n)
            cur.append((uid, sid, h, p, n, len(hist)))
    norm = {}
    for uid, l in per.items():
        c = collections.Counter(l).most_common(1)[0]
        norm[uid] = c[0] if len(l) >= 8 and c[1] >= 0.5 * len(l) else int(NORM23.get(uid, 2))
    for uid, sid, h, p, n, nh in cur:
        if n and n > norm[uid]: kand(uid, sid, h, "strane", dict(strane=n, norma=norm[uid]))
    # 2) „!” za sve što oblak nije pročitao, pa 3) P15 za normalne dužine
    todo = []
    for uid, sid, h, p, n, nh in cur:
        r = (RES.get(uid) or {}).get(sid) or {}
        if r.get("sha") != h["sha"]: todo.append((0 if nh > 1 else 1, uid, sid, h, p, n)); continue
        if r.get("ne") is None and r.get("zap") is None and rik_cached(uid, sid): todo.append((2, uid, sid, h, p, n)); continue
        if r.get("ne") and not r.get("ne_chk_at") == h["sha"] + now().strftime("%H"): todo.append((3, uid, sid, h, p, n)); continue  # proveri da RIK nije ispravio (jednom na sat)
        if "p15" not in r and n and n <= norm.get(uid, 2): todo.append((4, uid, sid, h, p, n))
    todo.sort(key=lambda x: x[0])
    if not todo:
        save(); publish();
        if A.once: break
        time.sleep(30); continue
    for pri, uid, sid, h, p, n in todo[:15]:
        t = time.time(); s = UNITS[uid]["st"].get(sid) or {}
        r = (RES.get(uid) or {}).get(sid) or {}
        try:
            if r.get("sha") != h["sha"] or pri == 2:
                r = dict(sha=h["sha"], n=s.get("n"), pages=n, link=h.get("link"))
                if oblak_done(uid, sid, h["sha"]): r["oblak"] = 1
                else:
                    r.update(read_rez(p))
                    ne = check_ne(uid, sid, h, p, r)
                    if ne is not None: r["ne"] = ne
                    if ne: log("! RIK ≠ zapisnik:", uid, "BM", s.get("n"), ne)
            elif pri == 3:
                fresh = rik_fresh(uid, sid)
                if fresh:
                    still = [x for x in r["ne"] if (dict((f[2], f[1]) for f in FIELDS).get(x[0]) and fresh.get(dict((f[2], f[1]) for f in FIELDS)[x[0]]) != x[1])]
                    if len(still) < len(r["ne"]): log("RIK ispravio, gasim !:", uid, "BM", s.get("n"))
                    r["ne"] = [[x[0], x[1], fresh[dict((f[2], f[1]) for f in FIELDS)[x[0]]]] for x in still]
                r["ne_chk_at"] = h["sha"] + now().strftime("%H")
            elif pri == 4:
                v = read_p15(p); r["p15"] = v
                if v == "DA": kand(uid, sid, h, "p15"); log("P (polje 15):", uid, "BM", s.get("n"))
        except Exception as e:
            log("greška", uid, sid, e); r = dict(r, sha=h["sha"], err=str(e)[:200])
        r["at"] = now().strftime("%d.%m. %H:%M"); r["s"] = round(time.time() - t, 1)
        RES.setdefault(uid, {})[sid] = r
    save()
    log(f"pročitano {sum(len(v) for v in RES.values())}, kandidata {sum(len(v) for v in KAND.values())}, u redu {max(0, len(todo) - 15)}")
    publish()
    if A.once: break
save(); publish(True); log("kraj")
