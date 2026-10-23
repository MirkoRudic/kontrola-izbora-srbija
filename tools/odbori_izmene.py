# Čita nova rešenja o odborima (OCR) i iz njih vadi promene sastava: "umesto X za ULOGU imenuje Y, na predlog Z", "briše X",
# kao i nova osnovna rešenja (imenovanje u stalnom/proširenom sastavu). Rezultat: public/data/odbori_izm.json
#   {uid: {n: [{l, ts, at, k:'S'|'P', ch:[{op:'zam'|'brisi'|'novo', role, old, new, key, by}] | base:{s|p}}]}}
# Pokreće se posle tools/odbori_novi.py (GitHub Actions). Potrebno: tesseract (srp, srp_latn), pypdfium2.
import json, os, re, sys, subprocess, tempfile, hashlib, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translit import lat
from parse_odb import parse_stalni, parse_prosireni, gkey, lkey, nice
from imena import ocisti
D = "public/data"
NOVI = json.load(open(f"{D}/odbori_novi.json")) if os.path.exists(f"{D}/odbori_novi.json") else {}
OUT = os.environ.get("IZM_OUT", f"{D}/odbori_izm.json")
IZ = json.load(open(OUT)) if os.path.exists(OUT) else {}
if os.environ.get("IZM_RETRY_EMPTY"):  # ponovo pročitaj rešenja iz kojih ništa nije izvučeno
    for u in IZ.values():
        for n in list(u): u[n] = [r for r in u[n] if (r.get("ch") or r.get("base")) and not (os.environ.get("IZM_RETRY_BAD") and any(c.get("op") in ("zam", "novo") and not c.get("new") for c in r.get("ch") or []))]
