from dataclasses import asdict, replace

import numpy as np
import pandas as pd
import pytest

from shm.v03.corporate_actions import AdjustmentBasis, CorporateAction, convert_position
from shm.v03.engine import advance_open
from shm.v03.strategy import Decision, PortfolioState, PositionState, evaluate_close, mark_equity, prepare_inputs


def _action(**changes):
    action = CorporateAction(
        action_id="FRX-2014-07-01", source_ticker="FRX", target_ticker="ACT",
        announced_date="2014-02-18", known_date="2014-06-30",
        last_trading_session="2014-06-30", effective_session="2014-07-01",
        cash_per_share=26.04, exchange_ratio=0.3306, cash_in_lieu_price=219.0,
        evidence="issuer closing notice; hashed source validated by loader",
        source_price_treatment="terminal_before_action",
    )
    return replace(action, **changes)


def _convert(position, action=None, **changes):
    kwargs = {
        "source_basis": AdjustmentBasis(0.5, "2014-06-30", "source final raw/adjusted quote"),
        "target_basis": AdjustmentBasis(0.25, "2014-07-01", "successor raw/adjusted quote"),
        "target_mark": 56.0,
    }
    kwargs.update(changes)
    return convert_position(position, action or _action(), **kwargs)


def test_mixed_conversion_preserves_value_cost_basis_and_atr_bound_without_market_fill():
    # 200 adjusted units are 100 nominal shares, not 200 real shares.
    position = PositionState(200, 40, "2014-03-03", 55, 47)
    before = asdict(position)
    result = _convert(position)
    successor = result.target_position
    assert result.cash_delta == pytest.approx(2604)
    assert successor.quantity == pytest.approx(100 * .3306 / .25)
    assert successor.entry_date == position.entry_date
    assert result.cash_delta + successor.quantity * 56 == pytest.approx(100 * (26.04 + .3306 * 224))
    assert result.cash_cost_basis + result.target_cost_basis == pytest.approx(8000)
    assert successor.quantity * successor.average_cost == pytest.approx(result.target_cost_basis)
    assert result.realized_cash_pnl + successor.quantity * (56 - successor.average_cost) == pytest.approx(
        result.event["total_consideration"] - 8000,
    )
    assert successor.quantity * successor.peak_close + result.cash_delta == pytest.approx(200 * 55)
    assert successor.quantity * successor.trailing_stop + result.cash_delta == pytest.approx(200 * 47)
    assert result.event["model_cost"] == 0 and result.event["market_fill"] is False
    assert asdict(position) == before
    assert result == _convert(position)  # Pure repeat; the engine owns apply-once persistence.


def test_adjusted_price_rebase_does_not_change_nominal_entitlement_or_dollar_bounds():
    first = _convert(PositionState(200, 40, "2014-03-03", 55, 47))
    rebased = _convert(
        PositionState(400, 20, "2014-03-03", 27.5, 23.5),
        source_basis=AdjustmentBasis(.25, "2014-06-30", "source rebased cache"),
        target_basis=AdjustmentBasis(.125, "2014-07-01", "target rebased cache"), target_mark=28,
    )
    assert rebased.cash_delta == first.cash_delta
    assert rebased.event["target_actual_shares"] == first.event["target_actual_shares"]
    assert rebased.target_cost_basis == pytest.approx(first.target_cost_basis)
    assert rebased.target_position.quantity == pytest.approx(first.target_position.quantity * 2)
    assert rebased.target_position.trailing_stop == pytest.approx(first.target_position.trailing_stop / 2)


