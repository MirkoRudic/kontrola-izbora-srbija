# Oblak (Claude zakazani zadatak): detaljno čitanje kandidata koje je laptop izdvojio (duži zapisnik, P u polju 15, nesigurno čitanje).
#   python3 tools/oblak.py lista [--max 6]     -> preuzme PDF-ove sledećih kandidata, napravi PNG strane, ispiše JSON sa putanjama
#   python3 tools/oblak.py upis rezultat.json  -> upiše pročitano u public/data/zap/oblak.json na grani 'uzivo' (spaja sa postojećim)
#   python3 tools/oblak.py stanje              -> koliko kandidata čeka
# Format jednog upisa (rezultat.json je lista ovakvih):
#   {"u":"84","sid":"222927","sha":"...","n":22,
#    "p":[{"v":"Ubacivanje listića","t":"Član odbora (lista 3) navodi da ..."}],   # prazna lista = nema primedbi
#    "uoc":[{"v":"Ispravke u zapisniku","t":"..."}],   # ono što se uočava u zapisniku, a nije primedba člana odbora (nije obavezno)
#    "zap":{"voters":287,"out":151,"valid":142,"invalid":9,"lists":{"1":58,"2":12,"3":41,...}},
#    "bmz":22,                                                                     # broj BM upisan u samom zapisniku (polje 1)
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
            w = k.get("why", []); pr = 0 if "neslaganje" in w else 1 if "nesigurno" in w else 2 if "p15" in w else 3
            out.append((pr, k.get("at", ""), uid, sid, k))
    out.sort(key=lambda x: (x[0], x[1]))
    return out
def _shard(sid, sh):
    if not sh: return True
    k, n = map(int, sh.split("/")); import zlib
    return zlib.crc32(str(sid).encode()) % n == k
def lista(mx, sh=None):
    res = []
    for pr, at, uid, sid, k in [x for x in pending() if _shard(x[3], sh)][:mx]:
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
        res.append(dict(u=uid, sid=sid, sha=k.get("sha"), n=k.get("n"), zasto=k.get("why"), sumnja=k.get("sumnja"), link=k.get("link"),
                        strane=[os.path.join(WD, x) for x in pngs],
                        rik=({kk: live.get(kk) for kk in ("voters", "out", "valid", "invalid", "lists")} if live.get("processed") else None)))
    print(json.dumps(dict(ceka=len([x for x in pending() if _shard(x[3], sh)]), sledeci=res), ensure_ascii=False, indent=1))
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
def cisti(ne, z):
    """Izbacuje očigledne greške čitanja (ne neslaganja RIK–zapisnik): broj pisan između kosih crta (/61/ pročitano kao 161),
    važeći ≠ zbir lista iz istog zapisnika a RIK = zbir, izašlih više od upisanih. Vraća (ne, sumnjivo)."""
    z = z or {}; L = z.get("lists") or {}
    S = sum(int(v) for v in L.values()) if len(L) == 18 and all(v is not None for v in L.values()) else None
    ok, mr = [], []
    for x in ne:
        lab, zv, rv = x[0], x[1], x[2]
        a, b = str(zv), str(rv)
        why = "kose" if a in ("1" + b, b + "1", "1" + b + "1") else None
        if not why and lab == "važeći" and S is not None and int(zv) != S and int(rv) == S: why = "zbir"
        if not why and lab == "izašli" and z.get("voters") and int(zv) > int(z["voters"]) >= int(rv): why = "upisani"
        if why: mr.append([lab, zv, rv, why])
        else: ok.append(x)
    # dodatno: zapisnik se ne slaže sam sa sobom, a RIK-ov broj ga „popravlja” → greška čitanja, ne neslaganje
    R = {x[0]: int(x[2]) for x in ne}; g = lambda k: None if z.get(k) is None else int(z[k])
    va, iv, out = g("valid"), g("invalid"), g("out"); Ls = {int(k): int(v) for k, v in L.items() if v is not None}
    S2 = sum(Ls.values()) if len(Ls) >= 12 else None; va_fix = S2 if (S2 is not None and "važeći" in R and S2 == R["važeći"]) else va
    def bad(x):
        lab = x[0]
        if lab.startswith("lista ") and S2 is not None and va is not None and S2 != va:
            i = int(lab.split()[1]); return S2 - Ls.get(i, 0) + int(x[2]) in (va, R.get("važeći"))
        if lab == "izašli" and out is not None and iv is not None:
            return any(vv is not None and vv + iv == int(x[2]) and out != vv + iv for vv in (va, va_fix))
        if lab == "nevažeći" and out is not None and va_fix is not None and (S2 is None or S2 == va_fix):
            return out - va_fix == int(x[2]) and iv != out - va_fix
        return False
    ok2 = []
    for x in ok:
        if bad(x): mr.append([x[0], x[1], x[2], "zapisnik sam sa sobom"])
        else: ok2.append(x)
    return ok2, mr
