import json

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

from shm.v03.engine import advance_open, run_simulation, sync_price_basis
from shm.v03.strategy import Decision, PortfolioState, PositionState, evaluate_close, prepare_inputs


@pytest.fixture
def market():
    dates = xcals.get_calendar("XNYS", start="2023-01-01", end="2025-01-01").sessions[:330].tz_localize(None)
    universe = [f"S{i:02d}" for i in range(32)]
    prices = {}
    for number, ticker in enumerate([*universe, "SPY"]):
        close = 50 + np.arange(len(dates)) * (0.025 + number * 0.001)
        prices[ticker] = pd.DataFrame({"open": close, "close": close, "high": close + 1,
                                       "low": close - 1, "volume": 1_000_000.0}, index=dates)
    return prices, universe, dates


def prepared(market, rebalance=None):
    prices, universe, dates = market
    return prepare_inputs(prices, universe, dates, rebalance if rebalance is not None else dates[[259, 279, 299, 319]])


def held(ticker, dates, price=100, quantity=100, stop=None):
    return PortfolioState(cash=0, positions={ticker: PositionState(quantity, price, str(dates[250].date()), price, stop)},
                          equity_high_water=price * quantity, marks={ticker: price})


def test_asof_260_session_eligibility_and_future_truncation(market):
    prices, names, dates = market
    ipo = names[-1]
    prices[ipo] = prices[ipo].loc[dates[10]:]
    full = prepared(market)
    column = full.ticker_index[ipo]
    assert not full.eligible[full.row(dates[268]), column]
    assert full.eligible[full.row(dates[269]), column]
    truncated_prices = {t: f.loc[:dates[279]] for t, f in prices.items()}
    truncated = prepare_inputs(truncated_prices, names, dates[:280], dates[[259, 279]])
    left = evaluate_close(full, dates[279], "C3", PortfolioState())
    right = evaluate_close(truncated, dates[279], "C3", PortfolioState())
    assert left.to_dict() == right.to_dict()
    # A future bad quote cannot globally quarantine a previously eligible name.
    prices[names[0]].loc[dates[300], "close"] = np.nan
    changed = prepared(market)
    assert changed.eligible[changed.row(dates[279]), changed.ticker_index[names[0]]]


def test_point_in_time_eligibility_survives_future_split_price_scaling(market):
    prices, names, dates = market
    for frame in prices.values():
        frame["as_traded_close"] = frame["close"]
        frame["dollar_volume"] = frame["close"] * frame["volume"]
    original = prepare_inputs(prices, names, dates, dates[[259]], require_point_in_time_eligibility=True)
    scaled = {ticker: frame.copy() for ticker, frame in prices.items()}
    for frame in scaled.values():
        frame[["open", "high", "low", "close"]] /= 20
        frame["volume"] *= 20
    adjusted = prepare_inputs(scaled, names, dates, dates[[259]], require_point_in_time_eligibility=True)
    assert np.allclose(original.returns, adjusted.returns, equal_nan=True)
    assert np.array_equal(original.eligible, adjusted.eligible)
    decision = evaluate_close(adjusted, dates[259], "C1", PortfolioState())
    assert decision.eligible_count == len(names)
    assert decision.diagnostics["eligibility_data_known_count"] == len(names)
    assert decision.diagnostics["eligibility_data_unknown_count"] == 0


def test_strict_eligibility_never_substitutes_adjusted_prices_for_missing_raw_data(market):
    prices, names, dates = market
    strict = prepare_inputs(prices, names, dates, dates[[259]], require_point_in_time_eligibility=True)
    assert not strict.eligible[strict.row(dates[259])].any()
    assert prepared(market).eligible[strict.row(dates[259])].any()  # Existing callers remain compatible.
    for frame in prices.values():
        frame["as_traded_close"] = frame["close"]
        frame["dollar_volume"] = frame["close"] * frame["volume"]
    prices[names[0]].drop(columns="as_traded_close", inplace=True)
    prices[names[1]].loc[dates[250], "dollar_volume"] = 0
    prices[names[1]].loc[dates[250], "volume"] = 0
    prices[names[2]].loc[dates[259], "as_traded_close"] = -1
    strict = prepare_inputs(prices, names, dates, dates[[259]], require_point_in_time_eligibility=True)
    decision = evaluate_close(strict, dates[259], "C1", PortfolioState())
    assert strict.eligible[strict.row(dates[259]), strict.ticker_index[names[1]]]
    assert decision.eligible_count == len(names) - 2
    assert decision.diagnostics["eligibility_data_unknown_count"] == 2
    assert decision.allow_new_risk
    prices[names[3]]["as_traded_close"] = 4.0
    preferred = prepared(market)
    assert not preferred.eligible[preferred.row(dates[259]), preferred.ticker_index[names[3]]]


