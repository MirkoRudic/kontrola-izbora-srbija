# Laptop: na 15 min čita nova rešenja o odborima (GitHub ih samo pronalazi – RIK mu ne da PDF-ove) i objavljuje odbori_izm_laptop.json na main.
#   python tools\laptop_izmene.py [--until 2026-10-25T19:00]
import os, sys, time, subprocess, datetime, argparse
ap = argparse.ArgumentParser(); ap.add_argument("--until", default="2026-10-25T19:00"); A = ap.parse_args()
UNTIL = datetime.datetime.fromisoformat(A.until)
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
F = "public/data/odbori_izm_laptop.json"
for k, v in (("TESSERACT", r"C:\Program Files\Tesseract-OCR\tesseract.exe"), ("TESSDATA_PREFIX", r"D:\VAJB\kontrolaizbora\podaci\ocr\tessdata")):
    if os.path.exists(v) and not os.environ.get(k): os.environ[k] = v
def g(*a): return subprocess.run(["git"] + list(a), cwd=REPO, capture_output=True, text=True)
def log(m): print(datetime.datetime.now().strftime("%d.%m. %H:%M:%S"), m, flush=True)
while datetime.datetime.now() < UNTIL:
    g("checkout", "-q", "--", "public/data/live"); g("clean", "-fdq", "public/data/live")
    r = g("pull", "-q", "--rebase", "--autostash", "origin", "main")
    if r.returncode: log("git pull nije uspeo: " + (r.stderr or r.stdout)[-300:])
    env = dict(os.environ, IZM_OUT=F, CURL="curl.exe" if os.name == "nt" else "curl", THREADS=os.environ.get("THREADS", "12"), OMP_THREAD_LIMIT="1", PYTHONUTF8="1")
    p = subprocess.run([sys.executable, "-u", "tools/odbori_izmene.py"], cwd=REPO, env=env, capture_output=True, text=True)
    log((p.stdout or "").strip().splitlines()[-1] if p.stdout.strip() else "odbori_izmene bez izlaza " + p.stderr[-200:])
    if g("diff", "--quiet", "--", F).returncode:
        g("add", F); g("commit", "-qm", "Izmene odbora: nova rešenja pročitana na laptopu")
        for i in range(3):
            if g("push", "-q").returncode == 0: log("objavljeno"); break
            g("pull", "-q", "--rebase", "-X", "ours", "origin", "main")
    time.sleep(900)
log("kraj")
