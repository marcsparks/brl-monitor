# BRL Monitor

**Brazil's stablecoin & tokenization economy, measured.** Complete, verifiable, source-linked.

- **Dashboard rule:** only datasets that are 100% complete within a declared perimeter — *complete by construction* (on-chain reads of enumerated contracts, every figure links to a public explorer) or *complete by law* (BCB/Receita/CVM mandatory reporting, linked to official publications). Failed sources render as "—", never an invented value. Estimates live only in Research essays.
- **Stack:** Python stdlib collector (no dependencies) + GitHub Actions cron + static site on GitHub Pages. Running cost: **$0** (+ optional domain).

## Deploy (≈10 minutes, one time)

1. Create a new GitHub repo (public → free unlimited Actions + Pages) and push this folder:
   ```bash
   git init && git add -A && git commit -m "BRL Monitor v0"
   git remote add origin https://github.com/YOURUSER/brl-monitor.git
   git push -u origin main
   ```
2. **Settings → Pages** → Source: *Deploy from a branch* → `main` / root. Your site: `https://YOURUSER.github.io/brl-monitor/`
3. **Actions tab** → enable workflows → run **collect** manually once with input `backfill = yes` (fills ~13 months of history from CoinGecko, then collects live data). It then runs automatically twice a day and commits fresh JSON.
4. (Optional) point a custom domain at Pages in Settings → Pages.

## Run locally

```bash
python3 collector/collect.py            # live fetch (network required)
python3 -m http.server 8000             # open http://localhost:8000
# offline smoke test (no network): python3 tests/make_fixtures.py && python3 collector/collect.py --offline
```

## Repo map

```
config/registry.json    token registry: contracts, APIs, explorer links — edit to add tokens
collector/collect.py    fetch everything → data/latest.json + daily snapshot + history append
collector/backfill.py   one-time CoinGecko history backfill (listed tokens)
data/licenses.json      hand-maintained license tracker (every status must cite a public source)
data/                   latest.json · history.json · snapshots/YYYY-MM-DD.json (committed by CI)
index.html              the site — reads data/*.json client-side, renders league table etc.
.github/workflows/      collect.yml — 2×/day cron + manual trigger
```

## Data sources (all free, all verified Aug 2026)

Blockscout (Base/Polygon/Ethereum — supply, holders, price) · XRPScan (BBRL obligations) · DefiLlama stablecoins (multichain remainders) · CoinGecko (prices, history backfill) · BCB SGS (PTAX/Selic/CDI — official) · DexScreener (BRL DEX pools). Known quirk: BCB's `/ultimos` endpoint can lag a few days (cached); the ref date is displayed with the value, so nothing is misrepresented. Receita monthly per-asset volumes + BCB BoP stablecoin line: v1.1 ingestion targets.

## Editorial rules (the moat — don't break them)

1. Every number: source + timestamp, one click from an official/public origin.
2. Never fill a gap with an estimate. "—" plus an error note beats a plausible guess.
3. Estimates only in Research, always as "two measurements and the gap," methodology shown.
4. License tracker entries must cite a public record; "no public record found" is itself the honest status.
5. This project publishes data. It never touches, routes, or advises on money — that line is what keeps it license-free.

## Roadmap

v1.1: tx-level issuance feed (mint/burn events with tx links) · Receita monthly ingestion · per-issuer pages with holder-concentration history · CVM 88 registry module. Oct 30, 2026: VASP census day — the license tracker becomes a live public census; have the day-one report drafted.
