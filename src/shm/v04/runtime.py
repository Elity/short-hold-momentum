"""Low-request universe verification and price refresh, separate from decisions."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from shm.data.market_refresh import refresh_market_cache
from shm.universe.sp500 import load_sp500_snapshot, refresh_sp500_universe, sp500_status
from shm.v03.research import write_json


def refresh_constituents(root: Path | str, *, as_of, now=None) -> dict:
    root = Path(root)
    result = refresh_sp500_universe(root, as_of=as_of, now=now)
    status = sp500_status(root, as_of, now=now)
    return {**status, "refresh_status": result.status}


def refresh_sp500_prices(root: Path | str, *, as_of, now=None, **overrides) -> dict:
    root = Path(root)
    settings = yaml.safe_load((root / "config/sp500.yaml").read_text())
    snapshot = load_sp500_snapshot(root)
    symbols = [member["symbol"] for member in snapshot["members"]] if snapshot else []
    held = set()
    legacy_accounts = sorted((root / "paper/accounts").glob("????-??-??.json"))
    if legacy_accounts:
        held.update(json.loads(legacy_accounts[-1].read_text()).get("positions", {}))
    for path in (root / "paper").glob("v0*/*/state.json"):
        for book in json.loads(path.read_text()).get("books", {}).values():
            held.update(book.get("state", {}).get("positions", {}))
    # The preserved V04 still needs its frozen candidate set; use this same
    # throttled queue so its old downloader cannot bypass the provider pause.
    legacy = root / "config/p2_eligible.frozen.yaml"
    if legacy.exists():
        held.update(set(yaml.safe_load(legacy.read_text())["tickers"]) - set(symbols))
    kwargs = {"held_tickers": sorted(held), "daily_budget": settings["daily_provider_call_budget"],
              "min_interval_seconds": settings["min_request_interval_seconds"],
              "history_start": settings["history_start"], "now": now}
    kwargs.update(overrides)
    result = refresh_market_cache(root, symbols, as_of=as_of, **kwargs)
    source = sp500_status(root, as_of, now=now)
    result["universe_status"] = source
    result["allow_new_risk"] = bool(source["allow_new_risk"] and result["complete"])
    write_json(root / "data/market_refresh/latest.json", result)
    return result