@pytest.mark.parametrize("integer_shares", [False, True])
def test_next_open_costs_gaps_and_no_ordinary_day_buys(market, integer_shares):
    prices, names, dates = market
    data = prepared(market)
    state = PortfolioState()
    decision = evaluate_close(data, dates[259], "C1", state)
    ticker = decision.selected[0]
    assert not state.positions
    # A quote changes at the next open, never at the prior decision's close.
    prices[ticker].loc[dates[260], "open"] = 90.0
    data = prepared(market)
    execution = advance_open(data, dates[260], state, cost_bps=10, integer_shares=integer_shares)
    trade = next(t for t in execution.transactions if t["ticker"] == ticker)
    assert trade["price"] == 90
    assert trade["signal_date"] == str(dates[259].date())
    assert trade["execution_date"] == str(dates[260].date())
    assert execution.cost > 0 and state.cash >= 0
    if integer_shares:
        assert all(p.quantity.is_integer() for p in state.positions.values())
    evaluate_close(data, dates[260], "C1", state)
    shares = state.shares.copy()
    assert not advance_open(data, dates[261], state, cost_bps=10, integer_shares=integer_shares).transactions
    assert state.shares == shares
    assert not advance_open(data, dates[261], state, cost_bps=10).transactions


def test_market_exit_and_ten_percent_warning_are_distinct(market):
    prices, names, dates = market
    prices["SPY"].loc[dates[270], "close"] = 40
    data = prepared(market)
    state = held(names[0], dates)
    c0 = evaluate_close(data, dates[270], "C0", state)
    assert "DRAWDOWN_10_PERCENT_REVIEW" in c0.warnings
    assert not c0.exits
    c1 = evaluate_close(data, dates[270], "C1", held(names[0], dates))
    assert c1.exits == {names[0]: "market_trend_exit"}
    assert not c1.allow_new_risk


def test_atr_is_simple_mean_monotone_and_keeps_state_on_rebalance(market):
    prices, names, dates = market
    ticker = names[-1]
    prices[ticker].loc[dates[259], "high"] += 10
    data = prepared(market)
    column, row = data.ticker_index[ticker], data.row(dates[259])
    assert data.atr20[row, column] == pytest.approx((19 * 2 + 12) / 20)
    close = data.closes[row, column]
    state = held(ticker, dates, price=close, quantity=5, stop=close - 2)
    state.cash = 100_000
    decision = evaluate_close(data, dates[259], "C3", state)
    assert state.positions[ticker].trailing_stop == close - 2
    peak, stop, entry = state.positions[ticker].peak_close, state.positions[ticker].trailing_stop, state.positions[ticker].entry_date
    advance_open(data, dates[260], state, cost_bps=10)
    assert state.positions[ticker].entry_date == entry
    assert state.positions[ticker].peak_close == peak
    assert state.positions[ticker].trailing_stop == stop
    assert ticker in decision.selected
    prices[ticker].loc[dates[261], ["close", "low"]] = close - 4
    data = prepared(market)
    evaluate_close(data, dates[261], "C3", state)
    assert state.positions[ticker].trailing_stop >= stop
    assert state.pending.exits[ticker] == "atr_trailing_exit"


def test_existing_atr_stop_exits_during_successor_warmup_and_keeps_new_risk_blocked(market):
    prices, names, dates = market
    ticker = names[0]
    prices[ticker] = prices[ticker].loc[dates[250]:].copy()
    prices[ticker].loc[dates[260], ["open", "high", "low", "close"]] = [40.0, 41.0, 39.0, 40.0]
    data = prepared(market)
    close = float(prices[ticker].loc[dates[259], "close"])
    state = held(ticker, dates, price=close + 3, quantity=5, stop=close + 1)
    state.cash = 100_000

    decision = evaluate_close(data, dates[259], "C3", state)
    assert f"MISSING_ATR20:{ticker}" in decision.warnings
    assert not decision.allow_new_risk and decision.target_weights is None
    assert decision.exits[ticker] == "atr_trailing_exit"
    assert state.positions[ticker].trailing_stop == close + 1
    execution = advance_open(data, dates[260], state, cost_bps=10)
    assert ticker not in state.positions
    assert len(execution.transactions) == 1
    assert execution.transactions[0]["price"] == 40.0
    assert execution.transactions[0]["reason"] == "atr_trailing_exit"