def test_integer_mode_rounds_actual_successor_shares_and_uses_contractual_fractional_cash():
    result = _convert(PositionState(200, 40, "2014-03-03", 55), integer_actual_shares=True)
    assert result.event["entitled_successor_shares"] == pytest.approx(33.06)
    assert result.event["target_actual_shares"] == 33
    assert result.target_position.quantity == 132  # Actual shares / .25, not floor(adjusted units).
    assert result.cash_delta == pytest.approx(2604 + .06 * 219)
    assert result.event["cash_in_lieu"] == pytest.approx(.06 * 219)
    with pytest.raises(ValueError, match="cash-in-lieu"):
        _convert(PositionState(200, 40, "2014-03-03", 55),
                 _action(cash_in_lieu_price=None), integer_actual_shares=True)


def test_cash_only_action_removes_position_and_recognizes_economic_pnl():
    result = _convert(
        PositionState(200, 40, "2014-03-03", 55),
        _action(target_ticker=None, exchange_ratio=0, cash_per_share=100, cash_in_lieu_price=None),
        target_basis=None, target_mark=None,
    )
    assert result.cash_delta == 10000
    assert result.target_position is None
    assert result.cash_cost_basis == 8000 and result.target_cost_basis == 0
    assert result.realized_cash_pnl == 2000


def test_action_rejects_future_knowledge_double_counting_or_unverified_basis():
    with pytest.raises(ValueError, match="known"):
        _action(known_date="2014-07-02")
    with pytest.raises(ValueError, match="double count"):
        _action(source_price_treatment="total_return_continuation")
    with pytest.raises(ValueError, match="positive adjustment factor"):
        AdjustmentBasis(0, "2014-07-01", "evidence")
    with pytest.raises(ValueError, match="dated evidence"):
        AdjustmentBasis(1, "2014-07-01", "")
    position = PositionState(200, 40, "2014-03-03", 55)
    with pytest.raises(ValueError, match="final trading session"):
        _convert(position, source_basis=AdjustmentBasis(.5, "2014-06-27", "stale quote"))
    with pytest.raises(ValueError, match="later session"):
        _convert(position, target_basis=AdjustmentBasis(.25, "2014-07-02", "future quote"))
    with pytest.raises(ValueError, match="positive mark"):
        _convert(position, target_mark=None)


def _market(*, settlement="2014-07-02", missing=None, continuing=False):
    dates = pd.to_datetime(["2014-06-27", "2014-06-30", "2014-07-01", "2014-07-02", "2014-07-03"])
    prices = {}
    for name, adjusted, nominal in (("FRX", 50., 100.), ("ACT", 25., 100.), ("SPY", 100., 100.)):
        prices[name] = pd.DataFrame({"open": adjusted, "close": adjusted, "high": adjusted + 1,
                                     "low": adjusted - 1, "volume": 1e6, "as_traded_close": nominal}, index=dates)
    # The successor splits 2-for-1 on the merger day. Its effective basis is
    # 25/100=.25; using the prior day's 25/200=.125 would double the entitlement.
    prices["ACT"].loc[dates[:2], "as_traded_close"] = 200.
    if not continuing:
        prices["FRX"] = prices["FRX"].loc[:"2014-06-30"]
    if missing is not None:
        prices["ACT"].loc["2014-07-01", missing] = np.nan
    action = _action(cash_per_share=50, exchange_ratio=.5, cash_settlement_session=settlement)
    data = prepare_inputs(prices, ("FRX", "ACT"), dates, (), corporate_actions=[action])
    state = PortfolioState(cash=0, positions={"FRX": PositionState(20, 40, "2014-03-03", 60, 45)},
                           marks={"FRX": 50.}, mark_dates={"FRX": "2014-06-30"}, equity_high_water=1000.)
    return data, state


