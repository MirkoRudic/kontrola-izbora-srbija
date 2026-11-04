import json, glob, sys
Y = sys.argv[1]; B = f'/tmp/k22/{Y}'; R = {}
for f in sorted(glob.glob(B + '/rez_*.json')):
    try:
        ids = {x['id'] for x in json.load(open(f.replace('rez_', 'serija_')))}
        for r in json.load(open(f)):
            if r['id'] in ids: R[r['id']] = r
    except Exception as e: print('loš', f, e)
ok = sum(1 for r in R.values() if r.get('vazeci') is not None and r.get('liste') and None not in r['liste'] and sum(r['liste']) == r['vazeci'])
print(json.dumps(dict(procitano=len(R), zbir_ok=ok, problem=len(R) - ok)))
