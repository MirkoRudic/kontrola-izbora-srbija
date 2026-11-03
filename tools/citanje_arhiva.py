# Čitanje arhivskih zapisnika (RG-2) lokalnim modelom (Ollama, qwen2.5vl) – parlamentarni izbori 2022 (dodato 3.11.2026).
#   python tools/citanje_arhiva.py --izbori 2022 --dir D:\VAJB\kontrolaizbora\arhiva [--max 20] [--until 2026-11-04T09:00]
# Za izbore za koje RIK nema rezultate po BM (2022, 2020) rezultat se čita iz zapisnika:
#   upisani (4), izašli (11.1), u kutiji (11.2), nevažeći (11.3), važeći (11.4) i glasovi za svaku listu (11.5).
# Provera bez RIK-a: zbir glasova lista = važeći, u kutiji = nevažeći + važeći. Ako ne prolazi, čita se ponovo na većoj
# rezoluciji; ako ni tada ne prolazi, BM dobija status „sumnja” i ide na detaljno čitanje (oblak).
# Rezultat: <dir>/<izbori>/citanje.json  {link: {...}}; nastavlja gde je stao.
import sys, os
if os.name == 'nt' and not sys.flags.utf8_mode:
    os.execv(sys.executable, [sys.executable, '-X', 'utf8'] + sys.argv)
import json, time, base64, io, argparse, datetime, re, urllib.request
import pypdfium2 as P
ap = argparse.ArgumentParser()
ap.add_argument('--izbori', default='2022')
ap.add_argument('--dir', required=True)
ap.add_argument('--model', default='qwen2.5vl:7b')
ap.add_argument('--max', type=int, default=0)
ap.add_argument('--until', default=None)
ap.add_argument('--liste', type=int, default=19)
A = ap.parse_args()
Q_KOL = None
D = os.path.join(A.dir, A.izbori); IXF = os.path.join(D, "index.json"); OUT = os.path.join(D, "citanje.json"); LOGF = os.path.join(D, "citanje_log.txt")
UNTIL = datetime.datetime.fromisoformat(A.until) if A.until else None
def log(*a):
    line = datetime.datetime.now().strftime("%d.%m. %H:%M:%S") + " " + " ".join(str(x) for x in a); print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f: f.write(line + "\n")
def api(path, data=None, t=600):
    req = urllib.request.Request("http://127.0.0.1:11434" + path, data=json.dumps(data).encode() if data else None, headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=t).read())
def b64(im):
    b = io.BytesIO(); im.save(b, "PNG"); return base64.b64encode(b.getvalue()).decode()
def ask(im, prompt):
    try:
        r = api("/api/chat", {"model": A.model, "stream": False, "format": "json", "options": {"temperature": 0},
                              "messages": [{"role": "user", "content": prompt, "images": [b64(im)]}]})
        return json.loads(r["message"]["content"])
    except Exception as e:
        return {"_greska": str(e)[:200]}
def toint(v):
    if v is None: return None
    s = str(v).strip()
    if s in ("-", "—", "–", "/", "0"): return 0
    s = re.sub(r"[^\d]", "", s)
    return int(s) if s else None
Q_LEVO = ("Isečak srpskog izbornog zapisnika (obrazac RG-2), rukom popunjen. Pročitaj rukom upisane brojeve: "
          "tačka 1 (broj biračkog mesta), tačka 4 (broj birača upisanih u izvod), 11.1 (broj birača koji su izašli), "
          "11.2 (broj listića u glasačkoj kutiji), 11.3 (nevažeći), 11.4 (važeći). Ako je broj precrtan i pored upisan drugi, važi novi. "
          'Vrati SAMO JSON: {"bm": ..., "upisani": ..., "izasli": ..., "u_kutiji": ..., "nevazeci": ..., "vazeci": ...}. Nečitko ili prazno = null. Crtica = 0.')
def q_tab(a, b):
    return ("Isečak srpskog izbornog zapisnika, tabela 11.5: broj glasova koje je dobila svaka izborna lista. Svaki red ima redni broj liste "
            f"(levo) i rukom upisan broj glasova (desno). Pročitaj redove {a} do {b}. Crtica ili prazno polje = 0. Ako je broj precrtan i pored upisan drugi, važi novi. "
            'Vrati SAMO JSON gde je ključ redni broj liste, a vrednost broj glasova, npr. {"' + str(a) + '": 151, "' + str(a + 1) + '": 0, ...}. Nečitko = null.')
Q_KOL_T = ("Slika ima dve kolone iz tabele srpskog izbornog zapisnika: levo je redni broj izborne liste (1 do {n}), desno je rukom upisan broj glasova za tu listu, u istom redu. "
         "Pročitaj broj glasova za svaki red, redom od 1 do {n}. Crtica, kosa crta ili prazno polje = 0. Ako je broj precrtan i pored upisan drugi, važi novi. "
         'Vrati SAMO JSON: {{"glasovi": [niz od tačno {n} celih brojeva, redom za liste 1 do {n}]}}.')
def render(path, dpi):
    pdf = P.PdfDocument(path); n = len(pdf); ims = [pdf[i].render(scale=dpi / 72).to_pil() for i in range(min(n, 2))]; pdf.close(); return n, ims
