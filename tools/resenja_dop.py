# Nova rešenja o biračkim odborima: priprema za čitanje sa slika (agenti) i upis u public/data/odbori_izm_dop.json.
#   python3 tools/resenja_dop.py spisak [--od 2026-10-23T17:00] [--deo 30]
#       -> preuzme PDF-ove novih rešenja (iz odbori_novi.json, kojih još nema u odbori_izm_dop.json),
#          napravi tekst i PNG strane u /tmp/resenja/, upiše /tmp/resenja/v1.json, v2.json ... (po --deo dokumenata)
#   python3 tools/resenja_dop.py upis      -> spoji /tmp/resenja/v*_out.json u odbori_izm_dop.json (+ kim_map.json), ne pravi commit
# Format izlaza agenta (v*_out.json): lista {"i","bm","k":"S"|"P","ch":[...],"napomena"}; KiM: u napomeni „opstina: <ime>”.
import sys, os, json, re, subprocess, urllib.parse, datetime, collections, unicodedata
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from parse_odb import gkey, lkey
P = os.path.join(HERE, "..", "public", "data") + "/"; W = "/tmp/resenja"; R = "https://www.rik.parlament.gov.rs"
TZ = ZoneInfo("Europe/Belgrade")
fold = lambda t: "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")
at = lambda ts: datetime.datetime.fromtimestamp(ts, TZ).strftime("%d.%m. %H:%M") if ts else ""
def J(f, d=None):
    try: return json.load(open(P + f, encoding="utf-8"))
    except Exception: return d
