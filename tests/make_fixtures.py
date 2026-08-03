#!/usr/bin/env python3
"""Generate offline test fixtures matching collector's fixture-key scheme.
Values mirror real API reads captured Aug 3, 2026 (Blockscout/XRPScan/Stellar/BCB verified live)."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "collector"))

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
FIX.mkdir(parents=True, exist_ok=True)

def key(url):
    return url.split("//", 1)[1].replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "_")[:120]

def w(url, obj):
    (FIX / (key(url) + ".json")).write_text(json.dumps(obj))

reg = json.loads((ROOT / "config" / "registry.json").read_text())

def bs(supply_wei, dec, holders, rate):
    return {"decimals": str(dec), "total_supply": supply_wei, "holders_count": str(holders),
            "exchange_rate": rate, "type": "ERC-20"}

# Real captured values (Jul 31–Aug 3, 2026)
w("https://base.blockscout.com/api/v2/tokens/0xd2047ebdb205Ee6862b69ae9fB3501652cC97d36",
  bs("390672791322829905157127293", 18, 95, "0.195179"))
w("https://polygon.blockscout.com/api/v2/tokens/0x4eD141110F6EeeAbA9A1df36d8c26f684d2475Dc",
  bs(str(51_080_000 * 10**4), 4, 5086, "0.1957"))
w("https://eth.blockscout.com/api/v2/tokens/0x01d33FD36ec67c6ada32cf36b31e88ee190b1839",
  bs(str(14_000_000 * 10**18), 18, 306, "0.1957"))
w("https://base.blockscout.com/api/v2/tokens/0xE9185Ee218cae427aF7B9764A011bb89FeA761B4",
  bs(str(9_070_000 * 10**18), 18, 1168, "0.1957"))
w("https://api.stellar.expert/explorer/public/asset/BRZ-GABMA6FPH3OJXNTGWO7PROF7I5WPQUZOB4BLTBTP4FK6QV7HWISLIEO2",
  {"supply": "20000000000000000", "trustlines": {"total": 84, "authorized": 84, "funded": 8}, "decimals": 7})
w("https://polygon.blockscout.com/api/v2/tokens/0xE6A537a407488807F0bbeb0038B79004f19DDDFb",
  bs(str(19_240_000 * 10**18), 18, 19177, "0.196"))
w("https://api.xrpscan.com/api/v1/account/rH5CJsqvNqZGxrMyGaqLEoMWRYcVTAPZMt/obligations",
  [{"currency": "4242524C00000000000000000000000000000000", "value": "41262222.97639076"}])
w("https://polygon.blockscout.com/api/v2/tokens/0x5c067c80c00ecd2345b05e83a3e758ef799c40b5",
  bs(str(12_950_000 * 10**18), 18, 260, "0.1957"))
w("https://stablecoins.llama.fi/stablecoins?includePrices=true",
  {"peggedAssets": [
      {"symbol": "BRLA", "price": 0.196, "circulating": {"peggedVAR": 136_750_000},
       "chainCirculating": {"Celo": {}, "Polygon": {}, "Gnosis": {}}},
      {"symbol": "CREAL", "price": 0.1957, "circulating": {"peggedVAR": 2_050_000},
       "chainCirculating": {"Celo": {}}}]})

ids = ",".join([t["coingecko_id"] for t in reg["tokens"] if t.get("coingecko_id")])
w(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_market_cap=true",
  {"crown-brlv": {"usd": 0.195179}, "brz": {"usd": 0.1957}, "brla-digital-brla": {"usd": 0.196},
   "brl1": {"usd": 0.1957}, "celo-real-creal": {"usd": 0.1957}})

for sid, val, date in [(1, "5.0579", "27/05/2026"), (432, "14.25", "18/06/2026"), (12, "0.052531", "31/07/2026")]:
    w(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{sid}/dados/ultimos/5?formato=json",
      [{"data": date, "valor": val}])

for pool, price, liq, vol in [("0x4Af62a93775C093Af3e32949EF23C9a323d20817", "0.1913", 65833.09, 108382.92),
                              ("0x0E7754127dEDd4097be750825Dbb4669bc32c956", "0.1960", 116000.0, 53000.0)]:
    w(f"https://api.dexscreener.com/latest/dex/pairs/polygon/{pool}",
      {"pair": {"priceUsd": price, "liquidity": {"usd": liq}, "volume": {"h24": vol}}})

print(f"fixtures written: {len(list(FIX.glob('*.json')))}")
