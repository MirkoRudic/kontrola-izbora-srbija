# Rezervni parser stalnog sastava: imena idu redom predsednik, zamenik predsednika, 1. član, zamenik 1., 2. član, zamenik 2.
import re,sys
import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from parse_odb import gkey, nice
from translit import lat
ROLES=['predsednik','zamenik predsednika','1. član','zamenik 1. člana','2. član','zamenik 2. člana']
STOP=set('''Града Новог Сада Општине Општинске Градске Градска Републичке Народне Скупштине Посланичке Групе Групa Начелника Изборне Комисије
Србија Србије Странка Покрет Народни Слободе Правде Решење Решења Ово Закона Члан Члана Председник Председника Заменик Заменика Чланови Предлог
Уба Уб Бирачко Место Број Бирачког Одбора Сталном Саставу Управе Општинска Градска Комисија Посланичка Група Јединствена Социјалистичка Партија
Ново Лице Зелено Леви Фронт Не Давимо Београд Београда Покрета Странке Демократска Демократске Савез Војвођанских Мађара Посланици Студенте
Контролу Избора Уз За Сме Да Стане'''.split())
W=r"[А-ЯЂЈЉЊЋЏ][а-яђјљњћџ]+(?:-[А-ЯЂЈЉЊЋЏ][а-яђјљњћџ]+)?"
def parse_seq(t):
    m=re.search(r"именуј\w*\s+се",t); t=t[m.end():] if m else t
    t=re.split(r"\n\s*[|]?\s*2\s*[.,]\s*Ово решење|Образложење",t)[0]
    T=re.sub(r"\s+"," ",t)
    names=[]
    for mm in re.finditer(rf"(?<![\wА-Яа-я])({W}(?:\s+{W}){{1,2}})(?![\wА-Яа-я])",T):
        ws=[w for w in mm.group(1).split() if w not in STOP]
        if re.search(r"(?:груп\w|листе|предлог)\s*[:;,-]?\s*$",T[max(0,mm.start()-20):mm.start()]): continue  # ime vođe liste u nazivu predlagača
        if len(ws)>=2 and len(ws)==len(mm.group(1).split()): names.append((mm.start(),mm.end(),' '.join(ws)))
    if len(names)!=6: return []
    out=[]
    for i,(a,b,n) in enumerate(names):
        seg=T[b:names[i+1][0] if i+1<6 else len(T)]
        by=re.search(r"на\s+пред[лп]ог\s*:?\s*(.+)",seg)
        byt=lat(by.group(1)).strip(" ,;")[:140] if by else ""
        out.append(dict(role=ROLES[i],name=nice(n),by=byt or None,key=gkey(byt) if byt else None))
    return out
