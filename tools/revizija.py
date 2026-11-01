# Revizioni dnevnik: šta je kad pročitano i preuzeto sa RIK-a (dodato 1.11.2026).
#   from revizija import zapisi, posalji
#   zapisi("laptop_zapisnici", "preuzet", opstina=..., bm=..., sha256=...)   -> u memoriju (i u lokalni fajl, ako je LOCAL zadat)
#   posalji()                                                               -> na granu 'revizija' (najviše na 5 min; posalji(True) odmah)
# Pravila:
#  * samo se dodaje: postojeći redovi se nikad ne menjaju niti brišu (fajl revizija/<gde>/<posao>/<datum>.jsonl);
#  * lanac heševa: svaki red nosi "prev" (heš prethodnog reda) i "h" = sha256 kanonskog JSON-a reda bez "h",
#    pa se svaka naknadna izmena ili brisanje reda vidi (python tools/revizija.py --proveri <fajl>);
#  * grana 'revizija' na GitHub-u je zaštićena pravilom (ruleset): ne može se obrisati ni prepisati (force push).
import os, sys, json, hashlib, datetime, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dnevnik as DN
GRANA = "revizija"
LOCAL = os.environ.get("KONTROLA_REVIZIJA")  # lokalni folder (laptop); svaki zapis se odmah dopisuje i tamo
_BUF = []; _LAST = [0.0]
def _t(): return datetime.datetime.now(DN.TZ).isoformat(timespec="seconds")
def _kanon(e): return json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
def zapisi(posao, tip, **polja):
    e = {"t": _t(), "gde": DN.host(), "posao": posao, "tip": tip, **polja}
    _BUF.append(e)
    if LOCAL:
        try:
            os.makedirs(LOCAL, exist_ok=True)
            with open(os.path.join(LOCAL, f"{e['gde']}-{posao}-{e['t'][:10]}.jsonl"), "a", encoding="utf-8") as f: f.write(_kanon(e) + "\n")
        except Exception as x: sys.stderr.write(f"revizija lokalno: {x}\n")
    return e
def _dodaj(old, events):
    lines = [l for l in old.splitlines() if l.strip()]
    prev = json.loads(lines[-1])["h"] if lines else "0" * 64
    out = []
    for e in events:
        e = {k: v for k, v in e.items() if k not in ("h", "prev")}; e["prev"] = prev
        e["h"] = prev = hashlib.sha256(_kanon(e).encode("utf-8")).hexdigest()
        out.append(_kanon(e))
    return "".join(l + "\n" for l in lines + out)
def posalji(force=False, razmak=300):
    if not _BUF or (not force and time.time() - _LAST[0] < razmak): return True
    ev = _BUF[:]; by = {}
    for e in ev: by.setdefault(f"revizija/{e['gde']}/{e['posao']}/{e['t'][:10]}.jsonl", []).append(e)
    ch = {p: (lambda L: lambda old: _dodaj(old, L))(L) for p, L in by.items()}
    ok = False
    try: ok = DN.push(ch, f"Revizija: {len(ev)} zapisa ({ev[0]['posao']})", branch=GRANA)
    except Exception as x: sys.stderr.write(f"revizija greška: {x}\n")
    if ok: del _BUF[:len(ev)]
    _LAST[0] = time.time(); return ok
def proveri(tekst):
    """(ispravno, broj_redova, prvi_los_red)"""
    prev = "0" * 64; n = 0
    for i, l in enumerate([l for l in tekst.splitlines() if l.strip()], 1):
        e = json.loads(l); h = e.pop("h", None)
        if e.get("prev") != prev or hashlib.sha256(_kanon(e).encode("utf-8")).hexdigest() != h: return False, i - 1, i
        prev = h; n = i
    return True, n, None
if __name__ == "__main__" and sys.argv[1:2] == ["--proveri"]:
    for p in sys.argv[2:]:
        ok, n, bad = proveri(open(p, encoding="utf-8").read())
        print(p, "ISPRAVAN" if ok else f"IZMENJEN od reda {bad}", f"({n} ispravnih redova)")
