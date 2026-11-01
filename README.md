# Revizioni dnevnik – Kontrola izbora

Ovde se samo dodaje: kada je koji posao pročitao RIK i šta je preuzeo (vreme, BM, link, sha256 fajla).

- Fajlovi: `revizija/<gde>/<posao>/<datum>.jsonl`, jedan JSON red po događaju.
- Lanac heševa: svaki red ima `prev` (heš prethodnog reda) i `h` (sha256 tog reda), pa se svaka izmena ili brisanje reda vidi.
  Provera: `python tools/revizija.py --proveri <fajl>` (alat je na grani `main`).
- Grana je zaštićena pravilom na GitHub-u: ne može se obrisati niti prepisati (force push).

Mirko & Claude (Anthropic)
