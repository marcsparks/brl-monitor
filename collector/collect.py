#!/usr/bin/env python3
"""BRL Monitor — collector.

Reads config/registry.json, fetches every source, computes the league table,
writes data/latest.json + a dated snapshot + appends data/history.json.

Design rules (do not violate):
- Every value carries provenance: {source, url, fetched_at}.
- A failed fetch produces null + an entry in `errors` — NEVER a made-up value.
- Dashboard data is complete-by-construction or complete-by-law only.

Usage:
  python collector/collect.py            # live run (needs network)
  python collector/collect.py --offline  # test run against tests/fixtures/
"""
import json, sys, time, datetime, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FIXTURES = ROOT / "tests" / "fixtures"
OFFLINE = "--offline" in sys.argv
UA = {"User-Agent": "brl-monitor/0.1 (public data collector; github)"}

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def get_json(url, retries=3, timeout=25):
    """Fetch JSON with retries. In offline mode, read a fixture keyed by host+path."""
    if OFFLINE:
        key = url.split("//", 1)[1].replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "_")[:120]
        p = FIXTURES / (key + ".json")
        if p.exists():
            return json.loads(p.read_text())
        raise FileNotFoundError(f"no fixture for {url} -> {p.name}")
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise last

def prov(source, url):
    return {"source": source, "url": url, "fetched_at": now_iso()}

# ---------------- fetchers (shapes verified against live responses, Aug 2026) ----------------

def fetch_blockscout(api):
    j = get_json(api)
    dec = int(j.get("decimals") or 18)
    supply = int(j["total_supply"]) / 10**dec
    price = float(j["exchange_rate"]) if j.get("exchange_rate") else None
    holders = int(j["holders_count"]) if j.get("holders_count") else None
    return {"supply": supply, "holders": holders, "price_usd": price}

def fetch_xrpscan(api, currency_hex_prefix):
    j = get_json(api)  # [{"currency": "4242524C...", "value": "41262222.97"}]
    for o in j:
        if o["currency"].startswith(currency_hex_prefix):
            return {"supply": float(o["value"]), "holders": None, "price_usd": None}
    return {"supply": 0.0, "holders": None, "price_usd": None}

def fetch_stellar_expert(api, decimals=7):
    j = get_json(api)
    return {"supply": int(j["supply"]) / 10**decimals,
            "holders": (j.get("trustlines") or {}).get("funded"), "price_usd": None}

def fetch_defillama_symbol(symbol):
    j = get_json("https://stablecoins.llama.fi/stablecoins?includePrices=true")
    for a in j.get("peggedAssets", []):
        if a.get("symbol", "").upper() == symbol.upper():
            circ = a.get("circulating") or {}
            supply = sum(v for v in circ.values() if isinstance(v, (int, float)))
            price = a.get("price")
            return {"supply": supply, "holders": None,
                    "price_usd": float(price) if price else None,
                    "chains": a.get("chainCirculating") and list(a["chainCirculating"].keys())}
    return None

def fetch_coingecko_prices(ids):
    ids = [i for i in ids if i]
    if not ids:
        return {}
    url = ("https://api.coingecko.com/api/v3/simple/price?ids=" + ",".join(ids)
           + "&vs_currencies=usd&include_market_cap=true")
    return get_json(url)

def fetch_sgs(series_id, last_n=5):
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_id}/dados/ultimos/{last_n}?formato=json"
    j = get_json(url)  # [{"data":"27/05/2026","valor":"5.0579"}]
    if not j:
        return None
    last = j[-1]
    d = datetime.datetime.strptime(last["data"], "%d/%m/%Y").date().isoformat()
    return {"value": float(last["valor"]), "ref_date": d}