def dop_links(D): return {r["l"].split("#")[0] for v in D.values() for L in v.values() for r in L}
def spisak(od, deo):
    os.makedirs(W + "/pdf", exist_ok=True)
    N = J("odbori_novi.json", {}); D = J("odbori_izm_dop.json", {}); IDX = J("index.json")
    have = dop_links(D); t0 = datetime.datetime.fromisoformat(od).replace(tzinfo=TZ).timestamp()
    L = []; seen = set()
    for u, v in N.items():
        for n, docs in v.items():
            for d in docs:
                if d["l"] in have or d["l"] in seen or (d.get("ts") or 0) < t0: continue
                seen.add(d["l"]); t = d.get("t", "")
                L.append(dict(u=u, bm=str(n), t=t, l=d["l"], ts=d.get("ts") or 0, at=d.get("at") or at(d.get("ts")),
                              k="S" if "stalnom" in t else "P" if "proširen" in t.lower() else None))
    L.sort(key=lambda d: d["ts"])
    for i, d in enumerate(L): d["i"] = i
    def one(d):
        f = f"{W}/pdf/{d['i']}.pdf"
        for a in range(3):
            subprocess.run(["curl", "-sS", "--http1.1", "--max-time", "120", "-o", f, R + urllib.parse.quote(d["l"][len(R):])], capture_output=True)
            if os.path.exists(f) and open(f, "rb").read(5) == b"%PDF-": break
        else: return None
        t = subprocess.run(["pdftotext", "-layout", f, "-"], capture_output=True, text=True).stdout
        subprocess.run(["pdftoppm", "-r", "150", "-png", "-l", "8", f, f"{W}/pdf/{d['i']}"], capture_output=True)
        pngs = sorted(f"{W}/pdf/{x}" for x in os.listdir(W + "/pdf") if x.startswith(f"{d['i']}-") and x.endswith(".png"))
        ex = re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", t))[:6000] if len(t.strip()) > 200 else "(sken)"
        return dict(i=d["i"], opstina=IDX["units"][d["u"]]["name"], u=d["u"], bm=int(d["bm"]), naslov=d["t"], k=d["k"], tekst=ex, slike=pngs, pdf=f)
    with ThreadPoolExecutor(8) as ex: items = [x for x in ex.map(one, L) if x]
    json.dump(L, open(W + "/list.json", "w"), ensure_ascii=False)
    for f in os.listdir(W):
        if re.match(r"v\d+(_out)?\.json$", f): os.remove(f"{W}/{f}")
    ch = [items[j:j + deo] for j in range(0, len(items), deo)]
    for j, c in enumerate(ch): json.dump(c, open(f"{W}/v{j+1}.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(dict(novih=len(L), preuzeto=len(items), delova=len(ch), fajlovi=[f"{W}/v{j+1}.json" for j in range(len(ch))]), ensure_ascii=False))
def upis():
    L = {d["i"]: d for d in json.load(open(W + "/list.json"))}
    D = J("odbori_izm_dop.json", {}); IDX = J("index.json"); KMAP = J("kim_map.json", {})
    kr = [r["id"] for r in IDX["regions"] if "Kosov" in r["name"]][0]
    KN = {fold(v["name"]): u for u, v in IDX["units"].items() if v.get("region") == kr}
    outs = []
    for f in sorted(os.listdir(W)):
        if re.match(r"v\d+_out\.json$", f): outs += json.load(open(f"{W}/{f}"))
    g = {}
    for r in outs:
        key = (r["i"], str(r.get("bm")), r.get("k"))
        if key in g: g[key]["ch"] = (g[key].get("ch") or []) + (r.get("ch") or [])
        else: g[key] = dict(r, ch=list(r.get("ch") or []))
    outs = list(g.values()); kk = collections.defaultdict(set)
    for r in outs: kk[(r["i"], str(r.get("bm")))].add(r.get("k"))
    links = {L[r["i"]]["l"] for r in outs if r["i"] in L}
    for u in list(D):
        for n in list(D[u]):
            D[u][n] = [x for x in D[u][n] if x["l"].split("#")[0] not in links]
            if not D[u][n]: del D[u][n]
        if not D[u]: del D[u]
    put = lambda u, n, x: D.setdefault(u, {}).setdefault(str(n), []).append(x)
    st = collections.Counter()
    for r in outs:
        d = L.get(r["i"])
        if not d: continue
        u = d["u"]; bm = str(r.get("bm") or d["bm"]); k = r.get("k") or d.get("k") or "P"
        m = re.search(r"op[sš]tina:\s*([^;,.()|]+)", r.get("napomena") or "", re.I)
        if u in KN.values() and m:
            hit = KN.get(fold(m.group(1).strip()))
            if hit and hit != u:
                put(u, d["bm"], dict(l=d["l"], ts=d["ts"], at=d["at"], x=1, src="dop")); u = hit; st["kim"] += 1
            if hit: KMAP[d["l"][len(R):]] = [u, bm]
        ch = []
        for c in r.get("ch") or []:
            c = dict(c)
            if c.get("op") == "ime" and not c.get("old"): continue
            if c.get("by") and not c.get("key"): c["key"] = (lkey(c["by"]) or gkey(c["by"])) if k == "P" else (gkey(c["by"]) or lkey(c["by"]))
            ch.append(c)
        l = d["l"] + ("#" + k if len(kk[(r["i"], str(r.get("bm")))]) > 1 else "")
        if l != d["l"]: put(u, bm, dict(l=d["l"], ts=d["ts"], at=d["at"], x=1, src="dop"))
        put(u, bm, dict(l=l, ts=d["ts"], at=d["at"], k=k, ch=ch, src="dop")); st["dok"] += 1; st["promena"] += len(ch)
        if bm != str(d["bm"]) and str(d["bm"]) != "0": put(u, d["bm"], dict(l=d["l"], ts=d["ts"], at=d["at"], x=1, src="dop")); st["premesteno"] += 1
    for v in D.values():
        for x in v.values(): x.sort(key=lambda r: r.get("ts") or 0)
    json.dump(D, open(P + "odbori_izm_dop.json", "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump(KMAP, open(P + "kim_map.json", "w"), ensure_ascii=False, indent=0)
    print(json.dumps(dict(st), ensure_ascii=False))
if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if c == "spisak":
        od = sys.argv[sys.argv.index("--od") + 1] if "--od" in sys.argv else "2026-10-23T17:00"
        deo = int(sys.argv[sys.argv.index("--deo") + 1]) if "--deo" in sys.argv else 30
        spisak(od, deo)
    elif c == "upis": upis()
    else: print(__doc__ or "spisak | upis")
