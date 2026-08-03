#!/usr/bin/env python3
"""BRL Monitor — volumes event-scan (v0.2).

Scans token-transfer events per EVM chain via Blockscout, decomposes into
mint / burn / transfer, aggregates daily USD volumes into data/volumes.json,
and captures large events (>= EVENT_MIN_USD) with tx hashes for the feed.

Honesty rules:
- Coverage is per-chain and declared: tokens whose supply partly lives on
  chains we don't scan yet (Solana, XRPL, Celo/Gnosis) get coverage="partial".
- XRPL (BBRL) volume is NOT scanned yet (v0.2.1) — BBRL gets coverage="none"
  and the UI must show its third-party anchor instead. Never a guessed number.

Usage: python collector/volumes.py [--offline] [--backfill-days N]
Run AFTER collect.py (uses data/latest.json for prices).
"""
import json, os, sys, datetime, pathlib
from collect import get_json, now_iso, OFFLINE  # noqa: F401  (shared fetch + offline mode)

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PAGE_CAP = int(os.environ.get("VOLUMES_PAGE_CAP") or 40)  # pages/chain/run (rate-limit + Actions guard)
EVENT_MIN_USD = 100_000
BACKFILL_DAYS = 90
EXPLICIT_BACKFILL = "--backfill-days" in sys.argv
if EXPLICIT_BACKFILL:
    BACKFILL_DAYS = int(sys.argv[sys.argv.index("--backfill-days") + 1])

ZERO = {"0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead"}

def classify(item):
    t = item.get("type", "")
    if t == "token_minting" or (item.get("from") or {}).get("hash", "").lower() in ZERO:
        return "mint"
    if t == "token_burning" or (item.get("to") or {}).get("hash", "").lower() in ZERO:
        return "burn"
    return "transfer"

def scan_chain(api_base, price_usd, since_date, sym, chain, events):
    """Walk transfer pages newest→oldest until since_date or PAGE_CAP."""
    daily = {}
    url = api_base + "/transfers"
    pages = 0
    capped = False
    while url and pages < PAGE_CAP:
        j = get_json(url)
        pages += 1
        for it in j.get("items", []):
            ts = it.get("timestamp", "")[:10]
            if not ts:
                continue
            if ts < since_date:
                url = None
                break
            dec = int((it.get("total") or {}).get("decimals") or 18)
            amt = int((it.get("total") or {}).get("value") or 0) / 10**dec
            usd = amt * price_usd if price_usd else 0.0
            kind = classify(it)
            d = daily.setdefault(ts, {"mint": 0.0, "burn": 0.0, "transfer": 0.0, "count": 0})
            d[kind] += usd
            d["count"] += 1
            if usd >= EVENT_MIN_USD:
                events.append({"date": ts, "symbol": sym, "chain": chain, "kind": kind,
                               "usd": round(usd, 0), "tx": it.get("transaction_hash")})
        else:
            npp = j.get("next_page_params")
            if npp and url:
                url = api_base + "/transfers?" + "&".join(f"{k}={v}" for k, v in npp.items())
            else:
                url = None
            continue
        break
    if pages >= PAGE_CAP:
        capped = True
    return daily, capped

