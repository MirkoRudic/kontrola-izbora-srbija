# Telegram poruke za izbornu noć (poziva ih rik_live.py).
# Tajne (GitHub Secrets): TELEGRAM_TOKEN (obavezno), TELEGRAM_CHAT (opciono – ako fali, uzima se poslednja grupa u kojoj je bot).
import json, os, urllib.request, urllib.parse

# liste 2026 (redni broj)
SL, SNS, SPS, AD, ES = 3, 1, 2, 8, 9
MANJINE = [4, 5, 6, 7, 10, 13, 14, 17, 18]   # RIK: rešenja o položaju izborne liste nacionalne manjine (2026)
OSTALI = [11, 12, 15, 16]
SNS23 = 1

def sim_lists():
    """Proba na rezultatima 2023: liste 2023 raspoređene u iste grupe (SL ≈ Srbija protiv nasilja, AD ≈ NADA, ES ≈ Zavetnici/Dveri)."""
    global SL, SNS, SPS, AD, ES, MANJINE, OSTALI
    SL, SNS, SPS, AD, ES = 7, 1, 2, 5, 4
    MANJINE = [6, 8, 9, 13, 16, 18]; OSTALI = [3, 10, 11, 12, 14, 15, 17]

B = lambda t: f"<b>{t}</b>"
SITE = "kontrola-izbora-srbija.pages.dev"

def fnum(n):
    """Kratko: 987 · 123,6k · 1,34M (da poruka ne puca u redu)"""
    n = int(n)
    if n >= 999_950: return f"{n/1e6:.2f}M".replace(".", ",")
    if n >= 1000: return f"{n/1e3:.1f}k".replace(".", ",")
    return str(n)
def fpct(x, d=1): return f"{x:.{d}f}".replace(".", ",")
def sgn(x): return ("+" if x > 0 else "−" if x < 0 else "±") + fpct(abs(x))
def arrow(x): return "↗️" if x > 0 else "↘️" if x < 0 else "→"
def emo(x, ch):
    """0–2 ništa, 2–4 jedan, 4–8 dva, preko 8 tri (x = pozitivna razlika u p.p.)"""
    if x < 2: return ""
    return ch * (1 if x < 4 else 2 if x <= 8 else 3)

def totals(UNITS, LU):
    """Zbir obrađenih BM (2026), isto za uparena BM (2026 i 2023), procena ukupnog broja upisanih."""
    z = dict(voters=0, out=0, valid=0, lists=[0] * 18); zm = dict(voters=0, out=0, valid=0, lists=[0] * 18)
    ym = dict(voters=0, out=0, valid=0, lists=[0] * 18)
    done = n = 0; reg_est = 0; ob = 0
    for uid, u in UNITS.items():
        bm = LU[uid]["bm"]
        vals = [s.get("y23", {}).get("voters") for s in u["st"].values() if s.get("y23")]
        avg = (sum(vals) / len(vals)) if vals else 800
        for sid, s in u["st"].items():
            n += 1; r = bm.get(sid) or {}
            if (r.get("status") or {}).get("oboreno"): ob += 1
            y = s.get("y23")
            if r.get("processed"):
                done += 1; reg_est += r.get("voters") or 0
                for k in ("voters", "out", "valid"): z[k] += r.get(k) or 0
                z["lists"] = [a + b for a, b in zip(z["lists"], r["lists"])]
                if y:
                    for k in ("voters", "out", "valid"): zm[k] += r.get(k) or 0; ym[k] += y.get(k) or 0
                    zm["lists"] = [a + b for a, b in zip(zm["lists"], r["lists"])]
                    ym["lists"] = [a + b for a, b in zip(ym["lists"], y["lists"])]
            else:
                reg_est += (y or {}).get("voters") or avg
    return dict(z=z, zm=zm, ym=ym, done=done, n=n, reg_est=reg_est, ob=ob)

def message(T, hhmm):
    z, zm, ym = T["z"], T["zm"], T["ym"]
    if not T["done"] or not z["valid"]: return None
    p = lambda i: 100 * z["lists"][i - 1] / z["valid"]
    sl, sns = p(SL), p(SNS)
    head = f"{hhmm}"
    # 💋 SL vodi do 2 %, 💋💋 vodi 2 % i više, 💋💋💋 SL preko 50 %; ⚔️ razlika SL–SNS manja od 2
    if sl > 50: head += " 💋💋💋"
    elif sl - sns >= 2: head += " 💋💋"
    elif sl > sns: head += " 💋"
    if abs(sl - sns) < 2: head += " ⚔️"
    L = [head, f"{B('Obrađeno:')} {fpct(100*T['done']/T['n'])} % BM • {fpct(100*z['voters']/max(T['reg_est'],1))} % glasova"]
    turn = 100 * z["out"] / max(z["voters"], 1)
    t_line = f"{B('Izlaznost:')} {fpct(turn)} %"
    if zm["voters"] and ym["voters"]:
        d = 100 * zm["out"] / zm["voters"] - 100 * ym["out"] / ym["voters"]
        t_line += f" • {arrow(d)} {sgn(d)}" + (" " + emo(d, "🔥") if emo(d, "🔥") else "")
    L += [t_line, ""]
    rk = emo(sl - sns, "🚀") if sl > sns else ""
    L.append(f"{B('SL:')} {fnum(z['lists'][SL-1])} – {fpct(sl)} %" + (" " + rk if rk else ""))
    s_line = f"{B('SNS:')} {fnum(z['lists'][SNS-1])} – {fpct(sns)} %"
    if zm["valid"] and ym["valid"]:
        d = 100 * zm["lists"][SNS-1] / zm["valid"] - 100 * ym["lists"][SNS23-1] / ym["valid"]
        s_line += f" • {arrow(d)} {sgn(d)}" + (" " + emo(-d, "❄️") if d < 0 and emo(-d, "❄️") else "")
    L += [s_line, ""]
    for name, idx in (("SPS", [SPS]), ("AD", [AD]), ("ES", [ES]), ("Manjine", MANJINE), ("Ostali", OSTALI)):
        v = sum(z["lists"][i - 1] for i in idx)
        L.append(f"{B(name + ':')} {fnum(v)} – {fpct(100*v/z['valid'])} %")
    L += ["", SITE]
    return "\n".join(L)