def test_shared_open_converts_once_and_only_releases_verified_cash_on_settlement():
    data, state = _market()
    result = advance_open(data, "2014-07-01", state, cost_bps=10)
    assert state.cash == 0 and state.receivables_value == 500
    assert state.shares == {"ACT": 20.}
    assert result.equity == 1000 and result.transactions == [] and result.cost == 0
    assert state.positions["ACT"].trailing_stop == 20
    assert state.positions["ACT"].peak_close == 35
    assert mark_equity(data, "2014-07-01", state) == (1000., [])
    serial = state.to_dict()
    restored = PortfolioState.from_dict(serial)
    repeat = advance_open(data, "2014-07-01", restored, cost_bps=10)
    assert repeat.events[0]["action"] == "already_processed"
    assert restored.to_dict() == serial
    settlement = advance_open(data, "2014-07-02", restored, cost_bps=10)
    assert restored.cash == 500 and restored.receivables_value == 0
    assert [e["action"] for e in settlement.events] == ["corporate_cash_settlement"]
    advance_open(data, "2014-07-03", restored, cost_bps=10)
    assert restored.cash == 500 and restored.processed_corporate_actions == ["FRX-2014-07-01"]


def test_existing_successor_keeps_its_atr_state_and_source_exit_sells_only_received_shares():
    data, state = _market()
    state.positions["ACT"] = PositionState(7, 20, "2013-01-01", 30, 22)
    state.marks["ACT"] = 25
    state.mark_dates["ACT"] = "2014-06-30"
    state.pending = Decision("2014-06-30", "2014-07-01", "risk_exit", exits={"FRX": "atr_trailing_exit"})
    result = advance_open(data, "2014-07-01", state, cost_bps=10)
    existing = state.positions["ACT"]
    assert existing.quantity == 7 and existing.entry_date == "2013-01-01"
    assert existing.peak_close == 30 and existing.trailing_stop == 22
    assert len(result.transactions) == 1
    assert result.transactions[0]["ticker"] == "ACT"
    assert result.transactions[0]["quantity"] == 20
    assert result.cost == pytest.approx(.5)  # Only the actual successor sale is charged.
    assert state.cash == pytest.approx(499.5) and state.receivables_value == 500
    assert not state.blocked_exits
    action = next(e for e in result.events if e["action"] == "corporate_action_conversion")
    assert action["existing_target_before"]["quantity"] == 7
    assert action["source_position"]["trailing_stop"] == 45


@pytest.mark.parametrize("missing,continuing", [("as_traded_close", False), ("open", False), (None, True)])
def test_missing_or_continued_price_input_keeps_source_unconverted(missing, continuing):
    data, state = _market(missing=missing, continuing=continuing)
    state.cash = 1000
    state.pending = Decision("2014-06-30", "2014-07-01", "rebalance", target_weights={"ACT": 1.},
                             diagnostics={"allow_new_risk": True})
    result = advance_open(data, "2014-07-01", state, cost_bps=10)
    assert any(e["action"] == "unresolved_corporate_action" for e in result.events)
    assert not any(row["side"] == "buy" for row in result.transactions)
    assert "FRX" in state.positions and not state.processed_corporate_actions
    assert not state.corporate_receivables


def test_unknown_cash_availability_remains_receivable_and_never_becomes_purchasing_cash():
    data, state = _market(settlement=None)
    result = advance_open(data, "2014-07-01", state, cost_bps=10)
    assert state.cash == 0 and state.receivables_value == 500
    assert result.equity == 1000
    assert any(e["action"] == "unresolved_corporate_settlement" for e in result.events)
    decision = evaluate_close(data, "2014-07-01", "C0", state)
    assert "MISSING_CORPORATE_SETTLEMENT:FRX-2014-07-01" in decision.warnings
    assert not decision.allow_new_risk
    advance_open(data, "2014-07-03", state, cost_bps=10)
    assert state.cash == 0 and state.receivables_value == 500


