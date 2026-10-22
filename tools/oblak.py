# Oblak (Claude zakazani zadatak): detaljno čitanje kandidata koje je laptop izdvojio (duži zapisnik, P u polju 15, nesigurno čitanje).
#   python3 tools/oblak.py lista [--max 6]     -> preuzme PDF-ove sledećih kandidata, napravi PNG strane, ispiše JSON sa putanjama
#   python3 tools/oblak.py upis rezultat.json  -> upiše pročitano u public/data/zap/oblak.json na grani 'uzivo' (spaja sa postojećim)
#   python3 tools/oblak.py stanje              -> koliko kandidata čeka
# Format jednog upisa (rezultat.json je lista ovakvih):
#   {"u":"84","sid":"222927","sha":"...","n":22,
#    "p":[{"v":"Ubacivanje listića","t":"Član odbora (lista 3) navodi da ..."}],   # prazna lista = nema primedbi
#    "zap":{"voters":287,"out":151,"valid":142,"invalid":9,"lists":{"1":58,"2":12,"3":41,...}},
#    "ne":[["izašli",151,157]]}                                                   # računa se ovde iz "zap" i RIK-a; ne popunjavaj ručno
import sys, os, json, time, subprocess, urllib.request, datetime, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import dnevnik as DN
RAWU = "https://raw.githubusercontent.com/MirkoRudic/kontrola-izbora-srbija/uzivo/public/data/"
WD = os.path.join(tempfile.gettempdir(), "oblak"); os.makedirs(WD, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (kontrola-izbora)"}
def raw(name):
    for a in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(RAWU + name + "?t=" + str(int(time.time())), headers=UA), timeout=60).read())
        except Exception: time.sleep(3)
    return None
def stamp():
    try:
        from zoneinfo import ZoneInfo; return datetime.datetime.now(ZoneInfo("Europe/Belgrade")).strftime("%d.%m. %H:%M")
    except Exception: return datetime.datetime.now().strftime("%d.%m. %H:%M")
def pending():
    K = (raw("zap/kandidati.json") or {}).get("u") or {}; O = (raw("zap/oblak.json") or {}).get("u") or {}
    out = []
    for uid, d in K.items():
        for sid, k in d.items():
            o = (O.get(uid) or {}).get(sid)
            if o and o.get("sha") == k.get("sha"): continue
            pr = 0 if "nesigurno" in k.get("why", []) else 1 if "p15" in k.get("why", []) else 2
            out.append((pr, k.get("at", ""), uid, sid, k))
    out.sort(key=lambda x: (x[0], x[1]))
    return out
def lista(mx):
    res = []
    for pr, at, uid, sid, k in pending()[:mx]:
        if not k.get("link"): continue
        f = os.path.join(WD, f"{uid}_{sid}.pdf")
        try:
            b = urllib.request.urlopen(urllib.request.Request(k["link"], headers=UA), timeout=120).read()
            if b[:5] != b"%PDF-": raise ValueError("nije PDF")
            open(f, "wb").write(b)
        except Exception as e:
            res.append(dict(u=uid, sid=sid, greska=str(e)[:200])); continue
        pre = os.path.join(WD, f"{uid}_{sid}")
        subprocess.run(["pdftoppm", "-r", "110", "-png", f, pre], capture_output=True)
        pngs = sorted(x for x in os.listdir(WD) if x.startswith(f"{uid}_{sid}-") and x.endswith(".png"))
        live = (raw(f"live/u/{uid}.json") or {}).get("bm", {}).get(sid) or {}
        res.append(dict(u=uid, sid=sid, sha=k.get("sha"), n=k.get("n"), zasto=k.get("why"), link=k.get("link"),
                        strane=[os.path.join(WD, x) for x in pngs],
                        rik=({kk: live.get(kk) for kk in ("voters", "out", "valid", "invalid", "lists")} if live.get("processed") else None)))
    print(json.dumps(dict(ceka=len(pending()), sledeci=res), ensure_ascii=False, indent=1))
