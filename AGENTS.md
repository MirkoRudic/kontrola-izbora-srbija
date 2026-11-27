Važe pravila iz `D:\VAJB\vajb-osnova\RULES.md`. Ovde su arhitektura, zamke i izuzeci. Šta app radi iz ugla korisnika je u `SPECIFICATION.md` — svaka izmena ponašanja prvo tamo. Dokle smo stigli: `STATUS.md`. Šta je već probano i nije radilo: `ATTEMPTS.md` — pročitati pre predloga rešenja.

# Kontrola izbora · Srbija

Javni sajt sa rezultatima parlamentarnih izbora po biračkim mestima (BM) za celu Srbiju: 2026, 2023, 2022, 2020.
- Sajt: kontrola-izbora-srbija.pages.dev (Cloudflare Pages, build output `public/`, bez build koraka).
- Repo: MirkoRudic/kontrola-izbora-srbija. Laptop folder: `D:\VAJB\kontrolaizbora` (zadaci, podaci, OCR tessdata).
- Sestrinska app za Žabare (kontrola-izbora-zabari) je izbrisana (27.11.2026).

## Arhitektura
- `public/index.html` — cela app u jednom fajlu (~250 KB, ručno se menja). `public/sw.js`, `manifest.webmanifest` (PWA). `version.txt` = vreme objave.
- `public/data/` — statični podaci: `index.json` (regioni, opštine, BM), `geo.json`, `bib23.json`/`bib26.json` (biblioteka rešenja), `odbori_izm*.json`, `o23/`, `live/`.
- Grane: `main` (kod i podaci → Cloudflare objava), `uzivo` (rezultati izborne noći, dnevnik `logovi/`, `zap/` čitanja; app ih čita sa GitHub-a), `revizija`, `uzivo-kopija`, `o23-izmene-wip`.
- `functions/api/greska.js`, `poseta.js` — upis grešaka iz pregledača i anonimnih poseta u D1 `kontrola-srbija-posete` (binding `DB`). Brojevi se ne prikazuju javno.
- `tools/` — Python poslovi:
  - `rik_live.py` (+ `telegram.py`, `dnevnik.py`, `revizija.py`) — prati RIK i objavljuje rezultate po BM; `--standby` = rezerva na laptopu; `--provera-bm`.
  - `laptop_zapisnici.py`, `laptop_citanje.py`, `laptop_izmene.py`, `oblak.py` — arhiva originalnih zapisnika, čitanje lokalnim modelom (Ollama qwen2.5vl), čitanje kandidata u oblaku (Claude zakazani zadatak).
  - `odbori_novi.py`, `odbori_izmene.py`, `parse_odb.py`, `parse_seq.py`, `resenja_*.py`, `fix_stalni_win.py`, `prigovori.py` — rešenja o odborima, sastavi, prigovori.
  - `arhiva_zapisnika.py`, `citanje_arhiva.py`, `arhiva_citanje/` — zapisnici 2022 i 2020 iz RIK baze.
  - `izbor_izbora.py`, `mandati.py` — izmene app za izbor izbora i mandate (jednokratne skripte nad `index.html`).
- `.github/workflows/izborna-noc.yml` (RIK uživo; cron sada na 2 h danju), `odbori.yml` (nova rešenja; cron istekao 25.10.).

## Zamke
- RIK ne daje PDF-ove GitHub serveru → rešenja i zapisnike čita laptop; GitHub ih samo pronalazi.
- Na RIK-u su ponekad zamenjeni fajlovi (Ub: „broj 1“ sadrži BM 2) — povezivati po sadržaju, ne po imenu fajla.
- Ponovljeno glasanje 1.11.: zapisnik sa ponovljenog glasanja je glavni.
- Isto ime na više BM = imenjaci, ne ista osoba.
- Arhivski zapisnici: crtica = 0; čita se kolona rednih brojeva + kolona glasova.
- Laptop poslovi idu kroz Windows planer „Kontrola – nadzor“ po `zadaci\rezim.json`, nikad ne zavise od Claude aplikacije.
- Telegram token i ostale tajne su u GitHub Secrets / laptop `.env`, nikad u repo.

## Izuzeci od RULES.md
- Javni sajt na Cloudflare Pages, ne lokalna app: P1–P9, V1–V5 i UI12 (Podešavanja) ne važe.
- UI na srpskom ćirilicom/latinicom po izboru u app; brojevi srpski.
- `index.html` jedan fajl bez otiska u adresi (UI11); keš rešava `sw.js` i `version.txt`.
