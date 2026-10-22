# Laptop, izborna noć: čita sačuvane zapisnike (RG-2) lokalnim modelom (Ollama, qwen2.5vl) i objavljuje rezultat čitanja.
#   python tools\laptop_citanje.py --dir D:\VAJB\kontrolaizbora\zapisnici [--until 2026-10-26T12:00] [--sim]
# Čita samo ono što RIK ne objavljuje kao podatak: prekid (8), kontrolni list (10, 10.1), primedbe (15), posmatrači (14), van BM (13),
# plus zbirove 11.1–11.4 radi poređenja sa RIK-om, i broj strana PDF-a (više od 2 = prilozi, najčešće primedbe).
# Redosled: BM sa upozorenjem provera i BM sa prilozima prvo, pa ostala po redu stizanja.
# Rezultat: <dir>\citanje.json i grana 'uzivo' -> public/data/zap/citanje.json (aplikacija), logovi/laptop-citanje.log
import sys, os
if os.name == 'nt' and not sys.flags.utf8_mode:
    os.execv(sys.executable, [sys.executable, '-X', 'utf8'] + sys.argv)
import json, time, base64, io, argparse, datetime, urllib.request
import pypdfium2 as P
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dnevnik as DN
ap = argparse.ArgumentParser()
ap.add_argument('--dir', required=True)
ap.add_argument('--until', default='2026-10-26T12:00')
ap.add_argument('--model', default='qwen2.5vl:7b')
ap.add_argument('--sim', action='store_true')
ap.add_argument('--no-push', action='store_true')
A = ap.parse_args()
if not DN.jedini("citanje" + ("-proba" if A.sim else "")): print("čitanje već radi – izlazim"); sys.exit(0)
D = A.dir; RES_F = os.path.join(D, "citanje.json"); IXF = os.path.join(D, "index.json")
RAW = "https://raw.githubusercontent.com/MirkoRudic/kontrola-izbora-srbija/uzivo/public/data/live/"
def now(): return datetime.datetime.now()
UNTIL = datetime.datetime.fromisoformat(A.until)
LOGBUF = []
def log(*a):
    s = " ".join(str(x) for x in a); print(now().strftime("%H:%M:%S"), s, flush=True); LOGBUF.append(s)
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
Q_TOK = ("Isečak srpskog izbornog zapisnika (obrazac RG-2, deo II), rukom popunjen. Vrati SAMO JSON: "
         '{"prekid": "DA"/"NE" (tačka 8, koje je zaokruženo), "kontrolni_list": "DA"/"NE" (tačka 10), "kontrolni_potpisan": "DA"/"NE" (tačka 10.1)}. '
         'Ako ništa nije zaokruženo, stavi null.')
Q_REZ = ("Isečak srpskog izbornog zapisnika (deo III, tačke 11.1–11.4), rukom popunjen. Vrati SAMO JSON: "
         '{"izasli": broj u 11.1, "u_kutiji": 11.2, "nevazeci": 11.3, "vazeci": 11.4}. Ako je polje prazno, stavi null (ne 0). Crtica = 0.')
Q_IV = ("Isečak srpskog izbornog zapisnika (deo IV, tačke 12–15), rukom popunjen. Vrati SAMO JSON: "
        '{"van_bm": broj iz tačke 13, "posmatraci": "DA"/"NE" (14, koje je zaokruženo), "primedbe": "DA"/"NE" (15, koje je zaokruženo)}. Crtica = 0, ništa zaokruženo = null.')
def read_pdf(path):
    pdf = P.PdfDocument(path); n = len(pdf)
    im = pdf[0].render(scale=150 / 72).to_pil(); pdf.close()
    W, H = im.size; out = dict(pages=n)
    if W < H:  # uspravno skeniran (jedna strana A4): ceo list, bez isecanja po polovinama
        out.update(ask(im, Q_TOK + " " + Q_REZ + " " + Q_IV)); return out
    out.update(ask(im.crop((0, int(H * .43), int(W * .48), int(H * .71))), Q_TOK))
    out.update(ask(im.crop((0, int(H * .70), int(W * .48), int(H * .89))), Q_REZ))
    out.update(ask(im.crop((int(W * .52), int(H * .69), W, int(H * .93))), Q_IV))
    return out
def flagged():
    """BM sa upozorenjem provera (iz objavljenih rezultata) -> prednost."""
    try:
        L = json.loads(urllib.request.urlopen(RAW + "log.json", timeout=30).read())
        return {(e["u"], str(e["s"])) for e in L if e.get("type") in ("provera", "oboreno", "izmena") and e.get("s")}
    except Exception: return set()
RES = json.load(open(RES_F, encoding="utf-8")) if os.path.exists(RES_F) else {}
def save():
    tmp = RES_F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(RES, f, ensure_ascii=False)
    os.replace(tmp, RES_F)
LASTPUSH = [0.0]
def publish(force=False):
    if A.no_push or (not force and time.time() - LASTPUSH[0] < 180): return
    body = json.dumps(dict(meta=dict(at=now().strftime("%d.%m. %H:%M"), n=sum(len(v) for v in RES.values()), sim=A.sim), u=RES), ensure_ascii=False, separators=(",", ":"))
    ch = DN.log_changes({"laptop-citanje" + ("-proba" if A.sim else ""): LOGBUF[:]}) if LOGBUF else {}
    ch["public/data/zap/citanje.json"] = lambda old: body
    if DN.push(ch, f"Čitanje zapisnika: {sum(len(v) for v in RES.values())} BM"): LOGBUF.clear()
    LASTPUSH[0] = time.time()
try: api("/api/tags")
except Exception as e: log("OLLAMA NE RADI:", e); publish(True); sys.exit(1)
log("start čitanja zapisnika, model", A.model, "već pročitano", sum(len(v) for v in RES.values()))
FL = set(); last_fl = 0
while now() < UNTIL:
    if time.time() - last_fl > 300: FL = flagged(); last_fl = time.time()
    try: IX = json.load(open(IXF, encoding="utf-8"))
    except Exception: IX = {}
    todo = []
    for uid, st in IX.items():
        for sid, hist in st.items():
            if not hist: continue
            h = hist[-1]
            if (RES.get(uid) or {}).get(sid, {}).get("sha") == h["sha"]: continue
            pri = 0 if (uid, sid) in FL else 1 if len(hist) > 1 else 2
            todo.append((pri, h.get("at", ""), uid, sid, h))
    todo.sort()
    if not todo:
        publish(); time.sleep(30); continue
    for pri, _, uid, sid, h in todo[:20]:
        t = time.time()
        try: r = read_pdf(os.path.join(D, h["file"]))
        except Exception as e: log("greška", uid, sid, e); r = dict(err=str(e)[:200])
        r.update(sha=h["sha"], at=now().strftime("%d.%m. %H:%M"), s=round(time.time() - t, 1))
        RES.setdefault(uid, {})[sid] = r
        if r.get("primedbe") == "DA" or r.get("prekid") == "DA" or r.get("kontrolni_list") == "NE" or r.get("pages", 2) > 2:
            log("ZNAK:", uid, sid, {k: r.get(k) for k in ("pages", "prekid", "kontrolni_list", "primedbe")})
    save(); log(f"pročitano ukupno {sum(len(v) for v in RES.values())}, u redu {max(0, len(todo) - 20)}")
    publish()
publish(True); log("kraj")
