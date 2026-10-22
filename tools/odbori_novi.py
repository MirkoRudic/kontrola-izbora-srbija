# Nova rešenja o biračkim odborima i komisijska rešenja na RIK-u (cela Srbija).
# RIK spisak je sortiran od najnovijeg: čitamo strane dok ne naiđemo na već poznate dokumente.
#   python3 tools/odbori_novi.py
# Piše: public/data/odbori_known.json (poznati id-jevi), public/data/odbori_novi.json (nova rešenja po BM), public/data/odbori_log.json (dnevnik)
import json, os, re, sys, time, subprocess, hashlib, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translit import lat
try:
    from zoneinfo import ZoneInfo; TZ = ZoneInfo("Europe/Belgrade")
except Exception: TZ = None
R = "https://www.rik.parlament.gov.rs"; D = "public/data"
stamp = lambda: datetime.datetime.now(TZ).strftime("%d.%m. %H:%M")
def page(p, dt):
    for a in range(6):
        o = subprocess.run(["curl", "-sS", "--http1.1", "--max-time", "90", "-G", R + "/get-additional-documents",
            "--data-urlencode", f"page={p}", "--data-urlencode", f"filters[document-type]={dt}",
            "--data-urlencode", "filters[election-round]=680072", "--data-urlencode", "filters[municipality-id]=0",
            "--data-urlencode", "filters[election_station]=0", "--data-urlencode", "filters[additional-document]=0",
            "--data-urlencode", "order=0", "--data-urlencode", "sort=0", "--data-urlencode", "election_type=-1"], capture_output=True, text=True).stdout
        try:
            d = json.loads(o); assert "records" in d; return d["records"]
        except Exception: time.sleep(3 + a * 5)
    raise RuntimeError("RIK nedostupan")
IDX = json.load(open(f"{D}/index.json"))
def _core(x): return re.sub(r'^(gradska opština|grad|opština)\s+', '', lat(x).lower()).strip()
UC = {}
for uid, u in IDX["units"].items(): UC.setdefault(_core(re.sub(r'\s*\(.*\)', '', u["name"])), []).append(uid)
K = json.load(open(f"{D}/odbori_known.json")); known = set(K["known"])
NOVI = json.load(open(f"{D}/odbori_novi.json")) if os.path.exists(f"{D}/odbori_novi.json") else {}
LOG = json.load(open(f"{D}/odbori_log.json")) if os.path.exists(f"{D}/odbori_log.json") else []
t = stamp(); new = []
for dt in (4, 1):
    for p in range(1, 400):
        recs = page(p, dt); fresh = 0
        for d in recs:
            for l in re.findall(r'href="([^"]+)"', str(d.get("extfiles_link"))):
                h = hashlib.md5(l.encode()).hexdigest()[:12]
                if h in known: continue
                known.add(h); fresh += 1; new.append((dt, d, l))
        if not recs or fresh == 0: break
UFC = {}
def kind(t):
    t = (t or '').lower()
    return 'S' if 'stalnom' in t else 'P' if 'prošir' in t else None
def prev_doc(uid, n, ts, title):
    if uid not in UFC: UFC[uid] = {str(x['n']): x.get('odb', []) for x in json.load(open(f'{D}/u/{uid}.json'))['stations']}
    ds = UFC[uid].get(str(n), []) + NOVI.get(uid, {}).get(str(n), [])
    ds = [d for d in ds if (d.get('ts') or 0) < ts]
    k = kind(title)
    if k and any(kind(d['t']) == k for d in ds): ds = [d for d in ds if kind(d['t']) == k]
    return max(ds, key=lambda d: d.get('ts') or 0)['l'] if ds else None
for dt, d, l in sorted(new, key=lambda x: int(x[1].get('datetime') or 0)):
    mn = d.get("municipality_display_name") or ""
    uids = UC.get(_core(mn), [])
    if len(uids) > 1: uids = [u for u in uids if ("Niš" in IDX["units"][u]["name"]) == ("Ниш" in (d.get("document_bearer") or ""))] or uids
    m = re.match(r"\s*(\d+)", d.get("election_station_title") or "")
    title = re.sub(r"<[^>]+>", "", d.get("election_board_decision") or d.get("document_name") or "Rešenje")
    title = lat(re.sub(r"\s+", " ", title).strip())
    ts = int(d.get("datetime") or 0)
    at = datetime.datetime.fromtimestamp(ts, TZ).strftime("%d.%m. %H:%M") if ts else t
    e = dict(t=title, l=R + l, ts=ts, at=at)
    if uids and m:
        uid, n = uids[0], m.group(1)
        pv = prev_doc(uid, n, ts, title)
        NOVI.setdefault(uid, {}).setdefault(n, []).append(e)
        LOG.append(dict(at=at, u=uid, n=int(n), type="odbor", detail=title, l=R + l, prev=pv))
    elif uids:
        NOVI.setdefault(uids[0], {}).setdefault("0", []).append(e)
        LOG.append(dict(at=at, u=uids[0], n=None, type="odbor", detail=title, l=R + l))
K["known"] = sorted(known); K["checked"] = t
json.dump(K, open(f"{D}/odbori_known.json", "w"), separators=(",", ":"))
json.dump(NOVI, open(f"{D}/odbori_novi.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(LOG, open(f"{D}/odbori_log.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump({"checked": t}, open(f"{D}/odbori_provera.json", "w"))
print("novih dokumenata:", len(new), "| provera", t)
