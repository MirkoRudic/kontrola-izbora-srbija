# Čitanje rezultata iz zapisnika biračkih odbora (parlamentarni izbori Srbija)

Dobijaš JSON spisak (putanja ti je data): lista stavki {"id", "opstina", "n" (broj BM), "img" (putanja do JPG slike), "orijentacija"}.

Svaka slika je sklopljena od isečaka prve strane zapisnika RG-2 (rukom popunjen):
- gore levo: tačke 1–4 (1 = broj biračkog mesta, 4 = broj birača upisanih u izvod iz biračkog spiska);
- dole levo: tačke 11.1–11.4 (11.1 izašli, 11.2 listića u glasačkoj kutiji, 11.3 nevažeći, 11.4 važeći);
- desno: tabela 11.5, dve kolone: redni broj izborne liste i broj glasova te liste (nazivi lista su odsečeni).
Za izbore 2020 (obrazac NPRS-14/20) levo je gore tačka 1 (broj BM), a ispod tabela 12.1–12.7: 12.1 upisani, 12.2 glasali (= izašli), 12.3 primljenih listića, 12.4 neupotrebljenih, 12.5 listića u kutiji, 12.6 nevažeći, 12.7 važeći; desno je tabela 12.8 sa glasovima lista (21 lista). Tada u JSON upiši izasli = 12.2, u_kutiji = 12.5, nevazeci = 12.6, vazeci = 12.7, upisani = 12.1.
Ako je "orijentacija" "visejezicno" (2020, višejezični obrazac): slika su 2–3 cele strane (spreada) zapisnika jedna ispod druge; na njima nađi tabelu 12.1–12.7 i tabelu 12.8 sa 21 listom (glasovi u desnoj koloni; tabela se nastavlja preko više strana); broj BM nije na slici, upiši "bm" iz polja "n".
Ako je "orijentacija" "uspravno", slika je cela strana i polja treba naći na njoj.

Za svaku stavku otvori sliku alatom Read i pročitaj brojeve. Pravila:
- Crtica, kosa crta ili prazno polje u tabeli = 0.
- Precrtan broj sa upisanim novim (često sa parafom) = važi NOVI broj.
- Obavezno proveri: zbir glasova svih lista mora biti jednak 11.4 (važeći), a 11.2 = 11.3 + 11.4 (za 2020: 12.5 = 12.6 + 12.7). Ako zbir ne odgovara, pogledaj ponovo baš sumnjive redove (ispravke, jedinice koje liče na crtice, sedmice, četvorke) i redosled redova. Ako i dalje ne odgovara, upiši ono što piše i u "napomena" kratko navedi razliku.
- Ako je neko polje zaista nečitko, stavi null i to navedi u "napomena". Ne nagađaj.
- Ako slika nije zapisnik RG-2 ili su isečci promašili polja, stavi "nije_procitano": "kratak razlog".

Upiši rezultat u fajl (putanja ti je data) kao JSON listu, po jedna stavka za SVAKO "id", istim redom:
{"id":"…","bm":18,"upisani":649,"izasli":432,"u_kutiji":432,"nevazeci":16,"vazeci":416,"liste":[203,56,34,9,29,21,15,0,7,6,12,12,1,5,0,0,2,1,3],"napomena":"lista 9: 97 precrtano, važi 7"}
"liste" je niz u redosledu tabele (lista 1, 2, 3, …), dužine koliko tabela ima redova.

Pomoćne skripte i isečke drži SAMO u folderu /tmp/k22/rad_<broj serije>/ (napravi ga), nikad u zajedničkom scratchpad folderu – paralelno radi više čitača. Prepisuj fajl posle svakih 10 stavki, da se ništa ne izgubi. Ne pokreći git, ne šalji ništa na mrežu, ne menjaj druge fajlove.
Na kraju vrati SAMO JEDAN RED: „gotovo N, zbir ok M” (bez objašnjenja; sve napomene su već u fajlu).
