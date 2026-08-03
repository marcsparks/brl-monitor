# CLAUDE.md — project context for Claude Code sessions

## What this is
**BRL Monitor** — public dashboard measuring Brazil's stablecoin & tokenization economy.
Static site (index.html, vanilla JS) + Python-stdlib collector + GitHub Actions cron (2×/day) + GitHub Pages. Cost target: $0/mo. Owner: Marc (founder, GTM background, not a career engineer — explain technical tradeoffs plainly).

## Non-negotiable editorial rules (the product IS these rules)
1. **Complete-only dashboard**: only datasets 100% complete within a declared perimeter — *complete by construction* (on-chain reads of enumerated contracts) or *complete by law* (BCB/Receita/CVM mandatory reporting). Partial/estimated data NEVER appears as a dashboard figure — it goes in Research essays as "two measurements and the gap."
2. **Provenance on every number**: source + timestamp + link (explorer or official publication). The ⓘ tooltips and "verify ↗" links are core product, not decoration.
3. **Never fabricate**: a failed fetch renders "—" plus an error banner. No estimates to fill gaps, ever.
4. **License tracker entries must cite a public record**; "no public record found" is itself a valid honest status.
5. This project publishes data. It never touches, routes, or advises on money — that keeps it license-free (Brazil: BCB Res. 519/520/521 VASP perimeter, Res. 561 eFX). Don't add features that cross that line.

## Architecture
- `config/registry.json` — token registry: contracts, API endpoints, explorer links. Add tokens here only with verified contract addresses.
- `collector/collect.py` — stdlib-only (keep it dependency-free). Fetches → computes league table/deltas → writes `data/latest.json`, `data/snapshots/YYYY-MM-DD.json`, appends `data/history.json`. `--offline` runs against `tests/fixtures/` (regenerate: `python3 tests/make_fixtures.py`).
- `collector/backfill.py` — one-time CoinGecko market-cap history backfill.
- `index.html` — reads `data/*.json` client-side. Design system: CSS vars, light/dark via prefers-color-scheme; palette follows the repo's existing tokens (--s1..--s6 categorical, fixed order per token; never re-color by rank).
- `.github/workflows/collect.yml` — cron 09:00/21:00 UTC + manual dispatch (input `backfill=yes` for first run). Commits data/ back to main.

## Known quirks & decisions
- BCB SGS `/ultimos` endpoint can lag days (server caching) — ref_date is displayed with the value, so it stays honest. Alternative: explicit dataInicial/dataFinal params.
- BRZ Stellar leg **excluded** deliberately: 2B issued to treasury, 8 funded holders → dormant, not circulating.
- BBRL has no market price → priced 1:1 via BCB PTAX, provenance says so.
- DefiLlama supplies are used as *multichain remainder* (total minus directly-read chains) for BRZ/BRLA; cREAL comes fully from DefiLlama pending contract verification.
- BCB VASP registers are empty until ~Oct 30, 2026 (filing deadline) — license tracker is hand-maintained in `data/licenses.json` until then; after, wire it to the BCB open-data CSV.

## Shipped in v0.2 (Aug 2026)
- Volume league (volume-first layout): collector/volumes.py — Blockscout transfer-event scan, mint/burn decomposition via type/zero-address, per-chain storage, 3-day rescan window, PAGE_CAP=40/chain/run, coverage declared per token (full/partial/none — BBRL XRPL & non-EVM legs NOT scanned; UI shows third-party anchor, never a guess).
- Tx-linked feed (events ≥ $100k with tx hashes) replacing snapshot-delta feed.
- USD league by asset (data/usd_league.json — official shares only, RLUSD "tracking" row; absolutes only when from an official publication).
- Market depth: max_ticket_1pct ≈ 1% × liquidity/2 (constant-product approx, documented as indicative).
- Period toggle (30d/90d/1y/all) driving stacked chart + table from volumes.json.

## Shipped in v0.2.1 (Aug 2026)
- Hero chart → cumulative stacked area (daily; end of curve = period total); hover tooltip.
- Honest scan windows: volumes.py records per-chain `chain_since` (+1 day when page-capped, since the cap cuts mid-day) → token `scan_since`; UI sums ONLY days ≥ scan_since, shows "since MM-DD" per token, hides period toggles the data can't fill (they unlock as the window grows). Velocity normalizes over days actually covered.
- Failed-source tokens: collect.py sets supply/usd=None + source_failed=true (never a misleading 0); UI renders "—" + "source failed this run" chip (cREAL case).
- Float league: snapshot timestamp in header; Δ float (period) column from history.json, driven by the same period toggle as the volume league; supply/≈USD ⓘ tooltips; backing chips wrap (.wraptd).
- Workflow inputs: volumes_pages (env VOLUMES_PAGE_CAP) + volumes_days (--backfill-days, forces deep re-backfill; idempotent since window days are overwritten per chain).
- CoinGecko history backfill run on live repo (backfill=yes) → ~13 months of float history.

## v1.1 backlog (priority order)
1. XRPL volume scan for BBRL (issuer account_tx — rippling means issued-currency payments touch the issuer account) — the volume league's biggest missing number.
2. Direct Celo contract reads for cREAL + BRZ/BRLA non-EVM remainders — DefiLlama is unreliable from GitHub Actions IPs (repeated failures Aug 3); Celo is EVM-compatible, Blockscout instance exists.
3. Validate BBRL/BRL1 volumes against rwa.xyz anchors.

## Ops notes (Aug 3, 2026)
- CoinGecko blocks GitHub Actions IPs → pre-launch history lives in data/backfill_coingecko.json (fetched once via browser, weekly grid); collect.py merges it below launch day. backfill.py kept for reference but cannot run in Actions.
- history.json hygiene filter in collect.py drops any pre-launch day carrying per-token "supply" (the v0 smoke-seed shape) — safe to keep permanently.
3. Receita monthly ingestion (per-asset volumes, history to 2019) → replace USD-league share labels with official absolutes.
4. Per-issuer pages: supply/holder history, concentration, peg chart; issuer fee-schedule links (linked, never transcribed).
5. License tracker → BCB register watcher (open-data CSV diff → alert). Oct 30 census report pre-drafted.
6. Weekly brief generator: facts-pack JSON → LLM draft → human edit (never auto-send).

## Strategy context (short)
Launch quietly, let cron accumulate real history, then launch essay ("Crown took #1 in seven months") into the Oct 30 VASP-census news cycle. Audiences: allocators, issuers (Crown/Transfero/Avenia/Braza/MB), chains (XRPL/Base/Celo/Polygon ecosystems — grant candidates), press. Revenue later: sponsorships/grants → paid brief tier → leads; dashboard data itself stays free and complete.
