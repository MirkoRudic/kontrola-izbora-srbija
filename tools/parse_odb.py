# Parsiranje OCR teksta rešenja o biračkim odborima -> sastav po BM
import json,re,glob,os,sys,unicodedata,collections
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from translit import lat
def low(s): return lat(s or '').lower()
GK=[(' puzs ','STUD'),(' pus ','STUD'),(' sdps ','SDPS'),(' sns ','SNS'),('ne sme da stane','SNS'),(' sps ','SPS'),(' ssp ','SSP'),(' nps ','NPS'),(' zlf ','ZLF'),(' svm ','SVM'),(' psg ','PSG'),(' js ','JS'),(' ds ','DS'),(' ms ','MI'),('studente','STUD'),('socijaldemokrat','SDPS'),('vučić','SNS'),('vucic','SNS'),('socijalist','SPS'),('dačić','SPS'),('narodni pokret','NPS'),('novo lice','NPS'),
    ('slobode i pravde','SSP'),('slobodnih građana','PSG'),('sda ','PSG'),('pdd','PSG'),('zeleno','ZLF'),('vojvođansk','SVM'),('vojvodjansk','SVM'),('mađar','SVM'),
    ('nada','NADA'),('dss','NADA'),('srce','SRCE'),('centar','SRCE'),('ekološk','EU'),('jedinstven','JS'),('palma','JS'),('pups','PUPS'),('zdrava','ZS'),
    ('snaga naroda','MI'),('glas iz naroda','MI'),('mi -','MI'),('mi –','MI'),('demokratsk','DS'),('zavetnic','ZAVET'),('radničk','RP_RS'),('ruska','RP_RS'),
    ('chc','SNS'),('srpska napredna','SNS'),(' eko ','EU'),('rp rs','RP_RS'),('načelnik','ADMIN'),('načelnic','ADMIN'),('uprave','ADMIN'),('ministar','ADMIN'),('upravljanja','ADMIN')]
def gkey(g):
    l=' '+re.sub(r'[^a-zčćžšđ]+',' ',low(g))+' '
    for k,v in GK:
        if k in l: return v
    return None
def nice(n):
    n=re.sub(r'[^A-Za-zА-Яа-яЂђЈјЉљЊњЋћЏџČčĆćŠšŽžĐđ \-]','',n).strip()
    n=re.sub(r'\s+',' ',n)
    n=lat(n)
    n=re.sub(r'^(\S+\s+\S+(?:\s+\S+)?)\s+(?:iz|IZ|Iz)(?:\s.*)?$',r'\1',n)
    n=re.sub(r'^(?:se|Se|SE)\s+','',n)
    return ' '.join(w[:1].upper()+w[1:].lower() if not w.isupper() or len(w)>1 else w for w in n.split()) if n else None
ROLE=[('predsednik',r'(?<!заменик )(?<!заменика )председник\s*[:;]'),('zamenik predsednika',r'заменик\s+председника\s*[:;]?'),
      ('1. član',r'(?:(?<!заменик )1\s*[.,]\s*члан|(?<!заменик )члан\s*1)\s*[:;]'),('zamenik 1. člana',r'заменик\s+(?:1\s*[.,]?\s*члана|члана\s*1)\s*[:;]?'),
      ('2. član',r'(?:(?<!заменик )2\s*[.,]\s*члан|(?<!заменик )члан\s*2)\s*[:;]'),('zamenik 2. člana',r'заменик\s+(?:2\s*[.,]?\s*члана|члана\s*2)\s*[:;]?')]
END=r'\n\s*2\s*\.\s*Ово решење|\nОбразложење|\nО\s*б\s*р\s*а\s*з'
def parse_stalni(t):
    t=re.split(END,t)[0]
    hits=[]
    for role,rx in ROLE:
        m=re.search(rx,t,re.I)
        if m: hits.append((m.start(),m.end(),role))
    hits.sort()
    if len(hits)<6:
        # redosled uloga je uvek isti: oznake hvatamo i sa greškama u broju (OCR ili greška u rešenju)
        P=r'^[\s\-–—|_.]*(?:1\)\s*)?'
        G=P+r'(?:председник(?!а)|заменик\s+председника|заменик\s+(?:\d{1,2}\s*[.,]?\s*члана|члана\s*\d{0,2})|(?:\d{1,2}\s*[.,]\s*члан|члан\s*\d{0,2})(?!\w))[\s:;.,|]*'
        g=[(m.start(),m.end()) for m in re.finditer(G,t,re.I|re.M)]
        if len(g)==6: hits=[(a,b,ROLE[i][0]) for i,(a,b) in enumerate(g)]
    out=[]
    for i,(s,e,role) in enumerate(hits):
        seg=t[e:hits[i+1][0] if i+1<len(hits) else len(t)]
        seg=re.sub(r'\n\s*2\)\s*ЧЛАНОВИ\s*:?','',seg)
        m=re.search(r'^\s*(.*?)\s*[,.+]?\s*(?:[нhН][аa]\s*)?(?:пред?[лп][оo]г|предпог)\s*(.*)$',seg,re.S|re.I)
        m2=re.search(r'^\s*(.*?)\s*[,.+]?\s*((?:посланичк|начелни|александар\s+вучић|посланици\s+уз).*)$',seg,re.S|re.I)
        if m and (not m2 or len(m.group(1))<=len(m2.group(1))): name,by=m.group(1),m.group(2)
        elif m2: name,by=m2.group(1),m2.group(2)
        else: name,by=seg.strip().split('\n')[0],''
        name=re.sub(r'\s+из\s+[А-ЯЂЈЉЊЋЏA-Z].*$','',name.replace('\n',' '),flags=re.I)
        by=re.sub(r'\s+',' ',by).strip(' -–.;')
        out.append(dict(role=role,name=nice(name),by=lat(by)[:120] or None,key=gkey(by)))
    return out
