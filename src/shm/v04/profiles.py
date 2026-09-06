from dataclasses import asdict
from pathlib import Path

from shm.v03.strategy import CANDIDATES


SP500_IDS = tuple(f"S500-{key}" for key in CANDIDATES)
STRATEGY_IDS = (*CANDIDATES, *SP500_IDS)


def base_candidate(strategy_id: str) -> str:
    if strategy_id not in STRATEGY_IDS:
        raise ValueError(f"unknown strategy: {strategy_id}")
    return strategy_id.removeprefix("S500-")


def version(strategy_id: str) -> str:
    base_candidate(strategy_id)
    return "0.4" if strategy_id.startswith("S500-") else "0.3"


def family(strategy_id: str) -> str:
    return "v04" if version(strategy_id) == "0.4" else "v03"


def candidate_config(strategy_id: str) -> dict:
    config = asdict(CANDIDATES[base_candidate(strategy_id)])
    if version(strategy_id) == "0.3":
        return config
    return {"spec_version": "0.4", "base_candidate": config,
            "universe_policy": "verified_current_sp500", "max_source_age_sessions": 1}


def account_directory(root: Path, strategy_id: str) -> Path:
    return root / "paper" / family(strategy_id) / strategy_id
