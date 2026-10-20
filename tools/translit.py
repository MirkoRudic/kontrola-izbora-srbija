M={'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Ђ':'Đ','Е':'E','Ж':'Ž','З':'Z','И':'I','Ј':'J','К':'K','Л':'L','Љ':'Lj','М':'M','Н':'N','Њ':'Nj','О':'O','П':'P','Р':'R','С':'S','Т':'T','Ћ':'Ć','У':'U','Ф':'F','Х':'H','Ц':'C','Ч':'Č','Џ':'Dž','Ш':'Š'}
M.update({k.lower():v.lower() for k,v in M.items()})
def lat(s):
    if s is None: return None
    out=[];w=list(s)
    for i,c in enumerate(w):
        t=M.get(c,c)
        if len(t)==2 and c.isupper():
            nxt=w[i+1] if i+1<len(w) else ''; prv=w[i-1] if i>0 else ''
            if (nxt.isupper()) or (not nxt.isalpha() and prv.isupper()): t=t.upper()
        out.append(t)
    return ''.join(out)