LBL = {"voters": "upisani", "out": "izašli", "valid": "važeći", "invalid": "nevažeći"}
R = "https://www.rik.parlament.gov.rs"
def rik_fresh(uid, sid, sim):
    """Svež upit RIK-u za jedno BM (pre upisa „!”)."""
    import http.cookiejar, urllib.parse
    PD = os.path.join(HERE, "..", "public", "data")
    try:
        reg = json.load(open(os.path.join(PD, "index.json"), encoding="utf-8"))["units"][uid]["region"]
        st = {s["sid"]: s for s in json.load(open(os.path.join(PD, "u", uid + ".json"), encoding="utf-8"))["stations"]}[sid]
    except Exception: return None
    q = st.get("m23") if sim else sid
    if not q: return None
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())); op.addheaders = list(UA.items())
    for a in range(3):
        try:
            op.open(R + "/542645/rezultati/", timeout=60).read()
            rq = urllib.request.Request(R + "/get_results/", data=urllib.parse.urlencode(dict(should_update_pies=1, type=2, election_round="341140" if sim else "680072", region=reg, municipality=uid, election_station=q)).encode(),
                                        headers={"X-Requested-With": "XMLHttpRequest", "Referer": R + "/542645/rezultati/"})
            d = json.loads(op.open(rq, timeout=60).read()); s = d.get("stat_sum_numbers") or {}
            num = lambda x: int(str(x).replace('.', '') or 0)
            if num(s.get("processed_stations", 0)) == 0: return None
            v, iv = [int(x) for x in d["sum_config"]["data"]["datasets"][0]["data"][:2]]
            lists = [0] * 18
            for l in d.get("table_data") or []:
                i = int(l["count_number"]) - 1
                if 0 <= i < 18: lists[i] = num(l["won_number"])
            return dict(processed=True, voters=num(s.get("total_voters", 0)), out=num(s.get("available", 0)), valid=v, invalid=iv, lists=lists)
        except Exception: time.sleep(3)
    return None
SIM = [None]
def neslaganja(uid, sid, z):
    live = (raw(f"live/u/{uid}.json") or {}).get("bm", {}).get(sid) or {}
    if live.get("processed") and z and any(z.get(k) is not None and live.get(k) is not None and int(z[k]) != int(live[k]) for k in LBL) or any(
            v is not None and live.get("lists") and int(v) != live["lists"][int(i) - 1] for i, v in ((z or {}).get("lists") or {}).items()):
        if SIM[0] is None: SIM[0] = bool(((raw("zap/kandidati.json") or {}).get("meta") or {}).get("sim"))
        f = rik_fresh(uid, sid, SIM[0])
        if f: live = f
    if not live.get("processed") or not z: return None
    ne = [[LBL[k], z[k], live[k]] for k in LBL if z.get(k) is not None and live.get(k) is not None and int(z[k]) != int(live[k])]
    for i, v in (z.get("lists") or {}).items():
        try:
            r = live["lists"][int(i) - 1]
            if v is not None and int(v) != int(r): ne.append([f"lista {int(i)}", int(v), r])
        except Exception: pass
    return ne
def upis(path):
    items = json.load(open(path, encoding="utf-8")); t = stamp(); lines = []
    def merge(old):
        d = json.loads(old) if old.strip() else {"meta": {}, "u": {}}
        for it in items:
            uid, sid = str(it["u"]), str(it["sid"])
            rec = dict(sha=it.get("sha"), n=it.get("n"), at=t, p=it.get("p") or [], zap=it.get("zap"), link=it.get("link"))
            ne = neslaganja(uid, sid, it.get("zap"))
            if ne is not None: rec["ne"] = ne
            d["u"].setdefault(uid, {})[sid] = rec
            lines.append(f"BM {it.get('n')} ({uid}/{sid}): primedbi {len(rec['p'])}" + (f", ! {ne}" if ne else ""))
        d["meta"] = dict(at=t, n=sum(len(v) for v in d["u"].values()))
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    ch = DN.log_changes({"oblak": lines or ["upis bez stavki"]})
    ch["public/data/zap/oblak.json"] = merge
    ok = DN.push(ch, f"Oblak: pročitano {len(items)} kandidata")
    print("upisano" if ok else "GREŠKA pri upisu", len(items))
if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "stanje"
    if c == "lista": lista(int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 6)
    elif c == "upis": upis(sys.argv[2])
    else: print(len(pending()), "kandidata čeka")
