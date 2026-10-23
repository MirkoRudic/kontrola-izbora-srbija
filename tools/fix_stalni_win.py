# Laptop: ponovo čita osnovna rešenja stalnog sastava za BM sa nepotpunim sastavom (leva polovina, psm 4, parser po redosledu)
#   python tools/fix_stalni_win.py todo.json izlazni_folder
import sys, os, json, re, subprocess, tempfile, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_odb import parse_stalni
from parse_seq import parse_seq
from concurrent.futures import ThreadPoolExecutor
import threading
TESS = os.environ.get("TESSERACT", "tesseract"); LOCK = threading.Lock()
todo = json.load(open(sys.argv[1], encoding="utf-8")); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
cnt = lambda r: len([x for x in r if x.get("name") and x["name"] != "?"])
def work(j):
    out = os.path.join(OUT, j["id"] + ".json")
    if os.path.exists(out): return
    try:
        import pypdfium2 as P
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "a.pdf"); u = "https://www.rik.parlament.gov.rs" + urllib.parse.quote(j["l"])
            subprocess.run([os.environ.get("CURL", "curl"), "-sS", "--max-time", "90", "-A", "Mozilla/5.0", "-o", f, u], capture_output=True)
            if not os.path.exists(f) or open(f, "rb").read(4) != b"%PDF": raise RuntimeError("preuzimanje")
            with LOCK:
                pdf = P.PdfDocument(f); imgs = [pdf[k].render(scale=300 / 72, grayscale=True).to_pil() for k in range(min(len(pdf), 2))]; pdf.close()
            txt = {}
            for k, im in enumerate(imgs):
                w, h = im.size
                if w > h:
                    p = os.path.join(d, f"{k}L.png"); im.crop((0, 0, w // 2, h)).save(p)
                    txt["levo"] = txt.get("levo", "") + subprocess.run([TESS, p, "-", "-l", "srp+srp_latn", "--psm", "6"], capture_output=True).stdout.decode("utf-8", "replace")
                p = os.path.join(d, f"{k}.png"); im.save(p)
                txt["psm4"] = txt.get("psm4", "") + subprocess.run([TESS, p, "-", "-l", "srp+srp_latn", "--psm", "4"], capture_output=True).stdout.decode("utf-8", "replace")
                txt["psm6"] = txt.get("psm6", "") + subprocess.run([TESS, p, "-", "-l", "srp+srp_latn", "--psm", "6"], capture_output=True).stdout.decode("utf-8", "replace")
        best, src = [], ""
        for name, t in txt.items():
            for pn, r in (("", parse_stalni(t)), ("+red", parse_seq(t))):
                if cnt(r) > cnt(best): best, src = r, name + pn
        alltxt = "\n".join(txt.values())
        bm = re.findall(r"(?:БРОЈ|БРОJ|број|броj)\s*:?\s*(\d{1,3})\s*\.?\s*(?:У|у|Y)\s", alltxt)
        json.dump(dict(s=best, src=src, n=cnt(best), bm=bm[:3]), open(out, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e:
        json.dump(dict(err=str(e)[:200]), open(out, "w", encoding="utf-8"))
with ThreadPoolExecutor(int(os.environ.get("THREADS", "16"))) as ex: list(ex.map(work, todo))
print("gotovo", len(todo))