def test_missing_open_keeps_exit_pending_without_fictional_fill(market):
    prices, names, dates = market
    ticker = names[0]
    prices["SPY"].loc[dates[270], "close"] = 40
    prices[ticker].loc[dates[271], "open"] = np.nan
    prices[ticker].loc[dates[272], "open"] = 42
    data = prepared(market)
    state = held(ticker, dates)
    evaluate_close(data, dates[270], "C1", state)
    first = advance_open(data, dates[271], state, cost_bps=10)
    assert not first.transactions and state.shares[ticker] == 100
    assert ticker in state.blocked_exits
    evaluate_close(data, dates[271], "C1", state)
    final = advance_open(data, dates[272], state, cost_bps=10)
    assert final.transactions[0]["price"] == 42
    assert final.transactions[0]["signal_date"] == str(dates[270].date())
    assert not state.positions and not state.blocked_exits


def test_missing_entry_is_not_retried_or_redistributed(market):
    prices, names, dates = market
    data = prepared(market)
    state = PortfolioState()
    signal = evaluate_close(data, dates[259], "C1", state)
    ticker = signal.selected[0]
    prices[ticker].loc[dates[260], "open"] = np.nan
    data = prepared(market)
    execution = advance_open(data, dates[260], state, cost_bps=10)
    assert any(e["action"] == "unfilled_entry" and e["ticker"] == ticker for e in execution.events)
    assert ticker not in state.positions and state.cash > 6000
    evaluate_close(data, dates[260], "C1", state)
    assert not advance_open(data, dates[261], state, cost_bps=10).transactions


def test_missing_regular_rebalance_sale_remains_pending(market):
    prices, names, dates = market
    ticker = names[0]
    prices[ticker].loc[dates[271], "open"] = np.nan
    data = prepared(market)
    state = held(ticker, dates)
    state.pending = Decision(str(dates[270].date()), str(dates[271].date()), "rebalance", {},
                             diagnostics={"allow_new_risk": True})
    first = advance_open(data, dates[271], state, cost_bps=10)
    assert not first.transactions
    assert state.blocked_exits[ticker]["reason"] == "rebalance_removal"
    evaluate_close(data, dates[271], "C0", state)
    final = advance_open(data, dates[272], state, cost_bps=10)
    assert final.transactions[0]["event_type"] == "rebalance"
    assert final.transactions[0]["quantity"] == 100
    assert not state.positions


def test_missed_open_never_backfills_a_buy_and_missing_spy_blocks_new_risk(market):
    prices, names, dates = market
    data = prepared(market)
    state = PortfolioState()
    evaluate_close(data, dates[259], "C1", state)
    execution = advance_open(data, dates[261], state, cost_bps=10)
    assert not execution.transactions and not state.positions
    assert any(e["action"] == "missed_execution" for e in execution.events)
    prices["SPY"].loc[dates[260], "open"] = np.nan
    data = prepared(market)
    state = PortfolioState()
    evaluate_close(data, dates[259], "C1", state)
    execution = advance_open(data, dates[260], state, cost_bps=10)
    assert not execution.transactions and not state.positions
    assert any(e["action"] == "incomplete_open_valuation" for e in execution.events)


def test_sma_exit_wins_rebalance_and_preserves_vacant_allocation(market):
    prices, names, dates = market
    ticker = names[-1]
    # Momentum ends 21 sessions back, so the newly weak name remains highly ranked.
    prices[ticker].loc[dates[259], "close"] = 55
    prices[ticker].loc[dates[259], "low"] = 54
    data = prepared(market)
    state = held(ticker, dates, price=60)
    decision = evaluate_close(data, dates[259], "C2", state)
    assert ticker in decision.selected
    assert decision.exits[ticker] == "sma50_exit"
    assert decision.target_weights[ticker] == 0
    assert sum(w > 0 for w in decision.target_weights.values()) == 14
    assert max(decision.target_weights.values()) == pytest.approx(decision.diagnostics["raw_exposure"] / 15)


