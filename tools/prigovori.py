# Registar prigovora RIK-a (https://www.rik.parlament.gov.rs/prigovori/340927) – samo „Parlamentarni 2026”.
#   python3 tools/prigovori.py <izlaz.json>        (izlaz: public/data/zap/prigovori.json na grani uzivo)
# Imena podnosilaca koji su birači se NE upisuju (Mirko, 27.10.): samo „birač”; ime se upisuje za stranke, liste, poslaničke grupe i sl.
import json, os, re, sys, subprocess, time, datetime, html, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translit import lat
try:
    from zoneinfo import ZoneInfo; TZ = ZoneInfo("Europe/Belgrade")
except Exception: TZ = datetime.timezone(datetime.timedelta(hours=1))
R = "https://www.rik.parlament.gov.rs"; D = "public/data"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{D}/zap/prigovori.json"
IZBORI = "Парламентарни 2026"; OD = "20260801"   # registar ne filtrira po izborima na kasnijim stranama – čitamo do avgusta 2026.
IDX = json.load(open(f"{D}/index.json"))
def _core(x): return re.sub(r'^(gradska opština|grad|opština)\s+', '', lat(x).lower()).strip()
UC = {}
for uid, u in IDX["units"].items(): UC.setdefault(_core(re.sub(r'\s*\(.*\)', '', u["name"])), []).append(uid)
def get(url):
    for a in range(5):
        o = subprocess.run(["curl", "-sS", "--http1.1", "--max-time", "60", url], capture_output=True, text=True).stdout
        try: return json.loads(o)
        except Exception: time.sleep(3 + a * 3)
    return None
def ymd(s):  # "26.10.2026 12:54" -> "20261026"
    m = re.match(r"(\d+)\.(\d+)\.(\d{4})", s or ""); return f"{m.group(3)}{int(m.group(2)):02d}{int(m.group(1)):02d}" if m else ""
def kratko(s):  # "26.10.2026 12:54" -> "26.10. 12:54"
    m = re.match(r"(\d+)\.(\d+)\.\d{4}\s*(\d+:\d+)?", s or ""); return f"{int(m.group(1)):02d}.{int(m.group(2)):02d}. {m.group(3) or ''}".strip() if m else s
def txt(h): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(h or "")))).strip()
def links(h): return [R + urllib.parse.quote(html.unescape(l), safe="/:%") for l in re.findall(r"href=['\"]([^'\"]+)['\"]", str(h or ""))]
old = json.load(open(OUT)) if os.path.exists(OUT) else {}
oldi = {x["id"]: x for x in old.get("items", [])}
ids = []
for p in range(1, 400):
    d = get(f"{R}/get-objections?page={p}&lang=sr&order=0&sort=0&filters%5Belection-round%5D=680072")
    if not d or not d.get("records"): break
    for x in d["records"]: ids.append((x["objection_more"], x))
    if all(ymd(x["objection_admission_datetime"]) < OD for x in d["records"]): break
items = []
for i, x in ids:
    if ymd(x["objection_admission_datetime"]) < OD: continue
    o = oldi.get(i)
    if o and o.get("status") in ("Završen", "Povučen"): items.append(o); continue  # gotovi predmeti se ne menjaju
    d = get(f"{R}/get-objection?objectionId={i}")
    if not d:
        if o: items.append(o)
        continue
    F = {v.get("title", ""): v.get("data", "") for v in (d.values() if isinstance(d, dict) else d)}
    if txt(F.get("Назив избора")) != IZBORI: continue
    vp = lat(txt(F.get("Врста подносиоца")))
    pod = lat(txt(F.get("Име/Назив подносиоца"))) if vp and vp.lower() != "birač" else ""
    docs, odl, odl_at = [], "", ""
    for k, v in F.items():
        kl = lat(k)
        if kl in ("Naziv izbora", "Vrsta dokumenta", "Datum i vreme prijema", "Vrsta podnosioca", "Ime/Naziv podnosioca", "Nadležna izborna komisija", "Predmet prigovora/zahteva", "Status predmeta"): continue
        L = links(v)
        if not L and txt(v) in ("", "-"): continue
        t = lat(txt(v))
        m = re.search(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})", t)
        rez = re.sub(r"\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}(:\d{2})?", "", t).strip(" |")
        if kl.startswith("Odluka"):
            odl, odl_at = (rez or odl), (kratko(m.group(1) + " " + m.group(2)) if m else odl_at)
        for l in L[:1]: docs.append(dict(t=kl, link=l, at=kratko(m.group(1) + " " + m.group(2)) if m else ""))
    kom = lat(txt(F.get("Надлежна изборна комисија")))
    mun = lat(x.get("objection_municipality") or "")
    uid = (UC.get(_core(mun)) or [None])[0] if mun and mun != "RIK" else None
    items.append(dict(id=i, broj=x.get("objection_number"), at=kratko(x["objection_admission_datetime"]), ymd=ymd(x["objection_admission_datetime"]),
        vrsta=lat(txt(F.get("Врста документа"))), podnosilac_vrsta=vp, podnosilac=pod, komisija=kom, opstina=mun, uid=uid,
        predmet=lat(txt(F.get("Предмет приговора/захтева"))), status=lat(txt(F.get("Статус предмета"))), odluka=odl, odluka_at=odl_at, docs=docs))
    time.sleep(0.3)
items.sort(key=lambda z: (z["ymd"], z["at"]), reverse=True)
doc = dict(meta=dict(at=datetime.datetime.now(TZ).strftime("%d.%m. %H:%M"), n=len(items), posle=sum(1 for z in items if z["ymd"] >= "20261025"),
    izvor=R + "/prigovori/340927", napomena="Imena birača koji su podneli prigovor se ne prikazuju; nalaze se u originalnim dokumentima na RIK-u."), items=items)
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
json.dump(doc, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print("prigovora:", len(items), "posle izbora:", doc["meta"]["posle"])
