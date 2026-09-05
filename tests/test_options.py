from __future__ import annotations

from collections import namedtuple
from datetime import date

import pandas as pd
import pytest

from shm.options import (
    Candidate,
    Holding,
    OptionChainSnapshot,
    OverlayRejectedError,
    YFinanceOptionChainSource,
    black_scholes_delta,
    build_overlay_plan,
    cash_secured_put_risk,
    covered_call_risk,
    first_standard_expiration,
    make_cash_secured_put_order,
    paper_ticket_rows,
    select_cash_secured_put,
    select_covered_call,
    validate_overlay,
    write_paper_ticket_csv,
)


def _chain(ticker: str = "AAA") -> OptionChainSnapshot:
    return OptionChainSnapshot(
        ticker=ticker,
        expiration=date(2026, 10, 16),
        calls=pd.DataFrame(
            [
                {
                    "contractSymbol": f"{ticker}261016C00105000",
                    "strike": 105.0,
                    "bid": 1.00,
                    "ask": 1.10,
                    "impliedVolatility": None,
                },
                {
                    "contractSymbol": f"{ticker}261016C00110000",
                    "strike": 110.0,
                    "bid": 1.20,
                    "ask": 1.50,
                    "impliedVolatility": None,
                },
            ]
        ),
        puts=pd.DataFrame(
            [
                {
                    "contractSymbol": f"{ticker}261016P00090000",
                    "strike": 90.0,
                    "bid": 0.80,
                    "ask": 1.00,
                    "impliedVolatility": 0.25,
                },
                {
                    "contractSymbol": f"{ticker}261016P00095000",
                    "strike": 95.0,
                    "bid": 1.40,
                    "ask": 1.60,
                    "impliedVolatility": 0.25,
                },
            ]
        ),
    )


def test_t11_risk_calculations_and_coverage_rejection() -> None:
    call = covered_call_risk(
        shares=250,
        stock_cost_basis=50.0,
        strike=55.0,
        premium_per_share=1.50,
    )
    put = cash_secured_put_risk(strike=45.0, premium_per_share=1.20)
    assert call.contracts == 2
    assert call.covered_shares == 200
    assert call.max_loss == 9_700.0
    assert call.upside_cap == 55.0
    assert call.cash_usage == 0.0
    assert put.max_loss == 4_380.0
    assert put.cash_usage == 4_500.0
    with pytest.raises(OverlayRejectedError, match="at least 100 shares"):
        covered_call_risk(
            shares=99,
            stock_cost_basis=50.0,
            strike=55.0,
            premium_per_share=1.50,
        )


def test_t11_cash_and_aggregate_loss_constraints_reject() -> None:
    order = make_cash_secured_put_order(
        underlying="AAA",
        contract_symbol="AAA261016P00045000",
        expiration=date(2026, 10, 16),
        strike=45.0,
        bid=1.20,
        ask=1.30,
        delta=-0.20,
        delta_source="chain",
    )
    with pytest.raises(OverlayRejectedError, match="available cash"):
        validate_overlay([order], portfolio_equity=50_000, available_cash=4_499)
    with pytest.raises(OverlayRejectedError, match="20%"):
        validate_overlay([order], portfolio_equity=20_000, available_cash=5_000)
    with pytest.raises(OverlayRejectedError, match="maximum loss"):
        validate_overlay([order], portfolio_equity=4_000, available_cash=5_000)


def test_first_standard_expiration_and_yfinance_api_adapter() -> None:
    Options = namedtuple("Options", ["calls", "puts", "underlying"])

    class FakeTicker:
        options = ("2026-10-09", "2026-10-16", "2026-11-20")

        def __init__(self) -> None:
            self.requested: str | None = None

        def option_chain(self, expiration: str):
            self.requested = expiration
            chain = _chain()
            return Options(chain.calls, chain.puts, {})

    fake = FakeTicker()
    source = YFinanceOptionChainSource(lambda symbol: fake)
    snapshot = source.load("AAA", not_before=date(2026, 10, 10))
    assert first_standard_expiration(fake.options, not_before="2026-10-10") == date(
        2026, 10, 16
    )
    assert snapshot is not None
    assert fake.requested == "2026-10-16"
    assert snapshot.expiration == date(2026, 10, 16)