def _rpc_call(rpc, to, data, timeout=25):
    """Minimal JSON-RPC eth_call (POST). Returns hex string result or raises."""
    if OFFLINE:
        key = "rpc_" + to.lower() + "_" + data
        p = FIXTURES / (key + ".json")
        if p.exists():
            return json.loads(p.read_text())["result"]
        raise FileNotFoundError(f"no rpc fixture for {to} {data}")
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                       "params": [{"to": to, "data": data}, "latest"]}).encode()
    req = urllib.request.Request(rpc, data=body,
                                 headers={**UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode())
    if "error" in j:
        raise ValueError(str(j["error"])[:120])
    return j["result"]

def fetch_evm_rpc(chain):
    """Read an ERC-20 on any EVM chain via JSON-RPC eth_call — no explorer needed.
    Used for chains without a Blockscout instance (e.g. XDC Network).
    totalSupply() = 0x18160ddd, decimals() = 0x313ce567."""
    to = chain["contract"]
    rpc = chain["rpc"]
    sup_hex = _rpc_call(rpc, to, "0x18160ddd")
    supply_raw = int(sup_hex, 16) if sup_hex and sup_hex != "0x" else 0
    try:
        dec = int(_rpc_call(rpc, to, "0x313ce567"), 16)
    except Exception:  # noqa: BLE001
        dec = 18
    return {"supply": supply_raw / 10**dec, "holders": None, "price_usd": None}

def fetch_dexscreener(api):
    j = get_json(api)
    pair = j.get("pair") or (j.get("pairs") or [None])[0]
    if not pair:
        return None
    return {"price_usd": float(pair["priceUsd"]),
            "liquidity_usd": (pair.get("liquidity") or {}).get("usd"),
            "vol24h_usd": (pair.get("volume") or {}).get("h24")}

# ---------------- main ----------------

def main():
    registry = json.loads((ROOT / "config" / "registry.json").read_text())
    out = {"generated_at": now_iso(), "tokens": [], "official": {}, "dex": {}, "errors": [],
           "known_unmeasured": registry.get("known_unmeasured", {})}

    # official series first — PTAX doubles as the 1:1-peg fallback price source
    for s in registry["official_series"]:
        try:
            v = fetch_sgs(s["sgs"])
            out["official"][s["id"]] = {**v, "label": s["label"], **prov("BCB SGS " + str(s["sgs"]), s["api"])}
        except Exception as e:  # noqa: BLE001
            out["errors"].append({"source": s["id"], "error": str(e)})
    ptax = (out["official"].get("ptax_usd_sell") or {}).get("value")

    cg = {}
    try:
        cg = fetch_coingecko_prices([t.get("coingecko_id") for t in registry["tokens"]])
    except Exception as e:  # noqa: BLE001
        out["errors"].append({"source": "coingecko", "error": str(e)})

    for t in registry["tokens"]:
        row = {"symbol": t["symbol"], "name": t["name"], "issuer": t["issuer"],
               "backing": t["backing"], "color": t.get("color", 1),
               "supply": 0.0, "usd": None, "holders": 0, "holders_known": False,
               "chains": [], "provenance": []}
        price = None
        cg_row = cg.get(t.get("coingecko_id") or "", {})
        if cg_row.get("usd"):
            price = float(cg_row["usd"])
            row["provenance"].append(prov("CoinGecko (price)",
                "https://www.coingecko.com/en/coins/" + t["coingecko_id"]))
        seen_defillama = False
        for c in t["chains"]:
            try:
                if c["type"] == "blockscout":
                    r = fetch_blockscout(c["api"])
                elif c["type"] == "xrpscan":
                    r = fetch_xrpscan(c["api"], c["currency_hex_prefix"])
                elif c["type"] == "stellar_expert":
                    r = fetch_stellar_expert(c["api"], c.get("decimals", 7))
                elif c["type"] == "evm_rpc":
                    r = fetch_evm_rpc(c)
                elif c["type"] == "defillama_note":
                    if seen_defillama:
                        continue
                    r = fetch_defillama_symbol(t["defillama_symbol"])
                    seen_defillama = True
                    if r is None:
                        raise ValueError("symbol not found on DefiLlama")
                    # DefiLlama returns TOTAL across chains; subtract chains we already counted directly
                    counted = sum(ch["supply"] for ch in row["chains"])
                    r["supply"] = max(0.0, r["supply"] - counted)
                else:
                    continue
                row["chains"].append({"chain": c["chain"], "supply": round(r["supply"], 2),
                                      "explorer": c["explorer"]})
                row["supply"] += r["supply"]
                if r.get("holders"):
                    row["holders"] += r["holders"]
                    row["holders_known"] = True
                if price is None and r.get("price_usd"):
                    price = r["price_usd"]
                    row["provenance"].append(prov("Explorer exchange_rate (price)", c["explorer"]))
                row["provenance"].append(prov(c["type"], c["api"]))
            except Exception as e:  # noqa: BLE001
                out["errors"].append({"source": f'{t["symbol"]}/{c["chain"]}', "error": str(e)})
        if price is None and t.get("peg") == "BRL" and ptax:
            price = 1.0 / ptax
            row["provenance"].append(prov("1:1 BRL peg x BCB PTAX (no market price source)",
                                          "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados"))
        if not row["chains"]:
            # every supply source for this token failed this run — rule 3:
            # render "—", never a fabricated (or misleading zero) value
            row["supply"] = None
            row["usd"] = None
            row["price_usd"] = price
            row["source_failed"] = True
            out["tokens"].append(row)
            continue
        row["supply"] = round(row["supply"], 2)
        row["price_usd"] = price
        row["usd"] = round(row["supply"] * price, 2) if price else None
        out["tokens"].append(row)

    total = sum(r["usd"] for r in out["tokens"] if r["usd"])
    out["total_onchain_brl_usd"] = round(total, 2)
    for r in out["tokens"]:
        r["share"] = round(100 * r["usd"] / total, 2) if (r["usd"] and total) else None
    out["tokens"].sort(key=lambda r: -(r["usd"] or 0))

    for p in registry["dex_pools"]:
        try:
            v = fetch_dexscreener(p["api"])
            if v:
                # market-depth metric: constant-product approximation — quote-side reserve
                # ≈ liquidity/2; ticket causing ~1% price impact ≈ 1% of quote reserve.
                # Documented on methodology page; an indicative bound, not an execution quote.
                if v.get("liquidity_usd"):
                    v["max_ticket_1pct_usd"] = round(0.01 * v["liquidity_usd"] / 2, 0)
                out["dex"][p["id"]] = {**v, "label": p["label"], **prov("DexScreener", p["page"])}
        except Exception as e:  # noqa: BLE001
            out["errors"].append({"source": p["id"], "error": str(e)})

    # history append + issuance deltas
    today = datetime.date.today().isoformat()
    hist_path = DATA / "history.json"
    hist = json.loads(hist_path.read_text()) if hist_path.exists() else {"days": []}
    # data hygiene: v0 shipped 2 pre-launch smoke-seed days (fixture values, not
    # collected data). Drop any pre-launch day carrying per-token "supply" —
    # real pre-launch rows come only from the CoinGecko backfill, which writes
    # "usd" alone. Launch day = 2026-08-03 (first live collector run).
    hist["days"] = [d for d in hist["days"] if d["date"] >= "2026-08-03"
                    or not any("supply" in (v or {}) for v in (d.get("tokens") or {}).values())]
    # pre-launch backfill: merge data/backfill_coingecko.json (weekly CoinGecko
    # market-cap points, usd only, provenance in that file) for dates BEFORE
    # launch day — live on-chain days always win and are never overwritten
    bf_path = DATA / "backfill_coingecko.json"
    if bf_path.exists():
        bf = json.loads(bf_path.read_text())
        by_date = {d["date"]: d for d in hist["days"]}
        for sym, series in (bf.get("series") or {}).items():
            for d, usd in series:
                # snap to the week's Monday so all tokens share a weekly grid —
                # each value is a real CoinGecko reading from that week (weekly
                # granularity is declared in the note; no interpolation)
                dt = datetime.date.fromisoformat(d)
                monday = (dt - datetime.timedelta(days=dt.weekday())).isoformat()
                if monday >= "2026-08-03":
                    continue
                row = by_date.setdefault(monday, {"date": monday, "total_usd": None, "tokens": {}})
                if "supply" in ((row["tokens"] or {}).get(sym) or {}):
                    continue  # never overwrite a live on-chain day
                row["tokens"][sym] = {"usd": usd}
        for row in by_date.values():
            if row["date"] < "2026-08-03":
                vals = [v.get("usd") for v in row["tokens"].values() if v.get("usd")]
                row["total_usd"] = round(sum(vals), 2) if vals else None
        hist["days"] = sorted(by_date.values(), key=lambda d: d["date"])
        hist["backfill_note"] = bf.get("_note")
    day_row = {"date": today, "total_usd": out["total_onchain_brl_usd"],
               "tokens": {r["symbol"]: {"usd": r["usd"], "supply": r["supply"]} for r in out["tokens"]}}
    hist["days"] = [d for d in hist["days"] if d["date"] != today] + [day_row]
    hist["days"].sort(key=lambda d: d["date"])
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    hist_path.write_text(json.dumps(hist, indent=1))

    def delta(sym, days):
        past = [d for d in hist["days"]
                if d["date"] <= (datetime.date.today() - datetime.timedelta(days=days)).isoformat()]
        if not past:
            return None
        old = past[-1]["tokens"].get(sym, {}).get("supply")
        new = day_row["tokens"].get(sym, {}).get("supply")
        return round(new - old, 2) if (old is not None and new is not None) else None

    for r in out["tokens"]:
        r["net_issuance_7d"] = delta(r["symbol"], 7)
        r["net_issuance_30d"] = delta(r["symbol"], 30)

    (DATA / "snapshots").mkdir(parents=True, exist_ok=True)
    (DATA / "snapshots" / f"{today}.json").write_text(json.dumps(out, indent=1))
    (DATA / "latest.json").write_text(json.dumps(out, indent=1))
    ok = len(out["tokens"]) - len([e for e in out["errors"] if "/" in e["source"]])
    print(f"OK: {len(out['tokens'])} tokens, total ${out['total_onchain_brl_usd']:,.0f}, "
          f"{len(out['errors'])} source errors -> data/latest.json")
    return 0

if __name__ == "__main__":
    sys.exit(main())