def test_own_successor_exit_has_priority_and_later_intent_is_not_executed_early():
    data, state = _market()
    state.positions["ACT"] = PositionState(7, 20, "2013-01-01", 30, 22)
    state.marks["ACT"], state.mark_dates["ACT"] = 25., "2014-06-30"
    state.pending = Decision("2014-06-30", "2014-07-01", "risk_exit",
                             exits={"FRX": "atr_trailing_exit", "ACT": "market_trend_exit"})
    result = advance_open(data, "2014-07-01", state, cost_bps=10)
    assert not state.positions and result.transactions[0]["quantity"] == 27
    assert result.transactions[0]["reason"] == "market_trend_exit"
    data, state = _market()
    state.pending = Decision("2014-06-30", "2014-07-02", "risk_exit", exits={"FRX": "atr_trailing_exit"})
    assert not advance_open(data, "2014-07-01", state, cost_bps=10).transactions
    assert state.shares == {"ACT": 20.}
    assert advance_open(data, "2014-07-02", state, cost_bps=10).transactions[0]["quantity"] == 20


def test_delayed_partial_rebalance_preserves_unrequested_successor_equity():
    data, state = _market()
    state.blocked_exits["FRX"] = {"signal_date": "2014-06-27", "reason": "rebalance_reduce",
                                   "event_type": "rebalance", "target_weight": .5}
    result = advance_open(data, "2014-07-01", state, cost_bps=10)
    # Of the $1000 pre-action entitlement, the old target retained one half;
    # retain half the stock entitlement too, with the other half's sale only.
    assert state.shares == {"ACT": 10.}
    assert result.transactions[0]["quantity"] == 10


def test_new_issuer_reusing_ticker_is_not_converted_by_old_action():
    data, state = _market(continuing=True)
    state.positions["FRX"].entry_date = "2014-07-01"
    result = advance_open(data, "2014-07-02", state, cost_bps=10)
    assert state.shares == {"FRX": 20.} and not state.corporate_receivables
    assert not result.events and mark_equity(data, "2014-07-02", state) == (1000., [])


def test_cash_settlement_evidence_can_resolve_an_existing_unknown_receivable():
    data, state = _market(settlement=None)
    advance_open(data, "2014-07-01", state, cost_bps=10)
    updated, _ = _market(settlement="2014-07-02")
    result = advance_open(updated, "2014-07-02", state, cost_bps=10)
    assert state.cash == 500 and state.receivables_value == 0
    assert [event["action"] for event in result.events] == ["corporate_cash_settlement"]


def test_paper_loader_uses_the_same_conversion_and_values_receivables_separately(tmp_path, monkeypatch):
    from shm.paper import v03 as paper
    from shm.v04 import history
    data, state = _market()
    old_reference = "2013-01-02"  # Outside the paper caller's normal 260-session window.
    state.mark_dates["FRX"], state.marks["FRX"] = old_reference, 100.
    state.positions["FRX"] = PositionState(20, 80, old_reference, 120, 90)
    frames = {}
    root = tmp_path
    (root / "config").mkdir()
    (root / "config/universe.yaml").write_text("tickers: [FRX, ACT]\nexclusions: []\n")
    (root / "data/raw/prices").mkdir(parents=True)
    for ticker in data.tickers:
        column = data.ticker_index[ticker]
        frame = pd.DataFrame({"date": data.dates, "open": data.opens[:, column], "close": data.closes[:, column],
                              "high": data.highs[:, column], "low": data.lows[:, column],
                              "volume": data.volumes[:, column], "as_traded_close": data.as_traded_closes[:, column]})
        frame = frame.loc[frame.close.notna()]
        if ticker == "FRX":
            reference = frame.iloc[[0]].copy()
            reference["date"] = pd.Timestamp(old_reference)
            frame = pd.concat([reference, frame], ignore_index=True)
        frames[ticker] = frame
        frame.to_parquet(root / f"data/raw/prices/{ticker}.parquet", index=False)
    data = prepare_inputs(frames, data.universe, data.sessions, (), corporate_actions=data.corporate_actions)
    monkeypatch.setattr(history, "load_corporate_actions", lambda root: (data.corporate_actions, {}, {}))
    monkeypatch.setattr(paper, "_schedule", lambda root, as_of: ())
    paper_data, _ = paper._prepare_day(root, pd.Timestamp("2014-07-01"), [state], "S500-C3")
    assert pd.Timestamp(old_reference) in paper_data.date_index
    shared_state = PortfolioState.from_dict(state.to_dict())
    expected = advance_open(data, "2014-07-01", shared_state, cost_bps=10)
    actual = advance_open(paper_data, "2014-07-01", state, cost_bps=10)
    assert state.to_dict() == shared_state.to_dict()
    assert actual.to_dict() == expected.to_dict()
    valuation = paper._valuation(state)
    assert valuation["equity"] == 2000 and valuation["cash"] == 0
    assert valuation["corporate_receivables"] == 1000 and valuation["stock_exposure"] == .5


