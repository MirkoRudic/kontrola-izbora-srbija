import re,json,os
FIRST=set(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'imena_prva.json'))))
def _split(w):
    lw=w.lower()
    for k in range(min(len(lw)-3,12),2,-1):
        if lw[:k] in FIRST: return [w[:k],w[k:]]
    return [w]
_OK=re.compile(r"^[A-ZČĆŠŽĐ][a-zčćšžđ]+(?: [A-ZČĆŠŽĐ]\.?)?(?:[- ][A-ZČĆŠŽĐ][a-zčćšžđ]+)+$")
CUT={'za','zamenika','zamenik','predsednika','predsednik','člana','član','clana','narodni','pokret','ivica','dragan','zeleno','jmbg','na','pa','pačelnika','načelnika','opštinske','ošštinske','kao','vučić','vučić-srbija','srbija','srbije','akcije','sandžaka','partija','demokratske','demokratsko','monarhisti','nada','ne','sme','da','stane','been','novu','pos','dačić-socijalistička','socijalistička','palma','jedinstvena','levi','front','pcjgror','iz','sa','ul','broj'}
STRONG={'ne','sme','monarhisti','akcije','sandžaka','demokratske','demokratsko','sda','pdd','partija','socijalistička','vučić-srbija','jmbg','pačelnika','načelnika','opštinske','ošštinske','uprave','delovanje'}
LEAD={'kao','i','pod','na','pa','e','n','pije','vučić-srbija'}
JUNK={'tačka','gi','ii','ji','ha','ime','prezime'}
def ocisti(n):
    """Popravlja tipične OCR greške u imenu; vraća ime, '?' (nečitko) ili None."""
    if not n: return n
    n=re.sub(r'^\s*(?:se\s+)?imenuj[eu]\s*(?:se)?\s*:?\s*','',str(n),flags=re.I)
    if re.match(r'^\s*ime\s*\w{0,3}rezime',str(n),re.I) or re.search(r'komisij|imenuje|^\s*(članovi|čjan|čpan|llan|član)\s*$',str(n),re.I): return None
    t=re.sub(r'\s+',' ',str(n)).strip(' .,;:-_|')
    t=re.sub(r'^(ime i prezime|ime)\s+','',t,flags=re.I)
    t=re.sub(r'\s+(I\s*-|(?:Stranka|Poslani\w*|Oslani\w*|Grupe|Zamenik|Predlog)\b).*$','',t,flags=re.I)
    t=re.sub(r'\s*-\s*','-',t)
    tw=t.split(' ')
    while tw and (tw[0].lower() in LEAD or len(tw[0])<=2): tw=tw[1:]
    for i,w in enumerate(tw):
        lw=re.sub(r'[^a-zčćšžđ-]','',w.lower())
        if (i>=1 and lw in STRONG) or (i>=2 and lw in CUT): tw=tw[:i]; break
    if any(re.sub(r'[^a-zčćšžđ-]','',w.lower()) in STRONG for w in tw) or (len(tw)<2 and len(str(n).split())>=3): return '?'
    t=' '.join(tw)
    ws=t.split(' ')
    if len(ws)<=2 and any(len(w)>7 for w in ws) and not _OK.match(' '.join(w[:1].upper()+w[1:] for w in ws)): t=' '.join(p for w in ws for p in (_split(w) if len(w)>7 else [w]))
    t=re.sub(r'(?:\s+[A-Za-zČĆŠŽĐčćšžđ]{1,2})+$','',t) if len(t.split())>2 else t
    t='-'.join(w[:1].upper()+w[1:] for w in t.split('-'))
    t=' '.join(w[:1].upper()+w[1:] for w in t.split(' '))
    if _OK.match(t): return t
    return '?'