def test_small_pool_blocks_entries_but_not_risk_and_pit_membership(market):
    prices, names, dates = market
    data = prepare_inputs(prices, names, dates, dates[[259]], membership_by_session={dates[259]: names[:29]})
    state = PortfolioState()
    decision = evaluate_close(data, dates[259], "C1", state)
    assert decision.eligible_count == 29 and not decision.allow_new_risk
    assert decision.target_weights is None
    assert "INSUFFICIENT_ELIGIBLE_UNIVERSE" in decision.warnings
    prices["SPY"].loc[dates[259], "close"] = 40
    data = prepare_inputs(prices, names[:29], dates, dates[[259]])
    decision = evaluate_close(data, dates[259], "C1", held(names[0], dates))
    assert decision.exits[names[0]] == "market_trend_exit"


def test_removed_constituent_keeps_quotes_for_risk_exit_but_cannot_be_rebought(market):
    prices, names, dates = market
    removed = names[-1]
    universe = names[:-1]
    prices["SPY"].loc[dates[270], "close"] = 40
    data = prepare_inputs(prices, universe, dates, dates[[259, 279]])
    state = held(removed, dates, price=60)
    decision = evaluate_close(data, dates[270], "C1", state)
    assert removed in data.ticker_index and removed not in data.universe
    assert not any(w.startswith("MISSING_HOLDING_CLOSE") for w in decision.warnings)
    assert decision.exits[removed] == "market_trend_exit"
    execution = advance_open(data, dates[271], state, cost_bps=10)
    assert execution.transactions[0]["ticker"] == removed
    assert execution.transactions[0]["side"] == "sell"
    assert execution.transactions[0]["price"] == prices[removed].loc[dates[271], "open"]
    assert removed not in state.positions and not state.blocked_exits
    next_selection = evaluate_close(data, dates[279], "C1", state)
    assert next_selection.allow_new_risk and removed not in next_selection.selected
    next_open = advance_open(data, dates[280], state, cost_bps=10)
    assert next_open.transactions
    assert all(trade["ticker"] != removed for trade in next_open.transactions)


def test_adjusted_basis_sync_is_same_date_not_market_gap(market):
    prices, names, dates = market
    ticker = names[0]
    data = prepared(market)
    old = float(prices[ticker].loc[dates[270], "close"])
    state = held(ticker, dates, price=old, stop=old - 3)
    evaluate_close(data, dates[270], "C3", state)
    value_before = state.positions[ticker].quantity * state.marks[ticker]
    for name in ("open", "high", "low", "close"):
        prices[ticker][name] *= 0.5
    refreshed = prepared(market)
    events = sync_price_basis(refreshed, state)
    assert events[0]["action"] == "adjustment_rescale"
    assert state.positions[ticker].quantity == 200
    assert state.positions[ticker].quantity * state.marks[ticker] == pytest.approx(value_before)
    assert not sync_price_basis(refreshed, state)
    # A change only at tomorrow's open is execution slippage, not a rebase.
    prices[ticker].loc[dates[271], "open"] = 7
    assert not sync_price_basis(prepared(market), state)


def test_persisted_daily_loop_matches_shared_simulation(market):
    prices, names, dates = market
    sessions = dates[259:286]
    rebalance = dates[[259, 279]]
    data = prepare_inputs(prices, names, sessions, rebalance)
    simulation = run_simulation(prices, names, "C3", sessions, rebalance, cost_bps=25, integer_shares=True, prepared=data)
    state = PortfolioState()
    transactions = []
    for date in sessions:
        execution = advance_open(data, date, state, cost_bps=25, integer_shares=True)
        transactions.extend(execution.transactions)
        evaluate_close(data, date, "C3", state)
        state = PortfolioState.from_dict(json.loads(json.dumps(state.to_dict(), allow_nan=False)))
    assert state.to_dict() == simulation.final_state.to_dict()
    assert len(transactions) == len(simulation.backtest.transactions)
    assert simulation.backtest.equity.iloc[-1] == pytest.approx(state.cash + sum(p.quantity * state.marks[t] for t, p in state.positions.items()))
