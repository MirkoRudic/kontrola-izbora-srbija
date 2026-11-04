# python3 sledece.py 2022 N -> ispiše N sledećih serija koje nisu pokrenute i obeleži ih kao pokrenute
import json, os, sys, glob, subprocess
Y, N = sys.argv[1], int(sys.argv[2]); B = f'/tmp/k22/{Y}'; LF = B + '/pokrenuto.txt'
L = set(open(LF).read().split()) if os.path.exists(LF) else set()
subprocess.run(['python3', '/tmp/k22/serije.py', Y, '50'], capture_output=True)
S = sorted(f.split('_')[-1][:-5] for f in glob.glob(B + '/serija_*.json'))
nove = [s for s in S if s not in L and not os.path.exists(f'{B}/rez_{s}.json')][:N]
open(LF, 'a').write(' '.join(nove) + ' ')
print(' '.join(nove))
