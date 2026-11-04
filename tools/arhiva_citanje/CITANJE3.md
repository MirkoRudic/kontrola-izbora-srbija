# Završno čitanje – zapisnici 2020 (obrazac NPRS-14/20) koje ranije nije bilo moguće pročitati

Dobijaš JSON spisak stavki {"id","opstina","n" (broj BM),"slike":[putanje]}. Svaka slika je JEDNA CELA STRANA PDF-a zapisnika, redom (strana 1, 2, …). Zapisnik može biti jednojezičan (2 strane) ili višejezičan (3–8 strana, tekst na srpskom i jeziku manjine). Neke strane mogu biti okrenute naopako – tada je napravi uspravnom (PIL rotate(180)) u svom pomoćnom folderu i pogledaj je.

Za svaku stavku pogledaj strane alatom Read (po potrebi iseci i uvećaj deo strane PIL-om u pomoćnom folderu) i nađi:
- tabelu 12.1–12.7: 12.1 upisani, 12.2 glasali (= izašli), 12.5 listića u kutiji, 12.6 nevažeći, 12.7 važeći;
- tabelu 12.8: glasovi 21 izborne liste (desna kolona; tabela se može nastaviti na sledećoj strani).
Pravila: crtica/kosa crta/prazno = 0; precrtan broj sa upisanim novim = važi novi. Provera: zbir 21 liste = 12.7, a 12.5 = 12.6 + 12.7. Ako ne odgovara, ponovo pogledaj sumnjive redove; ako i dalje ne odgovara, upiši ono što piše i navedi razliku u "napomena". Nečitko polje = null + napomena. Ne nagađaj.
Ako dokument nije zapisnik (npr. Obrazac PO/2020 – ispravka omaške) ili je obrazac prazan/nepopunjen, ili tabele 12.x zaista nema ni na jednoj strani: "nije_procitano": "kratak razlog".

Rezultat: JSON lista, za svaku stavku istim redom:
{"id":"…","bm":<n>,"upisani":…,"izasli":…,"u_kutiji":…,"nevazeci":…,"vazeci":…,"liste":[21 broj],"napomena":"…"}
Pomoćne fajlove drži SAMO u datom pomoćnom folderu i obriši ga na kraju (rm -rf). Ne pokreći git, ne šalji ništa na mrežu, ne menjaj druge fajlove. Prepisuj rezultat posle svake 3 stavke.
Na kraju vrati SAMO JEDAN RED: „gotovo N, zbir ok M, nije zapisnik/prazno K”.
