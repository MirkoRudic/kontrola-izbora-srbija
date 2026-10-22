# Čita nova rešenja o odborima (OCR) i iz njih vadi promene sastava: "umesto X za ULOGU imenuje Y, na predlog Z", "briše X",
# kao i nova osnovna rešenja (imenovanje u stalnom/proširenom sastavu). Rezultat: public/data/odbori_izm.json
#   {uid: {n: [{l, ts, at, k:'S'|'P', ch:[{op:'zam'|'brisi'|'novo', role, old, new, key, by}] | base:{s|p}}]}}
# Pokreće se posle tools/odbori_novi.py (GitHub Actions). Potrebno: tesseract (srp, srp_latn), pypdfium2.
import json, os, re, sys, subprocess, tempfile, hashlib, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translit import lat
from parse_odb import parse_stalni, parse_prosireni, gkey, lkey, nice
D = "public/data"
NOVI = json.load(open(f"{D}/odbori_novi.json")) if os.path.exists(f"{D}/odbori_novi.json") else {}
OUT = os.environ.get("IZM_OUT", f"{D}/odbori_izm.json")
IZ = json.load(open(OUT)) if os.path.exists(OUT) else {}
if os.environ.get("IZM_RETRY_EMPTY"):  # ponovo pročitaj rešenja iz kojih ništa nije izvučeno
    for u in IZ.values():
        for n in list(u): u[n] = [r for r in u[n] if r.get("ch") or r.get("base")]
done = {e["l"] for u in IZ.values() for l in u.values() for e in l}
for _f in (f"{D}/odbori_izm.json", f"{D}/odbori_izm_laptop.json"):  # ne čitaj ponovo ono što je pročitao drugi računar
    if os.path.exists(_f) and os.path.abspath(_f) != os.path.abspath(OUT):
        done |= {e["l"] for u in json.load(open(_f)).values() for l in u.values() for e in l if not os.environ.get("IZM_RETRY_EMPTY") or e.get("ch") or e.get("base")}
def kind(t):
    t = t.lower()
    return "S" if "stalnom" in t else "P" if "prošir" in t else None
FAILS = []
import time
TESS = os.environ.get("TESSERACT", "tesseract")
import threading
LOCK = threading.Lock()
def ocr(url):
    import pypdfium2 as P
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "a.pdf")
        u = urllib.parse.quote(url, safe=":/")
        for a in range(4):
            r = subprocess.run([os.environ.get("CURL", "curl"), "-sS", "--http1.1", "--max-time", "90", "-A",
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                                "-w", "%{http_code}", "-o", f, u], capture_output=True, text=True)
            if r.returncode == 0 and os.path.getsize(f) > 1000 and open(f, "rb").read(4) == b"%PDF": break
            time.sleep(2 + a * 3)
        else:
            FAILS.append(f"{r.returncode} http={r.stdout.strip()} {r.stderr.strip()[:120]} prvo={open(f,'rb').read(60) if os.path.exists(f) else b''}")
            if len(FAILS) <= 3: print("preuzimanje nije uspelo:", FAILS[-1], flush=True)
            return None
        txt = ""
        with LOCK:  # pdfium nije bezbedan za više niti
            pdf = P.PdfDocument(f); pngs = []
            for k in range(min(len(pdf), 3)):
                png = os.path.join(d, f"{k}.png"); pdf[k].render(scale=200 / 72, grayscale=True).to_pil().save(png); pngs.append(png)
            pdf.close()
        for png in pngs:
            txt += subprocess.run([TESS, png, "-", "-l", "srp+srp_latn", "--psm", "6"], capture_output=True).stdout.decode("utf-8", "replace") + "\n"
        return txt
ROLEW = [(r"заменик\w*\s+председник\w*", "zamenik predsednika"), (r"председник\w*", "predsednik"), (r"заменик\w*\s+члан\w*\s*(\d)", "zamenik {}. člana"), (r"члан\w*\s*(\d)", "{}. član"), (r"заменика\s+члана\s*(\d)", "zamenik {}. člana"), (r"члана\s*(\d)", "{}. član"), (r"заменика\s+(\d)\s*[.,]?\s*члана", "zamenik {}. člana"),
         (r"(\d)\s*[.,]?\s*члана", "{}. član"), (r"заменик\w*\s+члан\w*", "zamenik člana"), (r"заменик\w*", "zamenik člana"), (r"члан\w*", "član")]