if __name__=='__main__':
    st=collections.Counter();res={}
    for f in glob.glob('odb_s/*.txt')+glob.glob('odb_s_win/*.txt'):
        k=os.path.basename(f)[:-4]
        if k in res: continue
        t=open(f,encoding='utf-8',errors='replace').read()
        r=parse_stalni(t); res[k]=r
        st[len(r)]+=1; st['bez_kljuca']+=sum(1 for x in r if not x['key'])
    print(st)
    import random;random.seed(2)
    for k in random.sample(list(res),4): print(k,json.dumps(res[k],ensure_ascii=False)[:600])

# ---------- prošireni sastav ----------
LK=[('rusko-srp','RUSI_SRBI'),('rusko srp','RUSI_SRBI'),('rusi i srbi','RUSI_SRBI'),('studentsk','STUD'),('studenti pobe','STUD'),('vučić','SNS'),('ujedinjena srbija','SNS'),
    ('dačić','SPS'),('faktor stabil','SPS'),('ljajić','LJAJIC'),('ljudski','LJAJIC'),('mađar','SVM'),('magyar','SVM'),('pastor','SVM'),('zukorli','SPP'),('ujedinjenje','SPP'),
    ('ruska stranka','RUSKA'),('briks','RUSKA'),('autentičn','AUTDES'),('desnica','AUTDES'),('evropska srbija','EVROSRB'),('tepić','EVROSRB'),('ponoš','EVROSRB'),
    ('sda sandžak','SDA'),('čuvari sandžak','SDA'),('karić','KARIC'),('snaga srbije','KARIC'),('liberalno','LZS'),('bulić','SNAGA_BULIC'),('biram pravdu','SNAGA_BULIC'),
    ('ćale','DJURIC'),('đurić','DJURIC'),('gajić','GAJIC'),('alternativa za srbiju','GAJIC'),('albansk','ALB'),('majka srbija','MAJKA'),('gruda','MAJKA')]
def lkey(t):
    l=low(t)
    for k,v in LK:
        if k in l: return v
    return None
WORD=r"[A-Za-zА-Яа-яЂђЈјЉљЊњЋћЏџČčĆćŠšŽžĐđ]{2,}"
def pname(s):
    s=re.split(r',|\n|\s+и\s*$|\s+на\s+пред|\|',s)[0]
    ws=re.findall(WORD+r"(?:-"+WORD+")?",s)
    ws=[w for w in ws if w.lower() not in ('на','и','предлог','m')][:3]
    return nice(' '.join(ws)) if ws else None
def parse_prosireni(t):
    t=re.split(END,t)[0]
    m0=re.search(r'именују\s+се',t,re.I)
    if m0: t=t[m0.end():]
    ev=[]
    for m in re.finditer(r'заменик\s+члана\s*[:;.]?\s*',t,re.I): ev.append((m.start(),m.end(),'d'))
    for m in re.finditer(r'(?:\d+\s*[.,]\s*)?(?<![Зз]аменик )(?<![Зз]аменика )\bчлан\s*[:;.]?\s*',t,re.I):
        if not any(a<=m.start()<b for a,b,_ in ev): ev.append((m.start(),m.end(),'m'))
    for m in re.finditer(r'предлог\s+подносиоца\s+(?:проглашене\s+)?(?:изборне\s+)?листе\s*:?\s*',t,re.I): ev.append((m.start(),m.end(),'L'))
    ev.sort()
    out=[];pend=[]
    for i,(s,e,k) in enumerate(ev):
        nxt=ev[i+1][0] if i+1<len(ev) else len(t)
        seg=t[e:nxt]
        if k in 'md': pend.append((k,pname(seg)))
        else:
            lt=re.split(r';\s*\n|\n\s*-|\n\s*\d+\s*[.,]\s*члан',seg)[0]
            key=lkey(lt); rec=dict(key=key,list=re.sub(r'\s+',' ',lat(lt)).strip(' ;:.')[:140],member=None,deputy=None)
            for kk,nm in pend:
                if kk=='m' and not rec['member']: rec['member']=nm
                elif kk=='d' and not rec['deputy']: rec['deputy']=nm
            if out and out[-1]['key']==key and key and (not out[-1]['member'] or not out[-1]['deputy']) and not (rec['member'] and out[-1]['member']):
                out[-1]['member']=out[-1]['member'] or rec['member']; out[-1]['deputy']=out[-1]['deputy'] or rec['deputy']
            else: out.append(rec)
            pend=[]
    return out
