# Dnevnik rada svih poslova -> grana 'uzivo', folder logovi/ (Claude ga čita preko GitHub API-ja; ne pravi Cloudflare objavu na main).
#   iz koda:   from dnevnik import push_logs; push_logs({"posao": ["red", ...]})
#   iz ljuske: python3 tools/dnevnik.py posao < fajl     (dodaje redove iz fajla)
# logovi/<posao>.log čuva poslednjih 4000 redova; logovi/stanje.json ima vreme poslednjeg javljanja svakog posla.
import os, sys, json, subprocess, tempfile, datetime, socket
try:
    from zoneinfo import ZoneInfo; TZ = ZoneInfo("Europe/Belgrade")
except Exception: TZ = None
MAXL = 4000
def host():
    if os.environ.get("GITHUB_ACTIONS"): return "github"
    return "laptop" if os.name == "nt" else (socket.gethostname()[:20] or "racunar")
def now(): return datetime.datetime.now(TZ).strftime("%d.%m. %H:%M:%S")
def _git(env, *a, inp=None):
    return subprocess.run(["git", *a], capture_output=True, text=True, env=env, input=inp, encoding="utf-8", errors="replace")
def build_commit(changes, msg, extra_tree=None):
    """changes: {putanja_u_repou: callable(stari_tekst)->novi_tekst}; extra_tree: callable(env) koji dodaje još fajlova u indeks.
    Vraća (env, commit, base) ili None."""
    env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tempfile.gettempdir(), f"uzivo-{os.getpid()}.idx"))
    base = None
    if _git(env, "fetch", "-q", "origin", "uzivo").returncode == 0:
        base = _git(env, "rev-parse", "FETCH_HEAD").stdout.strip()
        _git(env, "read-tree", base)
    else:
        _git(env, "read-tree", "--empty")
    if extra_tree: extra_tree(env)
    for path, fn in changes.items():
        old = _git(env, "show", f"{base}:{path}").stdout if base else ""
        new = fn(old)
        h = _git(env, "hash-object", "-w", "--stdin", inp=new).stdout.strip()
        _git(env, "update-index", "--add", "--cacheinfo", f"100644,{h},{path}")
    tree = _git(env, "write-tree").stdout.strip()
    c = _git(env, "commit-tree", tree, *(["-p", base] if base else []), "-m", msg).stdout.strip()
    return env, c, base
def log_changes(entries):
    h = host(); t = now(); ch = {}
    for job, lines in entries.items():
        if not lines: continue
        add = "".join(f"{t} [{h}] {l.rstrip()}\n" if not l.startswith(t[:6]) else f"{l.rstrip()}\n" for l in lines)
        ch[f"logovi/{job}.log"] = (lambda add: lambda old: "".join((old + add).splitlines(True)[-MAXL:]))(add)
    def st(old):
        try: d = json.loads(old or "{}")
        except Exception: d = {}
        for job in entries: d[job] = {"vreme": t, "gde": h, "poslednje": (entries[job] or [""])[-1][-200:]}
        return json.dumps(d, ensure_ascii=False, indent=1)
    if ch: ch["logovi/stanje.json"] = st
    return ch
def push(changes, msg, extra_tree=None, tries=4):
    for a in range(tries):
        r = build_commit(changes, msg, extra_tree)
        if not r: return False
        env, c, base = r
        p = _git(env, "push", "-q", "origin", f"{c}:refs/heads/uzivo")
        if p.returncode == 0: return True
        if "non-fast-forward" not in p.stderr and "fetch first" not in p.stderr and "rejected" not in p.stderr:
            sys.stderr.write("dnevnik push: " + p.stderr[-300:] + "\n")
    return False
def push_logs(entries, msg=None):
    try: return push(log_changes(entries), msg or ("Dnevnik: " + ", ".join(entries)))
    except Exception as e:
        sys.stderr.write(f"dnevnik greška: {e}\n"); return False
if __name__ == "__main__":
    job = sys.argv[1]; lines = sys.stdin.read().splitlines()
    print("dnevnik", job, len(lines), "redova:", "ok" if push_logs({job: lines}) else "NIJE UPISANO")

_LOCKS = []
def jedini(ime):
    """Samo jedan primerak posla na ovom računaru (zaključan fajl). Vraća False ako već radi drugi."""
    import tempfile
    d = os.environ.get("KONTROLA_LOCKDIR") or tempfile.gettempdir()
    f = open(os.path.join(d, f"kontrola_{ime}.lock"), "a+")
    try:
        if os.name == "nt":
            import msvcrt; f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl; fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close(); return False
    _LOCKS.append(f); return True
