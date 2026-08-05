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

## Shipped in v0.3 (Aug 4, 2026) — coverage expansion
- Universe widened past the original 6 after Fintrender report review. Added two VERIFIED public tokens: **wBRL** (Ripio, reserve-backed, same 0xD76f5Faf6888e24D9F04Bf92a0c8B921FE4390e0 on 8 EVM chains — we read Base/Polygon/Ethereum directly, floor; ~$1.5M) and **BRLD** (Liqi, Brazil Real Digital, ~117M supply / ~$23M / 10.5k holders on public XDC Network).
- New collector reader `evm_rpc`: JSON-RPC eth_call totalSupply()/decimals() for EVM chains with no Blockscout instance (XDC). Priced 1:1 via PTAX (peg=BRL). Offline fixtures keyed `rpc_<contract>_<selector>.json`.
- `known_unmeasured` block in registry.json (→ latest.json → UI panel "Known BRL tokens — not yet publicly measurable"): BRLN (Núclea, permissioned), BRD (CF Inovação, no contract), BRS (Nora, unverified), VRL (SmartPay, unconfirmed), ABRL (no contract), DREX (permissioned CBDC, paused), jBRL (synthetic — excluded from float league), BRLP (Solana/BNB, no supply). All with issuer-primary sources.
- IMPORTANT: the Fintrender report's ticker→issuer table is SCRAMBLED (pairs BRLV w/ AmFi, BRD w/ Liqi, etc). Every issuer/chain fact was re-verified against issuer primary sources, not the report. cREAL is now also branded "BRLm" by Mento (same Celo contract) — that resolves the report's "BRLM".
- Palette extended to --s7 (purple, wBRL) / --s8 (teal, BRLD). Tile chain-count is now dynamic.
- v1.1 candidates surfaced but not added: BRLP BSC leg (0x7ce3...3f36) + Solana leg once a Solana reader exists; BRD Solana SPL (GNzvFdZ...eBZj) pending issuer disambiguation; wBRL Celo/Gnosis/BNB legs via DefiLlama remainder.

## Shipped in v0.4 (Aug 5, 2026) — concentration guardrail + reconciliation
- **Holder-concentration guardrail** (collect.py fetch_concentration): for Blockscout legs, reads top holders, classifies pool (DEX liquidity = circulating) vs wallet/contract, computes non-pool top1/top5 shares (raw values, decimals cancel, clamped ≤100% for proxy/bridged tokens whose live balances exceed reported supply). Flags: dormant (top1≥90% → leg EXCLUDED as treasury/bridge, recorded in row.excluded_legs), concentrated (top1≥25% or top5≥60% → ⚠, treat as upper bound), distributed (● green). Token-level row.distribution = concentration of its largest checked leg.
- **cREAL moved from evm_rpc (forno.celo.org) → Celo Blockscout** (celo.blockscout.com) so it gets supply + concentration automatically (reads "distributed"; Mento now brands it "BRLm", same contract 0xe8537a…).
- **Reconciliation panel** (registry.json `reconciliation` block → latest.json → UI #reconciliation): per token, our circulating float beside CoinGecko live market cap (row.cg_mcap, captured from simple/price include_market_cap — works from Actions) and curated issuer/press figures where there's no CG listing. Every gap explained in-row (circulating vs total supply): BRZ +~$37M dormant treasury (Stellar/Avax/BNB), BRLA CG counts ~60% Polygon vault, wBRL we read 3 of 8 chains (floor), BRLV/BRL1/cREAL match, BRLD/BBRL no CG listing → press reference. Gap <8% renders "match".
- **◌ "distribution not yet verified" badge** in float league for tokens whose concentration we can't check (no public top-holders API: XRPL/BBRL, XDC/BRLD) — honest marker, not silent blank. Non-EVM concentration (#1) is thus transparently labeled rather than faked.
- Offline fixtures added: cREAL celo.blockscout token+holders; CG price fixture carries usd_market_cap for all listed tokens.

## Ops notes (Aug 3, 2026)
- CoinGecko blocks GitHub Actions IPs → pre-launch history lives in data/backfill_coingecko.json (fetched once via browser, weekly grid); collect.py merges it below launch day. backfill.py kept for reference but cannot run in Actions.
- history.json hygiene filter in collect.py drops any pre-launch day carrying per-token "supply" (the v0 smoke-seed shape) — safe to keep permanently.
3. Receita monthly ingestion (per-asset volumes, history to 2019) → replace USD-league share labels with official absolutes.
4. Per-issuer pages: supply/holder history, concentration, peg chart; issuer fee-schedule links (linked, never transcribed).
5. License tracker → BCB register watcher (open-data CSV diff → alert). Oct 30 census report pre-drafted.
6. Weekly brief generator: facts-pack JSON → LLM draft → human edit (never auto-send).

## Strategy context (short)
Launch quietly, let cron accumulate real history, then launch essay ("Crown took #1 in seven months") into the Oct 30 VASP-census news cycle. Audiences: allocators, issuers (Crown/Transfero/Avenia/Braza/MB), chains (XRPL/Base/Celo/Polygon ecosystems — grant candidates), press. Revenue later: sponsorships/grants → paid brief tier → leads; dashboard data itself stays free and complete.