def main():
    registry = json.loads((ROOT / "config" / "registry.json").read_text())
    latest = json.loads((DATA / "latest.json").read_text()) if (DATA / "latest.json").exists() else {"tokens": []}
    prices = {t["symbol"]: t.get("price_usd") for t in latest.get("tokens", [])}

    vpath = DATA / "volumes.json"
    vol = json.loads(vpath.read_text()) if vpath.exists() else {"daily": {}, "events": [], "meta": {}}
    today = datetime.date.today()
    # incremental: rescan last 3 days (finality/lag); first run OR explicit
    # --backfill-days: scan back BACKFILL_DAYS (re-scanned days are overwritten
    # per chain, so a deep re-backfill is idempotent and only ever adds depth)
    have_any = bool(vol["daily"])
    deep = (not have_any) or EXPLICIT_BACKFILL
    since = (today - datetime.timedelta(days=BACKFILL_DAYS if deep else 3)).isoformat()

    events = []
    errors = []
    for t in registry["tokens"]:
        sym = t["symbol"]
        evm_chains = [c for c in t["chains"] if c["type"] == "blockscout"]
        all_chains = len(t["chains"])
        if not evm_chains:
            vol["meta"][sym] = {"coverage": "none",
                                "note": "no EVM chains scanned yet (XRPL/DefiLlama-sourced) — use third-party anchor, never a guess"}
            continue
        tok_daily = vol["daily"].setdefault(sym, {})
        capped_any = False
        prev_since = ((vol["meta"].get(sym) or {}).get("chain_since") or {})
        chain_since = dict(prev_since)
        for c in evm_chains:
            api_base = c["api"]  # .../api/v2/tokens/0x...
            try:
                daily, capped = scan_chain(api_base, prices.get(sym), since, sym, c["chain"], events)
                capped_any = capped_any or capped
                # per-chain storage; rescan window days are overwritten per chain (idempotent)
                for d, v in daily.items():
                    w = tok_daily.setdefault(d, {"mint": 0.0, "burn": 0.0, "transfer": 0.0, "count": 0, "_chains": {}})
                    w.setdefault("_chains", {})[c["chain"]] = {
                        "mint": round(v["mint"], 2), "burn": round(v["burn"], 2),
                        "transfer": round(v["transfer"], 2), "count": v["count"]}
                # honest scan-start: earliest COMPLETE day for this chain.
                # If the page cap cut the walk mid-day, that earliest day is
                # partial — the first complete day is the next one.
                if daily:
                    start = min(daily)
                    if capped:
                        start = (datetime.date.fromisoformat(start) + datetime.timedelta(days=1)).isoformat()
                    if c["chain"] not in chain_since or start < chain_since[c["chain"]]:
                        chain_since[c["chain"]] = start
            except Exception as e:  # noqa: BLE001
                errors.append({"source": f"{sym}/{c['chain']}", "error": str(e)})
        # roll per-chain window data up into day totals
        for d, w in tok_daily.items():
            ch = w.get("_chains")
            if ch:
                for k in ("mint", "burn", "transfer"):
                    w[k] = round(sum(x[k] for x in ch.values()), 2)
                w["count"] = sum(x["count"] for x in ch.values())
        # token-level complete-window start = the LATEST of its chains' starts
        # (before that date at least one scanned chain has no complete data)
        scan_since = max(chain_since.values()) if chain_since else None
        vol["meta"][sym] = {
            "coverage": "full" if len(evm_chains) == all_chains else "partial",
            "chains_scanned": [c["chain"] for c in evm_chains],
            "page_capped": capped_any,
            "chain_since": chain_since,
            "scan_since": scan_since,
            "note": None if len(evm_chains) == all_chains else
                    "EVM chains only — non-EVM legs not yet scanned; totals are a floor, labeled",
        }

    # merge new large events, dedupe by tx, keep newest 60
    seen = {e.get("tx") for e in vol["events"]}
    vol["events"] = (sorted([e for e in events if e.get("tx") not in seen] + vol["events"],
                            key=lambda e: e["date"], reverse=True))[:60]
    vol["generated_at"] = now_iso()
    vol["errors"] = errors
    vol["method"] = ("Blockscout token-transfer pages per contract; type=token_minting/burning or zero-address "
                     f"=> mint/burn, else transfer; USD at current price; events >= ${EVENT_MIN_USD:,}; "
                     f"page cap {PAGE_CAP}/chain/run; incremental 3-day rescan window.")
    vpath.write_text(json.dumps(vol, indent=1))
    ndays = sum(len(v) for v in vol["daily"].values())
    print(f"OK volumes: {len(vol['daily'])} tokens, {ndays} token-days, {len(vol['events'])} events, {len(errors)} errors")

if __name__ == "__main__":
    main()