def test_call_uses_5pct_otm_fallback_and_liquidity_rules() -> None:
    selected = select_covered_call(
        _chain(),
        spot=100.0,
        as_of=date(2026, 9, 16),
    )
    assert selected is not None
    assert selected.strike == 105.0
    assert selected.delta is None
    assert selected.delta_source == "otm_fallback"


def test_yfinance_iv_supplies_local_black_scholes_put_delta() -> None:
    snapshot = _chain()
    selected = select_cash_secured_put(
        snapshot,
        spot=100.0,
        as_of=date(2026, 9, 16),
        available_cash=10_000.0,
    )
    assert selected is not None
    assert selected.strike == 95.0
    assert selected.delta is not None
    assert abs(selected.delta) <= 0.25
    assert selected.delta_source == "black_scholes"
    call_delta = black_scholes_delta(
        option_kind="call",
        spot=100.0,
        strike=100.0,
        volatility=0.20,
        expiration=date(2027, 9, 16),
        as_of=date(2026, 9, 16),
    )
    put_delta = black_scholes_delta(
        option_kind="put",
        spot=100.0,
        strike=100.0,
        volatility=0.20,
        expiration=date(2027, 9, 16),
        as_of=date(2026, 9, 16),
    )
    assert call_delta - put_delta == pytest.approx(1.0)


def test_cash_secured_put_rejects_zero_bid_and_wide_spread() -> None:
    snapshot = OptionChainSnapshot(
        ticker="AAA",
        expiration=date(2026, 10, 16),
        calls=pd.DataFrame(),
        puts=pd.DataFrame(
            [
                {
                    "contractSymbol": "AAA261016P00097000",
                    "strike": 97.0,
                    "bid": 0.0,
                    "ask": 1.0,
                    "impliedVolatility": 0.25,
                },
                {
                    "contractSymbol": "AAA261016P00096000",
                    "strike": 96.0,
                    "bid": 1.0,
                    "ask": 2.0,
                    "impliedVolatility": 0.25,
                },
                {
                    "contractSymbol": "AAA261016P00095000",
                    "strike": 95.0,
                    "bid": 1.4,
                    "ask": 1.6,
                    "impliedVolatility": 0.25,
                },
            ]
        ),
    )
    selected = select_cash_secured_put(
        snapshot,
        spot=100.0,
        as_of=date(2026, 9, 16),
        available_cash=10_000.0,
    )
    assert selected is not None
    assert selected.strike == 95.0


def test_parameterized_dry_run_stays_covered_and_paper_only(tmp_path) -> None:
    class FakeSource:
        def load(self, ticker: str, *, not_before: date):
            assert not_before == date(2026, 10, 1)
            return _chain(ticker)

    plan = build_overlay_plan(
        holdings=[
            Holding("AAA", shares=250, spot=100.0, cost_basis_per_share=50.0),
            Holding("SMALL", shares=99, spot=25.0, cost_basis_per_share=20.0),
        ],
        candidates=[Candidate("BBB", spot=100.0)],
        portfolio_equity=50_000.0,
        available_cash=10_000.0,
        as_of=date(2026, 9, 16),
        next_rebalance_date=date(2026, 10, 1),
        source=FakeSource(),
    )
    assert [(order.strategy, order.contracts) for order in plan.orders] == [
        ("covered_call", 2),
        ("cash_secured_put", 1),
    ]
    assert plan.summary.cash_usage == 9_500.0
    assert plan.summary.csp_notional <= 50_000.0 * 0.20
    assert any(skip.ticker == "SMALL" for skip in plan.skipped)
    rows = paper_ticket_rows(plan)
    assert set(rows[0]) == {
        "ticker",
        "side",
        "qty",
        "order_type",
        "time_in_force",
        "reason",
    }
    assert all(row["side"] == "sell" for row in rows)
    assert all("paper_only" in str(row["reason"]) for row in rows)
    output = write_paper_ticket_csv(plan, tmp_path / "ticket.csv")
    assert pd.read_csv(output).columns.tolist() == list(rows[0])
