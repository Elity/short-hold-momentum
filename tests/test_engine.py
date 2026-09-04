import pandas as pd
import numpy as np
import pytest

from shm.engine import run_target_weight_backtest, validate_target_weights
from shm.experiments import compute_params_hash
from shm.checks import check_too_good
from shm.report import calculate_metrics


def _prices() -> dict[str, pd.DataFrame]:
    index = pd.bdate_range("2025-01-02", periods=5)
    return {
        "AAPL": pd.DataFrame(
            {"open": [100, 101, 102, 103, 104], "close": [100, 102, 103, 104, 105]}, index=index
        ),
        "NVDA": pd.DataFrame(
            {"open": [50, 51, 52, 53, 54], "close": [50, 52, 53, 54, 55]}, index=index
        ),
    }


def test_trade_executes_next_session_and_cash_stays_nonnegative() -> None:
    prices = _prices()
    signal_date = next(iter(prices.values())).index[0]
    targets = pd.DataFrame({"AAPL": [0.5], "NVDA": [0.5]}, index=[signal_date])
    result = run_target_weight_backtest(prices, targets, cost_bps=10)
    assert (result.transactions["execution_date"] > result.transactions["signal_date"]).all()
    assert result.transactions["execution_date"].min() == next(iter(prices.values())).index[1]
    assert result.cash.min() >= 0
    assert (result.weights.sum(axis=1) <= 1.0 + 1e-9).all()


def test_cost_floor_and_long_only_constraints() -> None:
    prices = _prices()
    signal_date = next(iter(prices.values())).index[0]
    targets = pd.DataFrame({"AAPL": [1.0]}, index=[signal_date])
    with pytest.raises(ValueError, match="at least 5"):
        run_target_weight_backtest(prices, targets, cost_bps=4)
    with pytest.raises(ValueError, match="non-negative"):
        validate_target_weights(pd.DataFrame({"AAPL": [-0.1]}))
    with pytest.raises(ValueError, match="at most 1.0"):
        validate_target_weights(pd.DataFrame({"AAPL": [0.6], "NVDA": [0.5]}))


def test_same_input_is_deterministic() -> None:
    prices = _prices()
    signal_date = next(iter(prices.values())).index[0]
    targets = pd.DataFrame({"AAPL": [0.5], "NVDA": [0.25]}, index=[signal_date])
    first = run_target_weight_backtest(prices, targets, cost_bps=10)
    second = run_target_weight_backtest(prices, targets, cost_bps=10)
    pd.testing.assert_series_equal(first.equity, second.equity)
    pd.testing.assert_frame_equal(first.weights, second.weights)
    pd.testing.assert_frame_equal(first.transactions, second.transactions)


def test_contract_frames_may_store_date_as_a_column() -> None:
    prices = {ticker: frame.rename_axis("date").reset_index() for ticker, frame in _prices().items()}
    signal_date = pd.Timestamp("2025-01-02")
    result = run_target_weight_backtest(
        prices,
        pd.DataFrame({"AAPL": [0.5]}, index=[signal_date]),
        cost_bps=10,
    )
    assert result.equity.index[0] == signal_date


def test_t_plus_one_peeking_strategy_is_flagged_suspect() -> None:
    index = pd.bdate_range("2024-01-02", periods=253)
    next_returns = np.where(np.arange(len(index)) % 2 == 0, 0.02, -0.02)
    opens = np.empty(len(index))
    closes = np.empty(len(index))
    previous_close = 100.0
    for position, daily_return in enumerate(next_returns):
        opens[position] = previous_close
        closes[position] = opens[position] * (1.0 + daily_return)
        previous_close = closes[position]
    prices = {"AAA": pd.DataFrame({"open": opens, "close": closes}, index=index)}
    targets = pd.DataFrame(
        {"AAA": (pd.Series(next_returns, index=index).shift(-1) > 0).astype(float).iloc[:-1]},
        index=index[:-1],
    )
    result = run_target_weight_backtest(prices, targets, cost_bps=5)
    metrics = calculate_metrics(result.equity, daily_weights=result.weights, target_weights=targets)
    assert check_too_good({"malicious_t_plus_one": metrics}).status == "SUSPECT"


def test_same_input_has_same_params_hash_and_metrics() -> None:
    prices = _prices()
    signal_date = next(iter(prices.values())).index[0]
    targets = pd.DataFrame({"AAPL": [0.5], "NVDA": [0.25]}, index=[signal_date])
    params = {
        "signal": {"top_n": 2},
        "eligibility": {},
        "risk": {},
        "execution": {"fill": "next_open"},
    }
    same_params = {
        "execution": {"fill": "next_open"},
        "risk": {},
        "eligibility": {},
        "signal": {"top_n": 2},
    }
    first = run_target_weight_backtest(prices, targets, cost_bps=10)
    second = run_target_weight_backtest(prices, targets, cost_bps=10)
    assert compute_params_hash(params, 10) == compute_params_hash(same_params, 10)
    first_metrics = calculate_metrics(
        first.equity, daily_weights=first.weights, target_weights=targets
    )
    second_metrics = calculate_metrics(
        second.equity, daily_weights=second.weights, target_weights=targets
    )
    assert first_metrics.to_dict() == second_metrics.to_dict()
