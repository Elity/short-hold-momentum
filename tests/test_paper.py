import pandas as pd
import pytest

from shm.paper import (
    FILL_COLUMNS,
    PAPER_LOOKBACK_SESSIONS,
    TICKET_COLUMNS,
    Fill,
    PaperAccount,
    build_monthly_comparison_inputs,
    fills_from_frame,
    fills_to_frame,
    generate_integer_share_tickets,
    ingest_fills,
    paper_xnys_window,
    read_fill_csv,
    read_ticket_csv,
    realized_cost_bps,
    render_monthly_report,
    validate_paper_window,
    write_fill_csv,
    write_monthly_report,
    write_ticket_csv,
)


def test_paper_account_rejects_live_mode_and_invalid_balances() -> None:
    with pytest.raises(PermissionError, match="live endpoints are forbidden"):
        PaperAccount(cash=1_000, mode="live")
    with pytest.raises(ValueError, match="cash"):
        PaperAccount(cash=-0.01)
    with pytest.raises(ValueError, match="integer shares"):
        PaperAccount(cash=1_000, positions={"AAPL": -1})


def test_integer_ticket_generation_substitutes_expensive_stock_without_negative_cash() -> None:
    plan = generate_integer_share_tickets(
        PaperAccount(cash=1_000),
        ["EXPENSIVE", "AAA", "BBB"],
        {"EXPENSIVE": 600, "AAA": 100, "BBB": 200},
        target_count=2,
        estimated_cost_bps=10,
        as_of="2026-09-04",
    )

    assert [(ticket.ticker, ticket.side, ticket.qty) for ticket in plan.tickets] == [
        ("AAA", "buy", 5),
        ("BBB", "buy", 2),
    ]
    assert all(isinstance(ticket.qty, int) for ticket in plan.tickets)
    assert plan.projected_cash == pytest.approx(99.1)
    assert plan.projected_cash >= 0
    assert plan.skipped[0].ticker == "EXPENSIVE"
    assert plan.skipped[0].replacement_ticker == "AAA"
    assert "price_exceeds_target_amount" in plan.skipped[0].reason
    assert "substitutes=EXPENSIVE" in plan.tickets[0].reason
    assert list(plan.to_frame().columns) == [
        "ticker",
        "side",
        "qty",
        "order_type",
        "time_in_force",
        "reason",
    ]


def test_unsubstituted_expensive_stock_keeps_an_explicit_skip_reason() -> None:
    plan = generate_integer_share_tickets(
        PaperAccount(cash=100),
        ["TOO_HIGH"],
        {"TOO_HIGH": 101},
        target_count=1,
    )

    assert plan.tickets == ()
    assert plan.target_positions == {}
    assert plan.projected_cash == 100
    assert plan.skipped[0].replacement_ticker is None
    assert plan.skipped[0].reason.endswith("no_affordable_substitute")


def test_fill_ingestion_updates_only_paper_state_and_calculates_realized_cost() -> None:
    plan = generate_integer_share_tickets(
        PaperAccount(cash=1_000),
        ["AAA", "BBB"],
        {"AAA": 100, "BBB": 200},
        target_count=2,
        estimated_cost_bps=10,
        as_of="2026-09-04",
    )
    fills = (
        Fill("AAA", 5, 101, "2026-09-05 09:30", 100, commission=1),
        Fill("BBB", 2, 199, "2026-09-05 09:30", 200, commission=0.5),
    )

    result = ingest_fills(PaperAccount(cash=1_000), plan, fills)

    assert result.account.positions == {"AAA": 5, "BBB": 2}
    assert result.account.cash == pytest.approx(95.5)
    assert result.account.cash >= 0
    assert result.realized_cost_bps == pytest.approx((5 + 1 + 2 + 0.5) / 900 * 10_000)
    assert realized_cost_bps(101, 100, qty=5, commission=1) == pytest.approx(120)
    assert fills_from_frame(fills_to_frame(fills)) == fills


def test_fill_ingestion_rejects_a_fill_that_would_borrow_cash() -> None:
    plan = generate_integer_share_tickets(
        PaperAccount(cash=100),
        ["AAA"],
        {"AAA": 99},
        target_count=1,
        estimated_cost_bps=0,
    )

    with pytest.raises(ValueError, match="negative cash"):
        ingest_fills(
            PaperAccount(cash=100),
            plan,
            [Fill("AAA", 1, 101, "2026-09-05 09:30", 99)],
        )