def role_of(s):
    for rx, r in ROLEW:
        m = re.match(r"\s*" + rx, s, re.I)
        if m: return r.format(*m.groups()) if "{}" in r else r
    return None
def changes(t):
    t = re.split(r"\n\s*[|]?\s*2\s*[.,)]\s*Ово решење|\nОбразложење", t)[0]
    m0 = re.search(r"тако\s+што\s+се", t); t = t[m0.end():] if m0 else t
    t = re.sub(r"[|]", " ", t); t = re.sub(r"\((?:име и презиме|функција[^)]*|назив предлагача[^)]*)\)", " ", t); t = re.sub(r"_+", " ", t)
    T = re.sub(r"\s+", " ", t); T = re.sub(r"на\s+пред?лог\s*:", "на предлог ", T, flags=re.I)
    out = []
    # „уместо X за ULOGU именује Y, на предлог Z (од …)“ – u bilo kom obliku (sa ili bez rednih brojeva, dvotačaka, zareza)
    RW = r"(?:за|као)\s+|(?:\d\s*[.,]?\s*)?(?:заменик\w*\s+)?(?:председник|члан)\w*|заменик\w*\s"
    for m in re.finditer(r"уместо\s*:?\s*(.+?)\s+именуј\w*\s*(?:се)?\s*[:;]?\s*(.+?)\s*,?\s+на\s+пред?лог\s+(.+?)(?=\s+од\s+\d|\s+\d{1,2}\s*[.)]\s|\s+уместо|\.\s|;|$)", T, re.I):
        M = m.group(1); k = re.search(r"\s*,?\s+(?=" + RW + ")", M, re.I)
        o, rl = (M[:k.start()], re.sub(r"^(?:за|као)\s+", "", M[k.end():], flags=re.I)) if k else (M, "")
        nw = re.sub(r"\s*,?\s+(?:заменик\w*\s+)?(?:председник|члан)\w*(?:\s*\d)?\s*$", "", m.group(2), flags=re.I)
        out.append(dict(op="zam", old=nice(o), role=role_of(rl), new=nice(nw), by=lat(m.group(3))[:140]))
    for m in re.finditer(r"брише\s+(?:се\s+)?(.+?)\s*,?\s+за\s+(\S+(?:\s+\S+)?)", T, re.I):
        by = re.search(r"на\s+пред?лог\s+(.+?)(?=\s+од\s+\d|$)", T[m.end():m.end()+200], re.I)
        out.append(dict(op="brisi", old=nice(m.group(1)), role=role_of(m.group(2)), by=lat(by.group(1))[:140] if by else ""))
    # „утврђује се да X по сили закона престаје функција ULOGE“
    for m in re.finditer(r"утврђује\s+се\s*,?\s*да\s+(.+?)\s+(?:из\s+\S+\s+)?(?:по\s+сили\s+закона\s+)?престаје\s+функција\s+(.{0,40})", T, re.I):
        out.append(dict(op="brisi", old=nice(m.group(1)), role=role_of(m.group(2)), by=""))
    if not out:  # „у бирачки одбор: 1) именује X, на предлог Z“ (bez uloge)
        for m in re.finditer(r"(?:одбор\s*:?\s*\d?\s*\)?|\d\s*\))\s*именуј\w*\s*(?:се)?\s*[:;]?\s*(.+?)\s*,?\s+на\s+предлог\s+(.+?)(?=\s+од\s+\d|,\s+који|\s+\d{1,2}\s*[.)]\s|\.\s|$)", T, re.I):
            out.append(dict(op="novo", role=None, new=nice(m.group(1)), by=lat(m.group(2))[:140]))
    if not out:
        for m in re.finditer(r"за\s+(\S+(?:\s+\S+){0,3}?)\s+именуј\w*\s*(?:се)?\s*[:;]?\s*(.+?)\s*,?\s+на\s+пред?лог\s+(.+?)(?=\s+од\s+\d|\s+\d{1,2}\s*[.)]\s|\.\s|$)", T, re.I):
            out.append(dict(op="novo", role=role_of(m.group(1)), new=nice(m.group(2)), by=lat(m.group(3))[:140]))
    # исправка: „речи: „X“ замењују речима: „Y““ ili „име … X … исправити на Y“
    for m in re.finditer(r"реч\w*\s*:?\s*[„\"“]\s*(.+?)\s*[“\"”]\s*замењуј\w*\s+реч\w*\s*:?\s*[„\"“]\s*(.+?)\s*[“\"”]", T, re.I):
        out.append(dict(op="zam", old=nice(m.group(1)), role=None, new=nice(m.group(2)), by=""))
    if not out:
        m = re.search(r"(?:име|презиме)\w*\s+(.{0,60}?)\s*,?\s+има\s+исправити\s+на\s+([A-ZА-ЯЂЈЉЊЋЏČĆŠŽĐ][\wА-Яа-яЂђЈјЉљЊњЋћЏџ\-]+)", T)
        if m:
            w = re.findall(r"[A-ZА-ЯЂЈЉЊЋЏ][A-ZА-ЯЂЈЉЊЋЏ\-]{2,}", m.group(1))
            if w: out.append(dict(op="ime", old=nice(w[-1]), new=nice(m.group(2)), role=None, by=""))
    for c in out:
        for f in ("old", "new"):
            if c.get(f): c[f] = re.sub(r"\s+(?:Iz|Из)\s+.*$", "", re.sub(r"^(?:Se|Се)\s+", "", c[f])).strip() or None
        c["key"] = (lkey(c["by"]) if c["role"] in ("član", "zamenik člana") else gkey(c["by"])) if c["by"] else None
    return out
