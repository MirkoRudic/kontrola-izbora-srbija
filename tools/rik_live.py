# Izborna noć: prati RIK i objavljuje rezultate po BM za celu Srbiju.
#   python3 tools/rik_live.py [--minutes 55] [--sim] [--out public/data/live] [--no-push]
# Svaki krug: 191 upit za zbir po opštini (broj obrađenih + vreme ažuriranja) -> detaljno samo nova BM
# + spora rotacija već obrađenih BM (provera izmena rezultata / zamenjenog zapisnika).
# Interval: start 5 min; ima novih -> pola (min 1); nema -> x1.5 (max 15); sve obrađeno -> 30.
# --sim: proba na izborima 2023 (stanica 2026 -> uparena stanica 2023), BM se "otkrivaju" postepeno.
import json, os, sys, time, re, subprocess, random, datetime, argparse, hashlib
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
ap = argparse.ArgumentParser()
ap.add_argument('--minutes', type=float, default=55)
ap.add_argument('--sim', action='store_true')
ap.add_argument('--out', default='public/data/live')
ap.add_argument('--no-push', action='store_true')
ap.add_argument('--threads', type=int, default=8)
ap.add_argument('--fast', action='store_true', help='kratki intervali (za test)')
A = ap.parse_args()
R = "https://www.rik.parlament.gov.rs"; CK = "/tmp/rik_ck"
ROUND = "341140" if A.sim else "680072"
OUT = A.out; os.makedirs(OUT + "/u", exist_ok=True)
now = lambda: datetime.datetime.now(ZoneInfo("Europe/Belgrade"))
stamp = lambda: now().strftime("%d.%m. %H:%M")
def log(*a): print(now().strftime("%H:%M:%S"), *a, flush=True)

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
    if r["valid"] is not None and r["invalid"] is not None and r["valid"] + r["invalid"] != r["out"]:
        w.append(f"važeći + nevažeći ({r['valid']}+{r['invalid']}) ≠ izašlo ({r['out']})")
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
        L[sid] = rec_; return True
    diffk = [k for k in ("voters", "out", "valid", "invalid", "lists") if old.get(k) != new[k]]
    if diffk:
        old["alerts"].append(dict(type="rezultat", at=t, detail="RIK promenio: " + ", ".join(diffk), before={k: old.get(k) for k in diffk}))
        old.update(new); old["chk"] = checks(r, y23); changed = True
    if r["zlink"] and (not old["zap"] or old["zap"][-1]["link"] != r["zlink"]):
        if old["zap"]: old["alerts"].append(dict(type="zapisnik", at=t, detail="Zapisnik na RIK-u zamenjen novim fajlom"))
        old["zap"].append(dict(link=r["zlink"], at=t)); changed = True
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
        if done: U[uid] = dict(done=done, m=m, s26=s26, s23=s23, dt=(AGG.get(uid) or {}).get("dt"))
    return dict(meta=dict(checked=t, processed=P, stations=sum(len(u["st"]) for u in UNITS.values()), sim=A.sim), u=U)

def write(changed_units, t):
    for uid in changed_units:
        json.dump(LU[uid], open(f"{OUT}/u/{uid}.json", "w"), ensure_ascii=False, separators=(",", ":"))
    s = summary(t); json.dump(s, open(f"{OUT}/summary.json", "w"), ensure_ascii=False, separators=(",", ":"))
    return s

def push(msg):
    if A.no_push: return True
    subprocess.run(["git", "add", OUT], check=False)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0: return True
    subprocess.run(["git", "commit", "-qm", msg], check=False)
    for a in range(4):
        if subprocess.run(["git", "push", "-q"]).returncode == 0: return True
        subprocess.run(["git", "pull", "-q", "--rebase", "-X", "theirs"], check=False)  # pri rebase "theirs" = naše lokalne izmene live/
    log("PUSH NIJE USPEO"); return False

# ---------- glavna petlja ----------
cookie()
deadline = time.time() + A.minutes * 60
interval = 1.0 if A.fast else 5.0
total = sum(len(u["st"]) for u in UNITS.values())
PENDING = False; LASTPUSH = 0
while time.time() < deadline:
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
    s = write(changed, t)
    if changed: PENDING = True
    if PENDING and time.time() - LASTPUSH >= 90:  # Cloudflare gradi sajt posle svakog push-a: ne češće od 90 s
        if push(f"Uživo: obrađeno {s['meta']['processed']}/{total} BM ({t})"): PENDING = False; LASTPUSH = time.time()
    # interval
    if s["meta"]["processed"] >= total: interval = 30.0
    elif new: interval = max(1.0, interval / 2)
    else: interval = min(15.0, interval * 1.5)
    if A.fast: interval = min(interval, 1.0)
    log(f"krug: upita {len(todo)} novih {new} greške {err} promenjeno opština {len(changed)} obrađeno {s['meta']['processed']}/{total} trajanje {time.time()-t0:.0f}s sledeći za {interval:.1f} min")
    nxt = t0 + interval * 60
    if nxt > deadline: break
    time.sleep(max(5, nxt - time.time()))
if PENDING: push(f"Uživo: obrađeno {summary(stamp())['meta']['processed']}/{total} BM ({stamp()})")
log("kraj")