done = {e["l"] for u in IZ.values() for l in u.values() for e in l}
for _f in (f"{D}/odbori_izm.json", f"{D}/odbori_izm_laptop.json"):  # ne čitaj ponovo ono što je pročitao drugi računar
    if os.path.exists(_f) and os.path.abspath(_f) != os.path.abspath(OUT):
        done |= {e["l"] for u in json.load(open(_f)).values() for l in u.values() for e in l if not os.environ.get("IZM_RETRY_EMPTY") or ((e.get("ch") or e.get("base")) and not (os.environ.get("IZM_RETRY_BAD") and any(c.get("op") in ("zam", "novo") and not c.get("new") for c in e.get("ch") or [])))}
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
        sc = lambda x: len(re.findall(r"решењ|бирачк|одбор|именуј|rešenj|biračk|odbor", x, re.I))
        for png in pngs:
            t1 = subprocess.run([TESS, png, "-", "-l", "srp+srp_latn", "--psm", "6"], capture_output=True).stdout.decode("utf-8", "replace")
            if sc(t1) < 2:  # skenirano naopako ili postrance
                from PIL import Image
                for ang in (180, 90, 270):
                    Image.open(png).rotate(ang, expand=True).save(png + ".r.png")
                    t2 = subprocess.run([TESS, png + ".r.png", "-", "-l", "srp+srp_latn", "--psm", "6"], capture_output=True).stdout.decode("utf-8", "replace")
                    if sc(t2) > sc(t1): t1 = t2
                    if sc(t1) >= 4: break
            txt += t1 + "\n"
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
    T = re.sub(r"\s+", " ", t)
    # OCR šum: „па/Ha предлог”, „преллог”, „имспује”, „каоЧлан 2”, „Члан 2на предлог”
    T = re.sub(r"\b(?:пред[лџп]ог|прелл?ог|првлпог|предлот|npm\w+|Ipc\S*)\b", "предлог", T)
    T = re.sub(r"(?<![\wА-Яа-я])(?:Ha|ha|na|Na|па|ка|не|Нa|на)\s*:?\s+(?=предлог)", "на ", T)
    T = re.sub(r"(?<![\wА-Яа-я])(?:на|Ha|па)\s+(?=(?:посланичк|начелник|подносиоц|подносиоца)\w*)", "на предлог ", T, flags=re.I)
    T = re.sub(r"(?<![\wА-Яа-я])[ИиЛл][Мм][А-Яа-яA-Za-z]{1,2}[УуYy]ј[ЕеУуОоАа](?![\wА-Яа-я])", "именује", T)
    T = re.sub(r"(?<![\wА-Яа-я])[Ии]м\s+нуј\w*", "именује", T)
    T = re.sub(r"(?<![\wА-Яа-я])с[еоев]\s+(?=именује)", "се ", T)
    T = re.sub(r"као(?=[А-ЯA-Zа-я])", "као ", T); T = re.sub(r"([\dа-яА-Я])(на\s+предлог)", r"\1 \2", T)
    T = re.sub(r"на\s+пред?лог\s*:", "на предлог ", T, flags=re.I)
    T = re.sub(r"(?<!на )(?<![\wА-Яа-я])предлог(?![\wА-Яа-я])", "на предлог", T)
    out = []
    # „уместо X за ULOGU именује Y, на предлог Z (од …)“ – u bilo kom obliku (sa ili bez rednih brojeva, dvotačaka, zareza)
    RW = r"(?:за|као)\s+|(?:\d\s*[.,]?\s*)?(?:заменик\w*\s+)?(?:председник|члан)\w*|заменик\w*\s"
    for m in re.finditer(r"уместо\s*:?\s*(.+?)\s+именуј\w*\s*(?:се)?\s*[:;]?\s*(.+?)\s*,?\s+на\s+пред?лог\s+(.+?)(?=\s+од\s+\d|\s+\d{1,2}\s*[.)]\s|\s+уместо|\.\s|;|$)", T, re.I):
        M = m.group(1); r0 = ""
        m0 = re.match(r"((?:заменик\w*\s+)?(?:председник|члан)\w*(?:\s*\d\s*\.?)?)\s+(?!(?:за|као)\s)(.+)", M, re.I)
        if m0: r0, M = m0.group(1), m0.group(2)
        k = re.search(r"\s*,?\s+(?=" + RW + ")", M, re.I)
        o, rl = (M[:k.start()], re.sub(r"^(?:за|као)\s+", "", M[k.end():], flags=re.I)) if k else (M, "")
        nw = re.split(r"\s+(?:\S{1,3}\s+)?предлог\b", m.group(2), flags=re.I)[0]
        nw = re.sub(r"\s*,?\s+(?:заменик\w*\s+)?(?:председник|члан)\w*(?:\s*\d)?\s*$", "", nw, flags=re.I)
        o = re.sub(r"^.*\bуместо\s*", "", o, flags=re.I)
        m2 = re.match(r"((?:заменик\w*\s+)?(?:председник|члан)\w*(?:\s*\d\s*\.?)?)\s+(.+)", o, re.I)
        if m2: o, rl = m2.group(2), (rl or m2.group(1))
        rl = rl or r0
        rl = re.sub(r"^нов\w*\s+", "", rl, flags=re.I)
        out.append(dict(op="zam", old=nice(o), role=role_of(rl), new=nice(nw), by=lat(m.group(3))[:140]))
    if not out:  # „уместо X из Y именује Z из W.” (bez uloge i predlagača)
        for m in re.finditer(r"уместо\s*:?\s*(.+?)\s+(?:се\s+)?именује\s*(?:се)?\s*:?\s*(.+?)(?=\.\s|;|$)", T, re.I):
            M = m.group(1); k = re.search(r"\s*,?\s+(?=(?:за|као)\s+)", M, re.I)
            o, rl = (M[:k.start()], re.sub(r"^(?:за|као)\s+", "", M[k.end():], flags=re.I)) if k else (M, "")
            out.append(dict(op="zam", old=nice(o), role=role_of(rl), new=nice(re.split(r",", m.group(2))[0]), by=""))
    # „БРИШЕ СЕ X из Y, члан бирачког одбора …, кога је предложила Z”
    for m in re.finditer(r"брише\s+се\s+(.+?)\s*,\s*((?:заменик\w*\s+)?(?:председник|члан)\w*(?:\s*\d)?)[^;]*?(?:кога|коју|које)\s+је\s+предложил\w*\s+(.+?)(?=;|\.\s|$)", T, re.I):
        out.append(dict(op="brisi", old=nice(m.group(1)), role=role_of(m.group(2)), by=lat(m.group(3))[:140]))
    if any(c["op"] == "brisi" for c in out): pass
    else:
     for m in re.finditer(r"брише\s+(?:се\s+)?(.+?)\s*,?\s+за\s+(\S+(?:\s+\S+)?)", T, re.I):
        by = re.search(r"на\s+пред?лог\s+(.+?)(?=\s+од\s+\d|$)", T[m.end():m.end()+200], re.I)
        out.append(dict(op="brisi", old=nice(m.group(1)), role=role_of(m.group(2)), by=lat(by.group(1))[:140] if by else ""))
    # ispravka predlagača: „ULOGA X из Y, именује на предлог Z уместо на предлог W”
    for m in re.finditer(r"одбор\s*,\s*((?:заменик\w*\s+)?(?:председник|члан)\w*(?:\s*\d\s*\.?)?)\s+(.+?)(?:\s+из\s+[^,]+)?\s*,\s*именује\s+на\s+предлог\s+(.+?)\s+уместо\s+на\s+предлог", T, re.I):
        out.append(dict(op="zam", old=nice(m.group(2)), role=role_of(m.group(1)), new=nice(m.group(2)), by=lat(re.sub(r"\s+од\s+\d.*$", "", m.group(3)))[:140]))
    # „утврђује се да X по сили закона престаје функција ULOGE“
    for m in re.finditer(r"утврђује\s+се\s*,?\s*да\s+(.+?)\s+(?:из\s+\S+\s+)?(?:по\s+\S+\s+закона\s+)?престаје\s+фу\w*ција\s+(.{0,40})", T, re.I):
        out.append(dict(op="brisi", old=nice(m.group(1)), role=role_of(m.group(2)), by=""))
    if not out:  # „у бирачки одбор: 1) именује X, на предлог Z“ (bez uloge)
        for m in re.finditer(r"(?:одбор\s*:?\s*\d?\s*\)?|\d\s*\))\s*именуј\w*\s*(?:се)?\s*[:;]?\s*(.+?)\s*,?\s+на\s+предлог\s+(.+?)(?=\s+од\s+\d|,\s+који|\s+\d{1,2}\s*[.)]\s|\.\s|$)", T, re.I):
            out.append(dict(op="novo", role=None, new=nice(m.group(1)), by=lat(m.group(2))[:140]))
    if not out:
        for m in re.finditer(r"за\s+(\S+(?:\s+\S+){0,3}?)\s+именуј\w*\s*(?:се)?\s*[:;]?\s*(.+?)\s*,?\s+на\s+пред?лог\s+(.+?)(?=\s+од\s+\d|\s+\d{1,2}\s*[.)]\s|\.\s|$)", T, re.I):
            out.append(dict(op="novo", role=role_of(m.group(1)), new=nice(m.group(2)), by=lat(m.group(3))[:140]))
    # исправка: „речи: „X“ замењују речима: „Y““ ili „име … X … исправити на Y“
    Q1, Q2 = "[«„\"“]", "[»“\"”„,]"
    for m in re.finditer(r"наведено\s+(?:име|презиме)\s+.{0,40}?" + Q1 + r"?\s*(?:г\.\s*)?([^«»„“”\"]{2,40}?)\s*" + Q2 + r"\s*исправља\s+и\s+гласи\s*" + Q1 + r"\s*([^«»„“”\"]{2,40}?)\s*(?:" + Q2 + r"|У\.)", T, re.I):
        out.append(dict(op="ime", old=nice(m.group(1)), new=nice(m.group(2)), role=None, by=""))
    for m in re.finditer(r"уместо\s+(?:имена|презимена|ознаке)?\s*" + Q1 + r"([^«»„“”\"]{0,40}?)\s*[»“\"”]\s*,?\s*уписује\s*(?:се)?\s*:?\s*" + Q1 + r"\s*([^«»„“”\"]{2,60}?)\s*[»“\"”]", T, re.I):
        o, n = m.group(1).strip(" /-"), m.group(2)
        if not o: out.append(dict(op="novo", role=None, new=nice(n), by=""))
        elif " " not in o.strip() and " " not in n.strip(): out.append(dict(op="ime", old=nice(o), new=nice(n), role=None, by=""))
        else: out.append(dict(op="zam", old=nice(o), new=nice(n), role=None, by=""))
    for m in re.finditer(r"као\s+(?:име|презиме)\s+.{0,60}?\s+уместо\s+(\S+)\s+наведено\s+([^\s.,]+)", T, re.I):
        out.append(dict(op="ime", old=nice(m.group(2)), new=nice(m.group(1)), role=None, by=""))
    for m in re.finditer(r"уместо\s*:?\s*" + Q1 + r"\s*(?:([^:«»„“”\"]{3,30}):\s*)?([^«»„“”\"]+?)\s*" + Q2 + r"\s*,?\s*треба\s+да\s+стоји\s*" + Q1 + r"\s*(?:[^:«»„“”\"]{3,30}:\s*)?([^«»„“”\"]+?)\s*" + Q2, T, re.I):
        out.append(dict(op="zam", old=nice(m.group(2)), new=nice(m.group(3)), role=role_of(m.group(1) or ""), by=""))
    for m in re.finditer(r"реч\w*\s*[:;]?\s*[„\"“]\s*(.+?)\s*[“\"”]\s*,?\s*(?:за)?мењ\w*\s+реч\w*\s*:?\s*[„\"“]\s*(.+?)\s*[“\"”]", T, re.I):
        out.append(dict(op="zam", old=nice(m.group(1)), role=None, new=nice(m.group(2)), by=""))
    if not out:
        m = re.search(r"(?:име|презиме)\w*\s+(.{0,60}?)\s*,?\s+има\s+исправити\s+на\s+([A-ZА-ЯЂЈЉЊЋЏČĆŠŽĐ][\wА-Яа-яЂђЈјЉљЊњЋћЏџ\-]+)", T)
        if m:
            w = re.findall(r"[A-ZА-ЯЂЈЉЊЋЏ][A-ZА-ЯЂЈЉЊЋЏ\-]{2,}", m.group(1))
            if w: out.append(dict(op="ime", old=nice(w[-1]), new=nice(m.group(2)), role=None, by=""))
    for c in out:
        for f in ("old", "new"):
            if c.get(f): c[f] = re.sub(r"\s+(?:Iz|Из|Sa|Са)\s+.*$", "", re.sub(r"^(?:Se|Се)\s+", "", c[f])).strip() or None
        if c.get("new"):
            v = ocisti(c["new"]); c["new"] = None if v in (None, "?") else v
        if c.get("old"):
            v = ocisti(c["old"]); c["old"] = v if v not in (None, "?") else c["old"]
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