# izvori: nova rešenja (odbori_novi.json) + starija rešenja o izmenama iz podataka opština (--stara)
SRC = []
for uid, x in NOVI.items():
    for n, docs in x.items():
        if n != "0": SRC += [(uid, n, e) for e in docs]
if "--stara" in sys.argv:
    import glob
    for f in glob.glob(f"{D}/u/*.json"):
        uid = os.path.basename(f)[:-5]
        for st in json.load(open(f))["stations"]:
            SRC += [(uid, str(st["n"]), d) for d in st.get("odb", []) if re.search(r"izmen|ispravk|dopun|razreš|prestan", d["t"].lower())]
todo = []
for uid, n, e in SRC:
    if e["l"] in done: continue
    t = e["t"].lower(); k = kind(t)
    if not k or not re.search(r"imenovan|izmen|ispravk|dopun|razreš|prestan", t): continue
    done.add(e["l"]); todo.append((uid, n, e, k, t))
todo.sort(key=lambda j: 0 if re.search(r"izmen|ispravk|dopun|razreš|prestan", j[4]) else 1)  # prvo izmene
if os.environ.get("IZM_REVERSE"): todo.reverse()  # drugi računar kreće od kraja spiska
print("za čitanje:", len(todo), flush=True)
def work(j):
    uid, n, e, k, t = j
    try: txt = ocr(e["l"])
    except Exception as ex:
        FAILS.append("izuzetak: " + repr(ex)[:200])
        if len(FAILS) <= 3: print("greška čitanja:", FAILS[-1], flush=True)
        txt = None
    if txt is None: return None
    rec = dict(l=e["l"], ts=e.get("ts"), at=e.get("at"), k=k)
    if re.search(r"izmen|ispravk|dopun|razreš|prestan", t): rec["ch"] = changes(txt)
    if not rec.get("ch"):
        # drugačiji oblik rešenja: pročitaj ga kao osnovno (prošireni: liste se dopisuju; stalni: postavlja samo pročitane uloge)
        rec.pop("ch", None)
        if k == "P":
            pp = [r for r in parse_prosireni(txt) if r.get("member") or r.get("deputy")]
            if pp: rec["base"] = {"p": pp}
        else:
            ss = [x for x in parse_stalni(txt) if x.get("name")]
            if len(ss) >= 4: rec["base"] = {"s": ss}
            elif ss: rec["ch"] = [dict(op="novo", role=x["role"], new=x["name"], by=x.get("by"), key=x.get("key")) for x in ss]
        if not rec.get("base") and not rec.get("ch"): rec["ch"] = []
    return uid, n, rec
from concurrent.futures import ThreadPoolExecutor
n_new = 0
with ThreadPoolExecutor(int(os.environ.get("THREADS", "4"))) as ex:
    for r in ex.map(work, todo):
        if not r: continue
        uid, n, rec = r; IZ.setdefault(uid, {}).setdefault(n, []).append(rec); n_new += 1
        if n_new % 25 == 0:
            json.dump(IZ, open(OUT, "w"), ensure_ascii=False, separators=(",", ":")); print(n_new, flush=True)
for u in IZ.values():
    for l in u.values(): l.sort(key=lambda r: r.get("ts") or 0)
json.dump(IZ, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print("pročitano novih rešenja:", n_new, "| neuspelih preuzimanja:", len(FAILS))
