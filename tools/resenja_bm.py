# Rešenja izbornih komisija (RIK, dodatni dokumenti tip 1) od dana izbora, povezana sa biračkim mestom.
#   python3 tools/resenja_bm.py <izlaz.json>       (izlaz: public/data/zap/resenja.json na grani uzivo)
# Broj BM: iz naziva dokumenta; ako ga nema – OCR prve strane (tesseract, srp). Već obrađeni linkovi se ne čitaju ponovo.
# Ruma okačuje zapisnike kao „PA42” / „PA42-RG-11” – to su zapisnici BM 42 (vrsta „dokument”).
import json, os, re, sys, subprocess, tempfile, datetime, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translit import lat
try:
    from zoneinfo import ZoneInfo; TZ = ZoneInfo("Europe/Belgrade")
except Exception: TZ = datetime.timezone(datetime.timedelta(hours=1))
R = "https://www.rik.parlament.gov.rs"; D = "public/data"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{D}/zap/resenja.json"
T0 = datetime.datetime(2026, 10, 25, 7, 0, tzinfo=TZ).timestamp()
RX = re.compile(r"(?:БМ|Б\.\s?М\.|БО|BM|BO|бирачк\w*\s+мест\w*|biračk\w*\s+mest\w*)\s*(?:бр\.?|број|br\.?|broj)?\s*(\d+)", re.I)
NEPON = re.compile(r"ОДБАЦ|ОДБИ[ЈJ]|НЕОСНОВАН", re.I)
IDX = json.load(open(f"{D}/index.json"))
def _core(x): return re.sub(r'^(gradska opština|grad|opština)\s+', '', lat(x).lower()).strip()
UC = {}
for uid, u in IDX["units"].items(): UC.setdefault(_core(re.sub(r'\s*\(.*\)', '', u["name"])), []).append(uid)
ST = {}
def sid_of(uid, n):
    if uid not in ST: ST[uid] = {s["n"]: s["sid"] for s in json.load(open(f"{D}/u/{uid}.json"))["stations"]}
    return ST[uid].get(n)
def page(p):
    for a in range(5):
        o = subprocess.run(["curl", "-sS", "--http1.1", "--max-time", "60", "-G", R + "/get-additional-documents", "--data-urlencode", f"page={p}",
            "--data-urlencode", "filters[document-type]=1", "--data-urlencode", "filters[election-round]=680072", "--data-urlencode", "filters[municipality-id]=0",
            "--data-urlencode", "filters[election_station]=0", "--data-urlencode", "filters[additional-document]=0", "--data-urlencode", "order=0",
            "--data-urlencode", "sort=0", "--data-urlencode", "election_type=-1"], capture_output=True, text=True).stdout
        try: return json.loads(o)["records"]
        except Exception: pass
    return None
def ocr_bm(url):
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "d.pdf")
        subprocess.run(["curl", "-sS", "--http1.1", "-m", "90", "-o", f, url])
        subprocess.run(["pdftoppm", "-r", "200", "-f", "1", "-l", "1", "-png", f, os.path.join(td, "s")])
        im = [x for x in os.listdir(td) if x.endswith(".png")]
        if not im: return None
        t = subprocess.run(["tesseract", os.path.join(td, im[0]), "-", "-l", "srp"], capture_output=True, text=True).stdout
        ns = re.findall(r"бирачк\w*\s+мест\w*\s+(?:бр\.?|број)\s*(\d+)", t, re.I)
        return int(max(set(ns), key=ns.count)) if ns else None
old = json.load(open(OUT)) if os.path.exists(OUT) else {}
seen = old.get("seen", {})  # link -> [uid, sid, n] ili null
out = {}
for p in range(1, 40):
    recs = page(p)
    if not recs: break
    stari = 0
    for d in recs:
        if int(d.get("datetime") or 0) < T0: stari += 1; continue
        name = re.sub(r"\s+", " ", (d.get("document_name") or "")).strip()
        dt = d.get("decision_type") or ""
        links = re.findall(r'href="([^"]+)"', str(d.get("extfiles_link")))
        if not links: continue
        url = R + urllib.parse.quote(links[0])
        pa = re.match(r"PA(\d+)", lat(name))
        if not (dt in ("РЕШЕЊЕ", "ЗАКЉУЧАК") or pa): continue
        uids = UC.get(_core(d.get("municipality_display_name") or ""), [])
        if not uids: continue
        uid = uids[0]
        if url in seen: hit = seen[url]
        else:
            m = RX.search(name); n = int(pa.group(1)) if pa else int(m.group(1)) if m else ocr_bm(url)
            s = sid_of(uid, n) if n else None
            hit = seen[url] = [uid, s, n] if s else None
        if not hit: continue
        uid, sid, n = hit
        vr = "dokument" if pa else "neutvrdjeno" if re.search(r"НЕ\s+МОГУ\s+(СЕ\s+)?УТВРДИТИ", name, re.I) else ("odbaceno" if NEPON.search(name) else "ponisteno") if re.search(r"ПОНИШТ", name, re.I) else "ispravka" if re.search(r"ИСПРАВ|ИЗМЕН", name, re.I) else "resenje"
        at = datetime.datetime.fromtimestamp(int(d["datetime"]), TZ).strftime("%d.%m. %H:%M")
        naz = ("Zapisnik BM %d (okačen kao dodatni dokument)" % n) if pa and "RG-11" not in lat(name) else ("Zapisnik o posmatračima BM %d (okačen kao dodatni dokument)" % n) if pa else lat(name)[:220]
        out.setdefault(uid, {}).setdefault(sid, []).append(dict(at=at, naziv=naz, link=url, vrsta=vr, ko=lat(d.get("document_bearer") or "")[:120]))
    if stari == len(recs): break
# RIK ume da prekine listanje (ograničenje upita) – nikad ne gubimo ranije nađena rešenja
for u, v in old.get("u", {}).items():
    for sid, L in v.items():
        have = {x["link"] for x in out.get(u, {}).get(sid, [])}
        for x in L:
            if x["link"] not in have: out.setdefault(u, {}).setdefault(sid, []).append(x); have.add(x["link"])
for u in out.values():
    for k in list(u):
        seen_l = set(); u[k] = [x for x in u[k] if not (x["link"] in seen_l or seen_l.add(x["link"]))]
    for L in u.values(): L.sort(key=lambda x: x["at"][3:5] + x["at"][:2] + x["at"][6:])
n = sum(len(L) for u in out.values() for L in u.values())
doc = dict(meta=dict(at=datetime.datetime.now(TZ).strftime("%d.%m. %H:%M"), n=n, bm=sum(len(u) for u in out.values())), u=out, seen=seen)
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
json.dump(doc, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print("rešenja:", n, "na", doc["meta"]["bm"], "BM; bez BM:", sum(1 for v in seen.values() if not v))
