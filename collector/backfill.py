#!/usr/bin/env python3
"""One-time history backfill from CoinGecko market-cap history (daily, ~13 months).

Fills data/history.json with {date, tokens:{SYM:{usd}}} rows for listed tokens.
Supply-level history for unlisted tokens (BBRL) accumulates from daily snapshots.
Run once (in GitHub Actions or locally): python collector/backfill.py
"""
import json, pathlib, datetime, time
from collect import get_json  # reuse fetch + offline mode

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

def main():
    registry = json.loads((ROOT / "config" / "registry.json").read_text())
    hist_path = DATA / "history.json"
    hist = json.loads(hist_path.read_text()) if hist_path.exists() else {"days": []}
    by_date = {d["date"]: d for d in hist["days"]}

    for t in registry["tokens"]:
        cg = t.get("coingecko_id")
        if not cg:
            continue
        url = f"https://api.coingecko.com/api/v3/coins/{cg}/market_chart?vs_currency=usd&days=400&interval=daily"
        try:
            j = get_json(url)
        except Exception as e:  # noqa: BLE001
            print(f"skip {t['symbol']}: {e}")
            continue
        for ts, mcap in j.get("market_caps", []):
            if not mcap:
                continue
            date = datetime.datetime.fromtimestamp(ts / 1000, datetime.timezone.utc).date().isoformat()
            row = by_date.setdefault(date, {"date": date, "total_usd": None, "tokens": {}})
            row["tokens"].setdefault(t["symbol"], {})["usd"] = round(mcap, 2)
        time.sleep(2)  # CoinGecko free-tier rate limit
        print(f"backfilled {t['symbol']}")

    for row in by_date.values():
        vals = [v.get("usd") for v in row["tokens"].values() if v.get("usd")]
        row["total_usd"] = round(sum(vals), 2) if vals else row.get("total_usd")
    hist["days"] = sorted(by_date.values(), key=lambda d: d["date"])
    hist["backfill_note"] = ("Pre-launch history via CoinGecko market-cap series (listed tokens only); "
                             "from launch day, values come from direct on-chain reads.")
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    hist_path.write_text(json.dumps(hist, indent=1))
    print(f"history: {len(hist['days'])} days")

if __name__ == "__main__":
    main()
