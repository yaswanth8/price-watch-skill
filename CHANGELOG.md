# Changelog

## 1.1.0 (2026-11-24)
- Version line, `VERSION` file and a once-per-chat update check (`scripts/check_update.py`, or a web fetch of `VERSION` without code) that tells you when to re-download the zip.
- Search rules: only dated prices count as "today", price-tracker pages first, warehouse-club prices never guessed, price-history answers from dated data only.
- Shorter Quick start.

## 1.0.0 (2026-11-24)
- `/price-watch <product>`: lowest price across the top stores (US, India, UK and more) with shipping, star rating, stock and buy links.
- At most two questions (variant, country). Works on every Claude plan with skills, Free included; 2 searches and 3 page opens per lookup.
- Optional watching: Price Watch dashboard artifact, alerts on every new low, scheduled checks where available.
- Safe buying: allowed stores, per-order cap, landed cost, duplicate-cart check, and no order without a live yes.
