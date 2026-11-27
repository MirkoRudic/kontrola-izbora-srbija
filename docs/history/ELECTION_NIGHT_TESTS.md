# Probe izborne noći i plan (oktobar 2026)

Premešteno iz projektnih dokumenata `proba-2-izvestaj.md`, `proba-3-izvestaj.md` i `kontrola-izbora-srbija-plan.md` 27.11.2026. Istorija; trenutno stanje je u `STATUS.md`.

## Proba 2 (noć 22/23.10.2026, 01:05–05:07)

Simulacija na rezultatima i zapisnicima iz 2023: GitHub, laptop (nadzor, zapisnici, čitanje, rezerva), oblak, Telegram, Google Drive, aplikacija. Ceo lanac je radio.

| | |
|---|---|
| GitHub | 4 kruga sim probe + Telegram test, svi uspešni |
| Laptop – preuzeti zapisnici | 7.606 od 7.606, ≈43 u minuti |
| Google Drive kopija | 7.606 = 7.606 |
| Laptop – pročitano | 5.251 za 3,5 h (≈22–25 u minuti) |
| Kandidati za oblak | 759 (≈15 % pročitanih) |
| Oblak – pročitano | 272 (P 107, ! 57) |
| Oblak – brzina | ≈3 u minuti dok radi, ≈14 min pripreme na početku svake sesije |

Ručno provereno 5 „!“: svih 5 oblak tačno pročitao, razlika zapisnik–RIK zaista postoji.

Puklo i popravljeno:
1. Telegram nije slao („ne znam kome da šaljem“): grupa je bila samo u `live/telegram.json`, obrisanom pri čišćenju. Grupa upisana u kod kao rezerva (e22605b).
2. Laptop nije čitao 20 min: spisak preuzetih upisivao se tek na kraju kruga (prvi krug > 2 h). Upis na 30 s (578c83f).
3. Rezerva ne bi preuzela od zaglavljenog GitHub-a: gledala je samo da li posao postoji; provere bez tokena na limitu 60/h, greška limita tumačena kao „GitHub radi“. Sada GitHub objavljuje bar na 10–19 min i bez novih rezultata, rezerva preuzima kad je objava starija od 25 min (b56414b). Prelaz proveren (03:13 → 03:14, povlačenje 03:32).
4. Promena režima nije gasila poslove prethodnog režima (7ec1204).
5. Nadzor jednom nestao (00:35, uzrok nepoznat); planer ga vratio. Sada beleži greške umesto pada.

Odluke koje su tražene od Mirka: blaži znak kad se razlikuje samo broj upisanih; oznaka „pogrešan zapisnik na RIK-u“ (npr. Novi Beograd BM 20 ima zapisnik BM 21); duže sesije oblaka; proširiti vrste primedbi („Ostalo“ 67 od ≈150); 1.051 od 8.348 BM bez svih 6 imena stalnog sastava.

Primećeno: posao zapisnika ne staje tačno u `--until`, nego na kraju intervala čekanja (do 10 min kasnije).

## Proba 3 (23/24.10.2026, 20 h – 09 h)

Sistem je radio celu noć bez zastoja i intervencije.
- GitHub: 19 krugova uspešno; objavljeno 7.595 od 8.392 BM (koliko simulacija 2023 sadrži).
- Laptop: zapisnici za 7.606 BM, 1.596 kandidata za oblak, ≈43 upisa na sat; rezerva nije morala da preuzme.
- Oblak: svih 1.596 do 03 h; po satu 278, 59, 391, 114, 202, 317, 210, 25. Uzrok sporih sati (21 h, 23 h) nije utvrđen.

Nalazi: P 253, AI uočio 977, „!“ 53, razlika samo u upisanim (≠) 39, na RIK-u zapisnik drugog BM 137, greške čitanja koje je alat sam izbacio 8.

Popravljeno tokom noći:
- Lažni P (lokalni čitač palio P i kad je polje prazno): P se pali samo kad oblak potvrdi.
- Lažni „!“ zbog čitanja (Despotovac BM 39: /61/ pročitano kao 161): alat izbacuje takve greške (kose crte, zbir lista, izašlih više od upisanih); uputstvo oblaku: kose crte nisu cifra 1.
- Primedbe razdvojene: P (članovi odbora), „AI uočio“ (oblak), posmatrači posebno; vrste po OEBS/ODIHR i CRTA; ispravke u zapisniku se ne beleže.
- Telegram: bez reda „oboreni BM“, bez ikonice sata, brojevi sa zarezom, bez ponavljanja iste poruke.

Za tumačenje 2023: velika neslaganja uglavnom su od ponovljenog glasanja (RIK 30.12.2023. ponovio na 27 BM, 2.1.2024. na još 8); rezultati na RIK-u su sa ponovljenog, zapisnik sa prvog (npr. Koceljeva BM 26, Kula BM 7).

Greška u nadzoru (Claude): u 03:02 javljeno da je sve stalo od 01:04 — netačno, lokalna kopija grane `uzivo` se nije osvežavala.

## Plan za izbornu noć (stanje 23.10.2026)

1. GitHub (`izborna-noc.yml`, `tools/rik_live.py`): RIK → grana `uzivo` i Telegram; objava bar na 10–19 min; sam pokreće krugove od 25.10. 19:40 do 26.10. 07:00.
2. Laptop (DELLBOY), planer „Kontrola – nadzor“ (na 10 min i pri prijavi), poslovi po `zadaci\rezim.json`: zapisnici (arhiva + kopija na Google Drive), čitanje, rezerva `rik_live --standby`.
3. Čitanje: ≈22–25 BM/min, ≈15 % ide oblaku; laptop sam nikad ne upisuje „!“.
4. Oblak (zakazani zadatak na sat, 25.10. 20:00 – 27.10. 12:00): „!“ uz svež RIK.
5. Rešenja o odborima: GitHub ih pronalazi, RIK mu ne daje PDF → čita laptop (`odbori_izm_laptop.json`).
6. Osnovni sastavi 23.10: pun sastav 8.109 od 8.392 BM; bez imena 157 pozicija, bez predlagača 2.076; 889 BM bez adrese; 2.966 BM bez tačne tačke na mapi.
7. Posle izbora: od ponedeljka 7 h vući dok RIK ne obradi 99 %, pratiti poništavanja.