def test_monthly_inputs_use_only_observed_common_dates_and_attribution_data() -> None:
    plan = generate_integer_share_tickets(
        PaperAccount(cash=1_000),
        ["EXPENSIVE", "AAA", "BBB"],
        {"EXPENSIVE": 600, "AAA": 100, "BBB": 200},
        target_count=2,
        estimated_cost_bps=10,
        as_of="2026-09-04",
    )
    ingestion = ingest_fills(
        PaperAccount(cash=1_000),
        plan,
        [
            Fill("AAA", 5, 101, "2026-09-05 09:30", 100, commission=1),
            Fill("BBB", 2, 199, "2026-09-05 09:30", 200, commission=0.5),
        ],
    )
    dates = pd.to_datetime(["2026-09-01", "2026-09-15", "2026-09-30"])
    inputs = build_monthly_comparison_inputs(
        "2026-09",
        pd.Series([1_000, 1_030, 1_050], index=dates),
        pd.Series([1_000, 1_020, 1_040], index=dates),
        applied_fills=ingestion.applied_fills,
        ticket_plans=[plan],
    )

    assert inputs.paper_return == pytest.approx(0.05)
    assert inputs.model_return == pytest.approx(0.04)
    assert inputs.return_gap == pytest.approx(0.01)
    assert inputs.realized_cost_bps == ingestion.realized_cost_bps
    assert inputs.cost_multiple == pytest.approx(inputs.realized_cost_bps / 10)
    assert inputs.hc07_triggered is True
    assert inputs.execution_price_impact_usd == pytest.approx(4.5)
    assert inputs.integer_rounding_usd == pytest.approx(plan.rounding_residual_usd)
    assert inputs.skipped_candidates == plan.skipped
    assert inputs.option_overlay_pnl_usd is None


def test_monthly_inputs_do_not_create_a_report_without_observed_period_data() -> None:
    dates = pd.to_datetime(["2026-09-01", "2026-09-30"])
    with pytest.raises(ValueError, match="at least two observed"):
        build_monthly_comparison_inputs(
            "2026-10",
            pd.Series([1_000, 1_010], index=dates),
            pd.Series([1_000, 1_005], index=dates),
        )


def test_ticket_and_fill_csv_round_trip_strict_contracts(tmp_path) -> None:
    plan = generate_integer_share_tickets(
        PaperAccount(cash=1_000),
        ["AAA"],
        {"AAA": 100},
        target_count=1,
        as_of="2026-09-04",
    )
    ticket_path = write_ticket_csv(tmp_path / "tickets.csv", plan)
    assert tuple(pd.read_csv(ticket_path).columns) == TICKET_COLUMNS
    assert read_ticket_csv(ticket_path) == plan.tickets

    fills = (Fill("AAA", 9, 100.25, "2026-09-05 09:30", 100, commission=1.25),)
    fill_path = write_fill_csv(tmp_path / "fills.csv", fills)
    assert tuple(pd.read_csv(fill_path).columns) == (*FILL_COLUMNS, "commission")
    assert read_fill_csv(fill_path) == fills

    zero_fee_path = write_fill_csv(
        tmp_path / "fills-zero-fee.csv",
        [Fill("AAA", 1, 100, "2026-09-05 09:30", 100)],
    )
    assert tuple(pd.read_csv(zero_fee_path).columns) == FILL_COLUMNS

    bad = pd.DataFrame([{**plan.tickets[0].to_record(), "endpoint": "live"}])
    bad.to_csv(tmp_path / "bad.csv", index=False)
    with pytest.raises(ValueError, match="exactly"):
        read_ticket_csv(tmp_path / "bad.csv")


def test_paper_window_is_exactly_the_latest_260_xnys_sessions() -> None:
    window = paper_xnys_window("2026-09-04")
    assert len(window) == PAPER_LOOKBACK_SESSIONS
    assert window[-1] == pd.Timestamp("2026-09-04")
    pd.testing.assert_index_equal(
        validate_paper_window(window, as_of="2026-09-04"),
        window,
    )
    with pytest.raises(PermissionError, match="live endpoints"):
        paper_xnys_window("2026-09-04", mode="live")
    with pytest.raises(ValueError, match="latest 260"):
        validate_paper_window(
            [window[0] - pd.offsets.BDay(1), *window],
            as_of="2026-09-04",
        )


def test_monthly_markdown_contains_required_comparison_and_attribution(tmp_path) -> None:
    plan = generate_integer_share_tickets(
        PaperAccount(cash=1_000),
        ["EXPENSIVE", "AAA"],
        {"EXPENSIVE": 1_100, "AAA": 100},
        target_count=1,
        as_of="2026-09-04",
    )
    ingestion = ingest_fills(
        PaperAccount(cash=1_000),
        plan,
        [Fill("AAA", 9, 101, "2026-09-05 09:30", 100, commission=1)],
    )
    dates = pd.to_datetime(["2026-09-01", "2026-09-30"])
    inputs = build_monthly_comparison_inputs(
        "2026-09",
        pd.Series([1_000, 1_050], index=dates),
        pd.Series([1_000, 1_040], index=dates),
        applied_fills=ingestion.applied_fills,
        ticket_plans=[plan],
        option_overlay_pnl_usd=12.5,
    )

    report = render_monthly_report(inputs)
    assert "Paper vs model" in report
    assert "Cost multiple" in report
    assert "Execution price impact" in report
    assert "Whole-share rounding residual" in report
    assert "Skipped/substituted stocks" in report
    assert "Option overlay P&L" in report
    assert "HC-07" in report
    path = write_monthly_report(tmp_path / "monthly.md", inputs)
    assert path.read_text(encoding="utf-8") == report
