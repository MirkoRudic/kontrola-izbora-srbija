# Druga runda čitanja – zapisnici kod kojih prvo čitanje nije dalo slaganje zbira

Dobijaš JSON spisak stavki {"id","opstina","n","slike":[putanje],"prvo":{prvo čitanje}}. Slike su veće rezolucije:
- 2022 (obrazac RG-2): "_a" = levi deo prve strane (tačke 1–4, i 11.1–11.4: 11.1 izašli, 11.2 u kutiji, 11.3 nevažeći, 11.4 važeći); "_b" = tabela 11.5 sa nazivima i glasovima 19 lista. Ako su slike cele strane (uspravni sken), nađi polja na njima.
- 2020 (obrazac NPRS-14/20): jedna slika; 12.1 upisani, 12.2 glasali (= izašli), 12.5 u kutiji, 12.6 nevažeći, 12.7 važeći, 12.8 glasovi 21 liste.

Za svaku stavku otvori sve njene slike alatom Read i pročitaj ponovo SVE brojeve, pažljivo, red po red (uporedi naziv liste i red sa brojem da ne pomeriš redove). Prvo čitanje ti je dato samo kao pomoć – ne veruj mu.
Pravila: crtica/kosa crta/prazno = 0; precrtan broj sa upisanim novim = važi novi. Provera: zbir lista = važeći, u kutiji = nevažeći + važeći.
Ako i posle pažljivog čitanja zbir ne odgovara, upiši ono što zaista piše i u "napomena" navedi da je razlika u samom zapisniku (npr. "zapisnik: zbir lista 610, a upisano važećih 616"). Nečitko polje = null + napomena.

Rezultat: JSON lista, za svaku stavku istim redom:
{"id":"…","bm":18,"upisani":649,"izasli":432,"u_kutiji":432,"nevazeci":16,"vazeci":416,"liste":[…],"napomena":"…","greska_u_zapisniku":true/false}
"greska_u_zapisniku": true ako je razlika stvarno u zapisniku (članovi odbora pogrešno sabrali/upisali), false ako se sada sve slaže.
Pomoćne fajlove drži SAMO u datom pomoćnom folderu. Ne pokreći git, ne šalji ništa na mrežu. Prepisuj rezultat posle svakih 5 stavki.
Na kraju vrati SAMO JEDAN RED: „gotovo N, zbir ok M, greška u zapisniku K”.
