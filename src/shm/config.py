from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HARD_COST_FLOOR_BPS = 5.0


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatesConfig(StrictModel):
    calendar: Literal["XNYS"]
    dev_start: date
    dev_end: date
    oos_start: date
    oos_end: date | None
    warmup_trading_days: int = Field(ge=1)
    rebalance_every_trading_days: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_periods(self) -> "DatesConfig":
        if not self.dev_start <= self.dev_end < self.oos_start:
            raise ValueError("expected dev_start <= dev_end < oos_start")
        if self.oos_end is not None and self.oos_end < self.oos_start:
            raise ValueError("oos_end must be null or on/after oos_start")
        return self


class SignalConfig(StrictModel):
    name: Literal["xs_momentum_12_1"]
    lookback_trading_days: int = Field(ge=1)
    skip_trading_days: int = Field(ge=0)
    top_n: int = Field(ge=1)
    weighting: Literal["equal"]
    tie_break: Literal["ticker_asc"]

    @model_validator(mode="after")
    def validate_windows(self) -> "SignalConfig":
        if self.skip_trading_days >= self.lookback_trading_days:
            raise ValueError("skip_trading_days must be below lookback_trading_days")
        return self


class EligibilityConfig(StrictModel):
    min_price_usd: float = Field(gt=0)
    min_adv_usd: float = Field(gt=0)
    adv_window_days: int = Field(ge=1)
    require_full_history: bool
    min_eligible_count: int = Field(ge=1)


class TrendFilterConfig(StrictModel):
    enabled: bool
    benchmark: str = Field(min_length=1)
    sma_days: int = Field(ge=1)
    off_exposure: float = Field(ge=0, le=1)


class VolTargetConfig(StrictModel):
    enabled: bool
    window_days: int = Field(ge=2)
    target_annual_vol: float = Field(gt=0)
    max_exposure: float = Field(gt=0, le=1)


class RiskConfig(StrictModel):
    trend_filter: TrendFilterConfig
    vol_target: VolTargetConfig


class ExecutionConfig(StrictModel):
    fill: Literal["next_open"]
    fractional_shares_in_backtest: bool
    cash_yield_annual: float = Field(ge=0)


class ParamsConfig(StrictModel):
    signal: SignalConfig
    eligibility: EligibilityConfig
    risk: RiskConfig
    execution: ExecutionConfig


class PerSideBpsConfig(StrictModel):
    default: float = Field(allow_inf_nan=False)
    stress: float = Field(allow_inf_nan=False)
    floor: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_floor(self) -> "PerSideBpsConfig":
        if self.floor < HARD_COST_FLOOR_BPS:
            raise ValueError(f"cost floor cannot be below {HARD_COST_FLOOR_BPS:g} bps")
        if self.default < self.floor or self.stress < self.floor:
            raise ValueError("default and stress costs must be at or above the floor")
        return self


class CostsConfig(StrictModel):
    model: Literal["fixed_bps_on_notional"]
    per_side_bps: PerSideBpsConfig


class UniverseConfig(StrictModel):
    frozen_on: date
    rule_text: str = Field(min_length=1)
    exclusions: list[str]
    tickers: list[str] = Field(min_length=1)

    @field_validator("rule_text")
    @classmethod
    def validate_rule_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rule_text must not be blank")
        return value

    @field_validator("exclusions", "tickers")
    @classmethod
    def validate_tickers(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value or value != value.strip().upper():
                raise ValueError("tickers must be non-empty uppercase symbols without surrounding spaces")
            if any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for character in value):
                raise ValueError(f"unsupported ticker symbol: {value}")
        if len(values) != len(set(values)):
            raise ValueError("ticker lists must not contain duplicates")
        return values


class ConfigBundle(StrictModel):
    dates: DatesConfig
    params: ParamsConfig
    costs: CostsConfig

    @model_validator(mode="after")
    def validate_cross_file_rules(self) -> "ConfigBundle":
        if self.dates.warmup_trading_days < self.params.signal.lookback_trading_days:
            raise ValueError("warmup_trading_days must cover the signal lookback")
        return self


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def load_config_bundle(config_dir: Path | str) -> ConfigBundle:
    root = Path(config_dir)
    return ConfigBundle.model_validate(
        {
            "dates": _read_yaml(root / "dates.yaml"),
            "params": _read_yaml(root / "params.yaml"),
            "costs": _read_yaml(root / "costs.yaml"),
        }
    )


def load_universe_config(config_dir: Path | str) -> UniverseConfig:
    return UniverseConfig.model_validate(_read_yaml(Path(config_dir) / "universe.yaml"))
