# python3 serije.py 2022 [velicina]  -> napravi serije od stavki koje nisu pročitane ni u obradi
import json, os, sys, glob
Y = sys.argv[1]; V = int(sys.argv[2]) if len(sys.argv) > 2 else 50
B = f'/tmp/k22/{Y}'; S = json.load(open(B + '/stavke.json'))
done = set()
for f in glob.glob(B + '/rez_*.json'):
    try:
        ids = {x['id'] for x in json.load(open(f.replace('rez_', 'serija_')))}
        done |= {r['id'] for r in json.load(open(f)) if r['id'] in ids}
    except Exception: pass
used = set()
for f in glob.glob(B + '/serija_*.json'):
    k = f.split('_')[-1][:-5]
    if not os.path.exists(f'{B}/rez_{k}.json'):
        used |= {x['id'] for x in json.load(open(f))}  # u obradi ili nedovršena
T = os.path.getmtime('/tmp/k22/komp.py') if Y == '2020' else 0
todo = [dict(id=k, opstina=v['opstina'], n=v['n'], img=v['img'], orijentacija=v['orijentacija']) for k, v in S.items() if k not in done and k not in used and not str(v['orijentacija']).startswith('greska') and os.path.exists(v['img']) and os.path.getmtime(v['img']) >= T]
n0 = max([int(f.split('_')[-1][:-5]) for f in glob.glob(B + '/serija_*.json')] + [0])
nova = []
full = len(sys.argv) > 3
for i in range(0, len(todo), V):
    if len(todo) - i < V and not full: break
    n0 += 1; json.dump(todo[i:i + V], open(f'{B}/serija_{n0:03d}.json', 'w'), ensure_ascii=False); nova.append(n0)
print(json.dumps(dict(ukupno=len(S), procitano=len(done), u_obradi=len(used), novih_serija=len(nova), serije=nova)))