def test_known_future_receivable_scales_equal_weight_basket_before_any_purchase():
    data, state = _market(settlement="2014-07-03")
    state.cash = 1000
    state.pending = Decision("2014-06-30", "2014-07-01", "rebalance",
                             target_weights={"ACT": .5, "SPY": .5}, diagnostics={"allow_new_risk": True})
    result = advance_open(data, "2014-07-01", state, cost_bps=10)
    actual_values = [state.positions[ticker].quantity * data.opens[data.row("2014-07-01"), data.ticker_index[ticker]]
                     for ticker in ("ACT", "SPY")]
    assert state.receivables_value == 500 and state.cash >= 0
    assert actual_values[0] == pytest.approx(actual_values[1])
    assert sum(actual_values) + result.cost == pytest.approx(1500)
    assert state.cash == pytest.approx(0, abs=1e-6)


@pytest.mark.parametrize("ticker,nav,quantity,cash", [("FRX", 2000., 40., 1000.), ("ACT", 1700., 48., 500.)])
def test_unverified_conversion_units_survive_restarts_until_reference_is_restored(ticker, nav, quantity, cash):
    data, state = _market()
    state.positions[ticker] = PositionState(20 if ticker == "FRX" else 7, 80, "2013-01-01", 120, 90)
    state.marks[ticker], state.mark_dates[ticker] = 100., "2014-06-26"
    original_positions = state.shares.copy()
    for day in ("2014-07-01", "2014-07-02"):
        result = advance_open(data, day, state, cost_bps=10)
        assert any(event["action"] == "unresolved_corporate_action" for event in result.events)
        assert state.shares == original_positions and not result.transactions
        assert not state.processed_corporate_actions and not state.corporate_receivables
        decision = evaluate_close(data, day, "C0", state)
        assert decision.diagnostics["equity"] == nav
        assert state.marks[ticker] == 100 and state.mark_dates[ticker] == "2014-06-26"
        assert ticker in state.unverified_price_basis
        state = PortfolioState.from_dict(state.to_dict())

    frames = {}
    for name in data.tickers:
        column = data.ticker_index[name]
        frame = pd.DataFrame({"open": data.opens[:, column], "close": data.closes[:, column],
                              "high": data.highs[:, column], "low": data.lows[:, column],
                              "volume": data.volumes[:, column], "as_traded_close": data.as_traded_closes[:, column]},
                             index=data.dates).dropna(subset=["close"])
        if name == ticker:
            frame.loc[pd.Timestamp("2014-06-26")] = frame.iloc[0]
        frames[name] = frame.sort_index()
    repaired = prepare_inputs(frames, data.universe, data.sessions, (), corporate_actions=data.corporate_actions)
    advance_open(repaired, "2014-07-03", state, cost_bps=10)
    assert not state.unverified_price_basis
    assert state.shares == {"ACT": quantity} and state.cash == cash
    assert mark_equity(repaired, "2014-07-03", state) == (nav, [])
    assert state.processed_corporate_actions == ["FRX-2014-07-01"]
    snapshot = state.to_dict()
    advance_open(repaired, "2014-07-03", state, cost_bps=10)
    assert state.to_dict() == snapshot
