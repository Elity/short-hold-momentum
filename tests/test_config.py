from pathlib import Path

import pytest
from pydantic import ValidationError

from shm.config import ConfigBundle, CostsConfig, UniverseConfig, load_config_bundle


ROOT = Path(__file__).resolve().parents[1]


def test_default_configs_validate() -> None:
    bundle = load_config_bundle(ROOT / "config")
    assert isinstance(bundle, ConfigBundle)
    assert bundle.dates.rebalance_every_trading_days == 20
    assert bundle.costs.per_side_bps.default == 10


def test_hard_cost_floor_cannot_be_lowered() -> None:
    with pytest.raises(ValidationError, match="cost floor cannot be below 5 bps"):
        CostsConfig.model_validate(
            {
                "model": "fixed_bps_on_notional",
                "per_side_bps": {"default": 10, "stress": 25, "floor": 4},
            }
        )


def test_non_finite_cost_is_rejected() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        CostsConfig.model_validate(
            {
                "model": "fixed_bps_on_notional",
                "per_side_bps": {"default": float("nan"), "stress": 25, "floor": 5},
            }
        )


def test_owner_universe_must_be_nonempty_and_unique() -> None:
    with pytest.raises(ValidationError):
        UniverseConfig.model_validate(
            {
                "frozen_on": "2026-09-04",
                "rule_text": "Large liquid US stocks selected by the owner.",
                "exclusions": ["MSFT"],
                "tickers": [],
            }
        )

    with pytest.raises(ValidationError, match="must not contain duplicates"):
        UniverseConfig.model_validate(
            {
                "frozen_on": "2026-09-04",
                "rule_text": "Large liquid US stocks selected by the owner.",
                "exclusions": ["MSFT"],
                "tickers": ["AAPL", "AAPL"],
            }
        )