def slot(now):
    """21:00–00:59 na pola sata, posle toga na sat. Pre 21 h nema redovnih poruka."""
    h, m = now.hour, now.minute
    if h >= 21 or h < 1: return f"{now:%d.%m.} {h:02d}:{0 if m < 30 else 30:02d}"
    if 1 <= h < 12: return f"{now:%d.%m.} {h:02d}:00"
    return None

def _api(token, method, data=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = urllib.parse.urlencode(data).encode() if data else None
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30).read())

# grupa u kojoj je bot (naučeno 21.10.); rezerva ako nema tajne TELEGRAM_CHAT ni stanja u telegram.json
KNOWN_CHAT = "-5301355164"
def chat_id(token, state):
    c = os.environ.get("TELEGRAM_CHAT") or state.get("chat")
    if c: return c
    try:
        ups = _api(token, "getUpdates").get("result", [])
        chats = [u.get("message", u.get("my_chat_member", {})).get("chat") for u in ups]
        chats = [c for c in chats if c]
        grp = [c for c in chats if c.get("type") in ("group", "supergroup")]
        c = (grp or chats)[-1]["id"] if (grp or chats) else None
        if c: state["chat"] = str(c)
        return state.get("chat") or KNOWN_CHAT
    except Exception: return KNOWN_CHAT

def maybe_send(T, now, statef, log, test=False):
    """Šalje po rasporedu + odmah na prve rezultate, 50 %, 90 %, 99 % i novo oboreno BM."""
    token = os.environ.get("TELEGRAM_TOKEN")
    state = json.load(open(statef)) if os.path.exists(statef) else {}
    frac = T["done"] / max(T["n"], 1)
    reasons = []
    s = slot(now)
    if s and s != state.get("slot") and T["done"] and not state.get("final"): reasons.append("raspored")
    for key, cond in (("prvi", T["done"] > 0), ("50", frac >= .5), ("90", frac >= .9), ("99", frac >= .99)):
        if cond and key not in state.get("mile", []): reasons.append(key); state.setdefault("mile", []).append(key)
    if T["ob"] > state.get("ob", 0): reasons.append("oboreno")
    if not reasons and not test: return False
    msg = message(T, now.strftime("%H:%M"))
    if not msg: return False
    import hashlib, time as _t
    body = hashlib.sha1("\n".join(msg.split("\n")[1:]).encode()).hexdigest()[:16]
    if reasons == ["raspored"] and not test and body == state.get("last") and _t.time() - state.get("last_t", 0) < 3600:
        if s: state["slot"] = s
        json.dump(state, open(statef, "w")); return False  # isti brojevi kao prošla poruka – ne ponavljaj (najviše jednom na sat)
    if "99" in reasons: msg = "✅ <b>Obrađeno preko 99 % BM – poslednja poruka.</b>\n\n" + msg; state["final"] = True
    if not token: log("telegram: nema TELEGRAM_TOKEN – poruka nije poslata:\n" + msg); return False
    c = chat_id(token, state)
    if not c: log("telegram: ne znam kome da šaljem (pošalji /start botu ili ga dodaj u grupu)"); return False
    try:
        _api(token, "sendMessage", dict(chat_id=c, text=msg, parse_mode="HTML", disable_web_page_preview="true"))
        log("telegram: poslato (" + ", ".join(reasons) + ")")
    except Exception as e:
        log("telegram: greška " + str(e)[:120]); return False
    if s: state["slot"] = s
    state["ob"] = T["ob"]; state["last"] = body; state["last_t"] = _t.time()
    json.dump(state, open(statef, "w"))
    return True


def demo(log):
    """Probne poruke sa izmišljenim brojevima da se vide svi emodžiji (ručno pokretanje)."""
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token: log("telegram demo: nema tokena"); return
    c = chat_id(token, {})
    def fake(sl, sns, turn23, turn26, sns23):
        L = [0] * 18; L[SL-1] = sl * 100; L[SNS-1] = sns * 100; L[SPS-1] = 500; L[AD-1] = 300; L[ES-1] = 200
        rest = 10000 - sum(L); L[MANJINE[0]-1] = rest // 2; L[OSTALI[0]-1] = rest - rest // 2
        z = dict(voters=17000, out=int(170 * turn26), valid=10000, lists=L)
        y = dict(voters=17000, out=int(170 * turn23), valid=10000, lists=[0] * 18); y["lists"][SNS23-1] = sns23 * 100
        return dict(z=z, zm=z, ym=y, done=410, n=1000, reg_est=40000, ob=1)
    for name, T in (("tesna trka", fake(44, 43, 58, 61, 47)), ("SL vodi 5", fake(45, 40, 58, 64, 47)),
                    ("SL preko 50", fake(53, 35, 58, 69, 47)), ("SNS vodi", fake(30, 52, 58, 57, 47))):
        _api(token, "sendMessage", dict(chat_id=c, text="🧪 PROBA – " + name + "\n" + message(T, "22:30"), parse_mode="HTML", disable_web_page_preview="true"))
        log("telegram demo poslato: " + name)