def upis(path):
    items = json.load(open(path, encoding="utf-8")); t = stamp(); lines = []; RECS = []
    for it in items:
        uid, sid = str(it["u"]), str(it["sid"])
        rec = dict(sha=it.get("sha"), n=it.get("n"), at=t, p=it.get("p") or [], zap=it.get("zap"), link=it.get("link"))
        if it.get("uoc"): rec["uo"] = it["uoc"]
        bmz = it.get("bmz")
        if bmz is not None and it.get("n") is not None and str(bmz).strip() != str(it.get("n")).strip():
            # 2) na RIK-u je okačen zapisnik drugog BM: beleži se, bez „!”
            rec["wz"] = str(bmz); ne = None
            lines.append(f"BM {it.get('n')} ({uid}/{sid}): na RIK-u je okačen zapisnik BM {bmz} – upisano kao greška RIK-a, bez „!”")
        else: ne = neslaganja(uid, sid, it.get("zap"))
        if ne is not None:
            ne, mr = cisti(ne, it.get("zap"))
            if mr: rec["mr"] = mr
            rec["ne"] = [x for x in ne if x[0] != "upisani"]; nu = [x for x in ne if x[0] == "upisani"]
            if nu: rec["nu"] = nu
        RECS.append((uid, sid, rec))
        lines.append(f"BM {it.get('n')} ({uid}/{sid}): primedbi {len(rec['p'])}" + (f", ! {ne}" if ne else ""))
    def merge(old):
        d = json.loads(old) if old.strip() else {"meta": {}, "u": {}}
        for uid, sid, rec in RECS: d["u"].setdefault(uid, {})[sid] = rec
        d["meta"] = dict(at=t, n=sum(len(v) for v in d["u"].values()))
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    ch = DN.log_changes({"oblak": lines or ["upis bez stavki"]})
    ch["public/data/zap/oblak.json"] = merge
    ok = DN.push(ch, f"Oblak: pročitano {len(items)} kandidata")
    print("upisano" if ok else "GREŠKA pri upisu", len(items))
def provera_ne():
    """Za BM sa „!”: svež RIK; ako je RIK ispravio, „!” se gasi (bez ponovnog čitanja)."""
    O = (raw("zap/oblak.json") or {}).get("u") or {}; SIM[0] = bool(((raw("zap/kandidati.json") or {}).get("meta") or {}).get("sim"))
    todo = [(u, s_, r) for u, d in O.items() for s_, r in d.items() if r.get("ne")]
    upd = {}
    for u, s_, r in todo:
        f = rik_fresh(u, s_, SIM[0]); z = r.get("zap") or {}
        if not f: continue
        ne = [[LBL[k], z[k], f[k]] for k in LBL if z.get(k) is not None and f.get(k) is not None and int(z[k]) != int(f[k])]
        for i, v in (z.get("lists") or {}).items():
            if v is not None and int(v) != f["lists"][int(i) - 1]: ne.append([f"lista {int(i)}", int(v), f["lists"][int(i) - 1]])
        ne = [x for x in cisti(ne, z)[0] if x[0] != "upisani"]
        if ne != r["ne"]: upd[(u, s_)] = ne
    if not upd: print("„!” bez promene:", len(todo)); return
    def merge(old):
        d = json.loads(old)
        for (u, s_), ne in upd.items(): d["u"][u][s_]["ne"] = ne
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    ch = DN.log_changes({"oblak": [f"RIK ispravio – „!” ažuriran: {u}/{s_} -> {ne}" for (u, s_), ne in upd.items()]})
    ch["public/data/zap/oblak.json"] = merge
    print("ažurirano" if DN.push(ch, "Oblak: provera „!” uz svež RIK") else "GREŠKA", len(upd))
if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "stanje"
    if c == "lista": lista(int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 6, sys.argv[sys.argv.index("--shard") + 1] if "--shard" in sys.argv else None)
    elif c == "upis": upis(sys.argv[2])
    elif c == "provera": provera_ne()
    else: print(len(pending()), "kandidata čeka")
