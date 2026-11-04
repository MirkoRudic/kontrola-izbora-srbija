import json,re,collections
u26=json.load(open('st2026.json'))
import sys
Y=sys.argv[1]
SP=json.load(open(f'/tmp/arhc/{Y}/spisak.json'))
def norm(s):
    s=' '+s.lower()+' '
    s=re.sub(r'[^0-9a-zа-яђјљњћџ]+',' ',s)
    for a,b in [(' мз ',' месна заједница '),(' ош ',' основна школа '),(' дом здравља ',' дз '),(' дк ',' дом културе ')]: s=s.replace(a,b)
    return re.sub(r'\s+',' ',s).strip()
from difflib import SequenceMatcher
def sim(a,b): return SequenceMatcher(None,a,b).ratio()
by23={}
for p in SP['strane'].values():
    for r in p:
        by23.setdefault(r['opstina'].strip(),{'stations':[]})['stations'].append(dict(id=r['opstina']+'|'+r['n'],name=r['n']+' - '+(r['naziv'] or '')))
def split(nm):
    m=re.match(r'\s*(\d+)\s*-\s*(.*)',nm); return (int(m.group(1)),m.group(2).strip()) if m else (None,nm)
res={}; stats=collections.Counter()
for x in u26:
    y=by23.get(x['mun'])
    if x['mun']=='Град Врање' and y:
        y=dict(y,stations=y['stations']+[dict(s,name=s['name']) for s in by23['Градска општина Врањска Бања']['stations']])
    s26=[(sid,)+split(nm) for sid,nm in x['stations'].items()]
    M={}
    if y:
        s23=[(s['id'],)+split(s['name']) for s in y['stations']]
        n23={n:(sid,nm) for sid,n,nm in s23}
        same=sum(1 for sid,n,nm in s26 if n in n23 and norm(n23[n][1])==norm(nm))
        # 1) isti broj i isti naziv
        for sid,n,nm in s26:
            if n in n23 and norm(n23[n][1])==norm(nm): M[sid]=(n23[n][0],'isti broj i naziv')
        # 2) jedinstven naziv (ili grupa istih naziva iste velicine, redom)
        used={v[0] for v in M.values()}
        g26=collections.defaultdict(list); g23=collections.defaultdict(list)
        for sid,n,nm in s26:
            if sid not in M: g26[norm(nm)].append((n,sid))
        for sid,n,nm in s23:
            if sid not in used: g23[norm(nm)].append((n,sid))
        for k,lst in g26.items():
            c=g23.get(k,[])
            if c and len(c)==len(lst):
                for (n,sid),(n2,sid2) in zip(sorted(lst),sorted(c)): M[sid]=(sid2,'isti naziv, drugi broj' if n!=n2 else 'isti broj i naziv')
        # 3) isti broj, slican naziv (>=0.8)  ili jedinstven vrlo slican naziv (>=0.9)
        used={v[0] for v in M.values()}
        free23=[(sid,n,nm) for sid,n,nm in s23 if sid not in used]
        for sid,n,nm in s26:
            if sid in M: continue
            c=[(sim(norm(nm),norm(nm2)),sid2,n2) for sid2,n2,nm2 in free23 if sid2 not in used]
            if not c: continue
            same=[t for t in c if t[2]==n and t[0]>=0.55]
            best=sorted(c,reverse=True)
            if same: t=same[0]
            elif best[0][0]>=0.9 and (len(best)==1 or best[1][0]<best[0][0]-0.05): t=best[0]
            else: continue
            M[sid]=(t[1],'sličan naziv'); used.add(t[1])
        # 4) isti broj BM u obe godine i vecina naziva ista -> ostatak po broju (numeracija stabilna)
        if len(s26)==len(s23):
            exact=sum(1 for v in M.values() if v[1]=='isti broj i naziv')
            if exact>=0.7*len(s26):
                used={v[0] for v in M.values()}
                for sid,n,nm in s26:
                    if sid in M or n not in n23 or n23[n][0] in used: continue
                    M[sid]=(n23[n][0],'isti broj, drugi naziv'); used.add(n23[n][0])
    for sid,n,nm in s26:
        stats['upareno' if sid in M else 'bez para']+=1
    res[x['mun_id']]={sid:dict(n=n,name=nm,m=M.get(sid,(None,None))[0],how=M.get(sid,(None,None))[1]) for sid,n,nm in s26}
    if not y: print('nema',Y,':',x['mun'])
json.dump(res,open(f'match{Y}.json','w'),ensure_ascii=False)
print(stats)
# po jedinici sa najvise bez para
bad=sorted(((sum(1 for v in r.values() if not v['m']),k) for k,r in res.items()),reverse=True)[:12]
names={x['mun_id']:x['mun'] for x in u26}
print([(names[k],c,len(res[k])) for c,k in bad])
