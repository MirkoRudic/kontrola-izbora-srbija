# Rezultati ranijih izbora pročitani iz zapisnika (2022, 2020) -> arh/<god>.json za build_srb.py (4.11.2026)
#   python3 build_arh.py 2022
import json, sys, glob, re, os
from translit import lat
Y = sys.argv[1]; B = f'/tmp/k22/{Y}'
L = {'2022': ["Aleksandar Vučić – Zajedno možemo sve", "Ivica Dačić – Premijer Srbije", "Savez vojvođanskih Mađara – Ištvan Pastor",
              "Dr Vojislav Šešelj – SRS", "Marinika Tepić – Ujedinjeni za pobedu Srbije", "Dr Miloš Jovanović – NADA za Srbiju",
              "Milica Đurđević Stamenkovski – Zavetnici", "Muftijin amanet – SPP – Usame Zukorlić", "Moramo – Akcija – Ekološki ustanak – Ćuta – Ne davimo Beograd",
              "Suverenisti – Radulović, Stamatović, Stojković", "Boško Obradović – Dveri – POKS – Patriotski blok", "Zajedno za Vojvodinu – Vojvođani",
              "SDA Sandžaka – dr Sulejman Ugljanin", "Boris Tadić – Ajmo ljudi – SDS i partneri", "Alternativa za promene – Albanska demokratska alternativa",
              "Koalicija Albanaca doline", "Otete bebe – Ana Pejić", "Romska partija – Srđan Šajn", "Ruski manjinski savez – Milena Pavlović"],
     '2020': ["Aleksandar Vučić – Za našu decu", "Ivica Dačić – SPS, JS – Dragan Marković Palma", "Dr Vojislav Šešelj – SRS", "Savez vojvođanskih Mađara – Ištvan Pastor",
              "Aleksandar Šapić – Pobeda za Srbiju", "Za Kraljevinu Srbiju (POKS) – Žika Gojković", "Ujedinjena demokratska Srbija", "Akademik Muamer Zukorlić – SPP",
              "Metla 2020", "Milan Stamatović – Zdravo do pobede – Zdrava Srbija", "SDA Sandžaka – dr Sulejman Ugljanin", "Milica Đurđević Stamenkovski – Zavetnici",
              "Narodni blok – Velimir Ilić", "Sergej Trifunović – Pokret slobodnih građana", "Suverenisti", "Albanska demokratska alternativa – Ujedinjena dolina",
              "Grupa građana: 1 od 5 miliona", "Nek maske padnu – Zelena stranka – Nova stranka", "Ruska stranka – Slobodan Nikolić",
              "Čedomir Jovanović – Koalicija za mir", "Pokret Levijatan – Živim za Srbiju"]}[Y]
S = json.load(open(B + '/stavke.json'))
R = {}
for f in sorted(glob.glob(B + '/rez_*.json')):
    ids = {x['id'] for x in json.load(open(f.replace('rez_', 'serija_')))}
    for r in json.load(open(f)):
        if r['id'] in ids and not (r.get('nije_procitano') and r['id'] in R and not R[r['id']].get('nije_procitano')): R[r['id']] = r
for f in sorted(glob.glob(B + '/druga/rez2_*.json')):  # druga runda (veće slike) zamenjuje prvo čitanje
    ids = {x['id'] for x in json.load(open(f.replace('rez2_', 'serija2_')))}
    for r in json.load(open(f)):
        if r['id'] in ids and r.get('vazeci') is not None and r.get('liste'): R[r['id']] = r
for f in sorted(glob.glob(B + '/zavrsna/rezZ_*.json')):  # završno čitanje (sve strane) za ranije nepročitane
    ids = {x['id'] for x in json.load(open(f.replace('rezZ_', 'serijaZ_')))}
    for r in json.load(open(f)):
        if r['id'] in ids and r.get('vazeci') is not None and r.get('liste') and (r['id'] not in R or R[r['id']].get('nije_procitano') or R[r['id']].get('vazeci') is None): R[r['id']] = r
def rec(r):
    if r.get('nije_procitano') or r.get('vazeci') is None or not r.get('liste'): return None
    li = [int(x or 0) for x in r['liste']][:len(L)] + [0] * max(0, len(L) - len(r['liste']))
    o = dict(voters=r.get('upisani') or 0, out=r.get('izasli') if r.get('izasli') is not None else (r.get('u_kutiji') or 0),
             valid=r['vazeci'], invalid=r.get('nevazeci') or 0, lists=li)
    if sum(li) != r['vazeci']: o['pr'] = 1
    if r.get('napomena'): o['nap'] = r['napomena'][:300]
    if r.get('greska_u_zapisniku'): o['gz'] = 1
    return o
BYK = {}   # 'opstina|n' -> (rezultat, stavka)
BYM = {}   # opstina -> [rezultati]
for k, s in S.items():
    o = rec(R[k]) if k in R else None
    key = s['opstina'].strip() + '|' + s['n']
    BYK[key] = (o, s)
    if o: BYM.setdefault(s['opstina'].strip(), []).append(o)
M = json.load(open(f'match{Y}.json')); U26 = {x['mun_id']: x['mun'] for x in json.load(open('st2026.json'))}
def agg(lst):
    if not lst: return None
    a = dict(voters=0, out=0, valid=0, invalid=0, lists=[0] * len(L))
    for o in lst:
        for kk in ('voters', 'out', 'valid', 'invalid'): a[kk] += o[kk] or 0
        for i, v in enumerate(o['lists']): a['lists'][i] += v
        a['pr'] = a.get('pr', 0) + o.get('pr', 0)
    if not a['pr']: a.pop('pr')
    return a
out = dict(lists=L, st={}, u={}, meta=dict(procitano=len(R), stavki=len(S)))
for mid, st in M.items():
    mun = U26.get(mid)
    lst = BYM.get(mun, []) + (BYM.get('Градска општина Врањска Бања', []) if mun == 'Град Врање' else [])
    a = agg(lst)
    if a: out['u'][mid] = a
    for sid, v in st.items():
        if not v.get('m'): continue
        o, s = BYK.get(v['m'], (None, None))
        if s is None: continue
        d = dict(n=s['n'], name=lat(s.get('naziv') or ''), z=s['link'], how=v.get('how'))
        if o: d['y'] = o
        out['st'][sid] = d
os.makedirs('arh', exist_ok=True)
json.dump(out, open(f'arh/{Y}.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(Y, 'pročitano', len(R), 'od', len(S), '| BM 2026 sa podacima', sum(1 for d in out['st'].values() if 'y' in d), '| opština', len(out['u']))