def citaj(path, dpi):
    n, ims = render(path, dpi); im = ims[0]; W, H = im.size
    if W < H:  # uspravni sken: strana 1 = levo, strana 2 = tabela (ako postoji)
        levo = im; tab = ims[1] if len(ims) > 1 else im; tw, th = tab.size; tabA = tab.crop((0, 0, tw, int(th * .6))); tabB = tab.crop((0, int(th * .3), tw, th)); orient = "uspravno"
    else:
        levo = im.crop((0, int(H * .12), int(W * .50), int(H * .90)))
        tabA = im.crop((int(W * .50), int(H * .04), W, int(H * .45))); tabB = im.crop((int(W * .50), int(H * .30), W, int(H * .75))); orient = "polozeno"
    L = ask(levo, Q_LEVO)
    z = {k: toint(L.get(k)) for k in ("bm", "upisani", "izasli", "u_kutiji", "nevazeci", "vazeci")}
    lists = None; nacin = "kolona"
    if orient == "polozeno":  # 4.11.: samo kolona rednih brojeva + kolona glasova (bez naziva lista) – model se ne zbunjuje tekstom
        y0, y1 = int(H * .085), int(H * .72)
        a = im.crop((int(W * .505), y0, int(W * .565), y1)); b = im.crop((int(W * .86), y0, int(W * .985), y1))
        from PIL import Image
        c = Image.new("RGB", (a.width + b.width + 40, max(a.height, b.height)), "white"); c.paste(a, (0, 0)); c.paste(b, (a.width + 40, 0))
        T = ask(c, Q_KOL)
        v = T.get("glasovi") if isinstance(T, dict) else None
        if isinstance(v, list) and len(v) == A.liste: lists = {str(i + 1): toint(x) for i, x in enumerate(v)}
    if lists is None:
        nacin = "tabela"; h = (A.liste + 1) // 2
        T = {}; T.update(ask(tabA, q_tab(1, h))); T.update({k: v for k, v in ask(tabB, q_tab(h + 1, A.liste)).items() if k not in T or T[k] is None})
        lists = {str(i): toint(T.get(str(i))) for i in range(1, A.liste + 1)}
    # prazna/nečitka polja: ako sa njima = 0 zbir tačno daje važeće, to su crtice
    if z.get("vazeci") is not None and any(x is None for x in lists.values()) and sum(x or 0 for x in lists.values()) == z["vazeci"]:
        lists = {k: (x or 0) for k, x in lists.items()}
    return dict(strana=n, orijentacija=orient, dpi=dpi, nacin=nacin, **z, liste=lists)
def provera(r):
    v, iv, uk = r.get("vazeci"), r.get("nevazeci"), r.get("u_kutiji")
    L = r["liste"]; poz = []
    if any(x is None for x in L.values()): poz.append("nečitka lista")
    else:
        S = sum(L.values())
        if v is None or S != v: poz.append(f"zbir lista {S} ≠ važeći {v}")
    if None in (v, iv, uk) or uk != v + iv: poz.append(f"u kutiji {uk} ≠ nevažeći {iv} + važeći {v}")
    if r.get("izasli") is not None and r.get("upisani") is not None and r["izasli"] > r["upisani"]: poz.append("izašlo više od upisanih")
    return poz
Q_KOL = Q_KOL_T.format(n=A.liste)
IX = json.load(open(IXF, encoding="utf-8"))
RES = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
def rg2(v):
    t = v.get("tip") or ""
    return v.get("aktivan") and "поновљен" not in t and ("РГ-2" in t or (not t and "_rg2_" in v.get("fajl", "")))
todo = [(l, v) for l, v in IX.items() if rg2(v) and l not in RES]
todo.sort(key=lambda x: (x[1]["opstina"], int(re.sub(r"\D", "", x[1]["n"]) or 0)))
if A.max: todo = todo[:A.max]
log(f"čitanje {A.izbori}: za čitanje {len(todo)}, već pročitano {len(RES)}, model {A.model}")
t0 = time.time(); ok = sus = 0
for i, (l, v) in enumerate(todo):
    if UNTIL and datetime.datetime.now() >= UNTIL: log("isteklo vreme"); break
    p = os.path.join(D, v["fajl"])
    try:
        r = citaj(p, 150); poz = provera(r)
        if poz:
            r2 = citaj(p, 220); poz2 = provera(r2)
            if len(poz2) <= len(poz): r, poz = r2, poz2
    except Exception as e:
        r, poz = dict(greska=str(e)[:200]), ["greška"]
    r.update(opstina=v["opstina"], n=v["n"], sha=v["sha"], fajl=v["fajl"], status="ok" if not poz else "sumnja", problemi=poz,
             at=datetime.datetime.now().strftime("%d.%m. %H:%M"))
    if r.get("bm") is not None and str(r["bm"]) != re.sub(r"\D", "", v["n"]): r["problemi"] = poz + [f"u zapisniku BM {r['bm']}"]
    RES[l] = r; ok += r["status"] == "ok"; sus += r["status"] != "ok"
    if (i + 1) % 10 == 0 or i + 1 == len(todo):
        tmp = OUT + ".tmp"; json.dump(RES, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, OUT)
        el = time.time() - t0; log(f"pročitano {i+1}/{len(todo)} (ok {ok}, sumnja {sus}), {60*(i+1)/el:.1f}/min, još oko {(len(todo)-i-1)*el/(i+1)/60:.0f} min")
tmp = OUT + ".tmp"; json.dump(RES, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, OUT)
log(f"kraj: ok {ok}, sumnja {sus}, ukupno pročitano {len(RES)}")
