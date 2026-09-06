import json
from datetime import date
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest
import yaml

from shm.config import ConfigBundle
from shm.experiments import compute_file_hash, compute_params_hash
from shm.options import OptionOrder, OverlayPlan, OverlaySummary, SkippedOverlay
from shm.paper import (
    FILL_COLUMNS,
    PAPER_LOOKBACK_SESSIONS,
    TICKET_COLUMNS,
    Fill,
    OrderTicket,
    PaperAccount,
    build_paper_progress,
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
    run_paper_option_overlay,
    run_paper_rebalance,
    simulate_next_open_fills,
    validate_paper_window,
    write_fill_csv,
    write_monthly_report,
    write_ticket_csv,
)
from shm.universe import xnys_rebalance_dates


def _paper_repo(tmp_path):
    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "data/raw/prices"
    config_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)
    dates = {
        "calendar": "XNYS",
        "dev_start": "2024-01-02",
        "dev_end": "2024-12-31",
        "oos_start": "2025-01-01",
        "oos_end": None,
        "warmup_trading_days": 260,
        "rebalance_every_trading_days": 20,
    }
    params = {
        "signal": {
            "name": "xs_momentum_12_1",
            "lookback_trading_days": 126,
            "skip_trading_days": 21,
            "top_n": 1,
            "weighting": "equal",
            "tie_break": "ticker_asc",
        },
        "eligibility": {
            "min_price_usd": 5,
            "min_adv_usd": 1,
            "adv_window_days": 20,
            "require_full_history": True,
            "min_eligible_count": 2,
        },
        "risk": {
            "trend_filter": {
                "enabled": True,
                "benchmark": "SPY",
                "sma_days": 20,
                "off_exposure": 0,
            },
            "vol_target": {
                "enabled": True,
                "window_days": 5,
                "target_annual_vol": 0.15,
                "max_exposure": 1,
            },
        },
        "execution": {
            "fill": "next_open",
            "fractional_shares_in_backtest": True,
            "cash_yield_annual": 0,
        },
    }
    universe = {
        "frozen_on": "2026-09-04",
        "rule_text": "synthetic fixed paper universe",
        "exclusions": [],
        "tickers": ["AAA", "BBB", "CCC"],
    }
    costs = {
        "model": "fixed_bps_on_notional",
        "per_side_bps": {"default": 10, "stress": 25, "floor": 5},
    }
    for name, payload in {
        "dates.yaml": dates,
        "params.frozen.yaml": params,
        "universe.yaml": universe,
        "costs.yaml": costs,
    }.items():
        (config_dir / name).write_text(yaml.safe_dump(payload), encoding="utf-8")
    bundle = ConfigBundle.model_validate(
        {"dates": dates, "params": params, "costs": costs}
    )
    frozen_eligible = {
        "version": 1,
        "source_phase": "P2",
        "params_hash": compute_params_hash(
            bundle.params.model_dump(mode="json"), bundle.costs.per_side_bps.default
        ),
        "universe_hash": compute_file_hash(config_dir / "universe.yaml"),
        "eligible_count": 2,
        "excluded_count": 1,
        "tickers": ["AAA", "BBB"],
    }
    (config_dir / "p2_eligible.frozen.yaml").write_text(
        yaml.safe_dump(frozen_eligible), encoding="utf-8"
    )

    schedule = xnys_rebalance_dates(
        dates["dev_start"],
        "2026-09-04",
        warmup_trading_days=dates["warmup_trading_days"],
        every_trading_days=dates["rebalance_every_trading_days"],
    )
    as_of = schedule[-1]
    sessions = paper_xnys_window(as_of)
    for ticker, closes in {
        "AAA": np.linspace(100, 200, len(sessions)),
        "BBB": np.linspace(100, 130, len(sessions)),
        "CCC": np.linspace(100, 250, len(sessions)),
        "SPY": np.linspace(100, 150, len(sessions)),
    }.items():
        frame = pd.DataFrame(
            {
                "date": sessions,
                "open": closes,
                "high": closes,
                "low": closes,
                "close": closes,
                "volume": np.full(len(sessions), 100_000, dtype="int64"),
                "adjusted": True,
                "source": "yfinance",
                "downloaded_at": pd.Timestamp("2026-09-04", tz="UTC"),
            }
        )
        frame.to_parquet(cache_dir / f"{ticker}.parquet", index=False)
    return tmp_path, as_of


def test_paper_account_rejects_live_mode_and_invalid_balances() -> None:
    with pytest.raises(PermissionError, match="live endpoints are forbidden"):
        PaperAccount(cash=1_000, mode="live")
    with pytest.raises(ValueError, match="cash"):
        PaperAccount(cash=-0.01)
    with pytest.raises(ValueError, match="integer shares"):
        PaperAccount(cash=1_000, positions={"AAPL": -1})


def test_p2_eligible_manifest_matches_the_frozen_strategy_and_universe() -> None:
    root = Path(__file__).resolve().parents[1]
    config_dir = root / "config"
    payload = yaml.safe_load((config_dir / "p2_eligible.frozen.yaml").read_text())
    bundle = ConfigBundle.model_validate(
        {
            "dates": yaml.safe_load((config_dir / "dates.yaml").read_text()),
            "params": yaml.safe_load((config_dir / "params.frozen.yaml").read_text()),
            "costs": yaml.safe_load((config_dir / "costs.yaml").read_text()),
        }
    )

    assert payload["params_hash"] == "2064365d"
    assert payload["params_hash"] == compute_params_hash(
        bundle.params.model_dump(mode="json"), bundle.costs.per_side_bps.default
    )
    assert payload["universe_hash"] == compute_file_hash(config_dir / "universe.yaml")
    assert payload["eligible_count"] == len(payload["tickers"]) == 48
    assert payload["excluded_count"] == 36


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
    assert write_monthly_report(path, inputs) == path
    path.write_text("partial", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_monthly_report(path, inputs)


def test_paper_rebalance_reads_frozen_local_window_and_writes_ticket(
    tmp_path, monkeypatch
) -> None:
    repo_root, as_of = _paper_repo(tmp_path)
    monkeypatch.setattr("shm.paper.runner._git_sha", lambda root: "abc123")

    result = run_paper_rebalance(PaperAccount(cash=1_000), repo_root, as_of)

    assert result.run_id == f"paper-{as_of:%Y%m%d}-{result.params_hash}"
    assert tuple(result.ranking.index) == ("AAA", "BBB")
    frozen = yaml.safe_load((repo_root / "config/p2_eligible.frozen.yaml").read_text())
    assert result.params_hash == frozen["params_hash"]
    assert result.universe_hash == frozen["universe_hash"]
    assert result.selected == ("AAA",)
    assert result.exposure == pytest.approx(1.0)
    assert result.ticket_path == repo_root / "paper/tickets" / f"{as_of.date()}.csv"
    assert result.ticket_path.exists()
    assert result.snapshot_id
    assert result.log_path == repo_root / "experiments/log.jsonl"
    assert tuple(pd.read_csv(result.ticket_path).columns) == TICKET_COLUMNS
    assert all(ticket.qty == int(ticket.qty) for ticket in result.ticket_plan.tickets)
    assert result.ticket_plan.projected_cash >= 0
    assert not (repo_root / "paper/fills").exists()

    repeated = run_paper_rebalance(PaperAccount(cash=1_000), repo_root, as_of)
    assert repeated.ticket_path == result.ticket_path
    rows = [
        json.loads(line)
        for line in result.log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["mode"] == "paper"
    assert rows[0]["phase"] == "P4"
    assert rows[0]["snapshot_id"] == result.snapshot_id
    assert rows[0]["results"]["account_hash"]
    assert rows[0]["results"]["ranking"] == ["AAA", "BBB"]
    assert "sharpe" not in rows[0]["results"]
    result.ticket_path.write_text("different\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_paper_rebalance(PaperAccount(cash=1_000), repo_root, as_of)


def test_paper_rebalance_rejects_live_mode_and_non_rebalance_dates(tmp_path) -> None:
    repo_root, as_of = _paper_repo(tmp_path)

    with pytest.raises(PermissionError, match="live endpoints"):
        run_paper_rebalance(PaperAccount(cash=1_000), repo_root, as_of, mode="live")

    with pytest.raises(ValueError, match="not an XNYS session"):
        run_paper_rebalance(PaperAccount(cash=1_000), repo_root, "2026-08-22")

    next_session = paper_xnys_window(as_of)[-2]
    with pytest.raises(ValueError, match="not a configured 20-session rebalance date"):
        run_paper_rebalance(PaperAccount(cash=1_000), repo_root, next_session)


def test_paper_rebalance_requires_spy_window_and_minimum_eligible_count(tmp_path) -> None:
    repo_root, as_of = _paper_repo(tmp_path)
    spy_path = repo_root / "data/raw/prices/SPY.parquet"
    spy = pd.read_parquet(spy_path).iloc[:-1]
    spy.to_parquet(spy_path, index=False)
    with pytest.raises(ValueError, match="SPY is missing close"):
        run_paper_rebalance(PaperAccount(cash=1_000), repo_root, as_of)

    repo_root, as_of = _paper_repo(tmp_path / "below-minimum")
    (repo_root / "data/raw/prices/BBB.parquet").unlink()
    with pytest.raises(ValueError, match="eligibility below minimum"):
        run_paper_rebalance(PaperAccount(cash=1_000), repo_root, as_of)
    assert not (repo_root / "paper/tickets" / f"{as_of.date()}.csv").exists()


def test_local_simulator_fills_stock_ticket_at_next_official_open(tmp_path) -> None:
    signal_date = pd.Timestamp("2026-08-19")
    execution_date = pd.Timestamp("2026-08-20")
    ticket_path = write_ticket_csv(
        tmp_path / "paper/tickets/2026-08-19.csv",
        [OrderTicket("AAA", "buy", 5)],
    )
    cache_path = tmp_path / "data/raw/prices/AAA.parquet"
    cache_path.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "date": [execution_date],
            "open": [101.0],
            "high": [102.0],
            "low": [100.0],
            "close": [101.5],
            "volume": [100_000],
            "adjusted": [True],
            "source": ["yfinance"],
            "downloaded_at": [pd.Timestamp("2026-08-20", tz="UTC")],
        }
    ).to_parquet(cache_path, index=False)

    result = simulate_next_open_fills(
        PaperAccount(cash=1_000),
        tmp_path,
        signal_date,
        ticket_path=ticket_path,
    )

    assert result.execution_date == execution_date
    assert result.ingestion.account.cash == pytest.approx(495.0)
    assert result.ingestion.account.positions == {"AAA": 5}
    assert result.ingestion.realized_cost_bps == 0.0
    assert read_fill_csv(result.fill_path)[0].official_open == 101.0
    repeated = simulate_next_open_fills(
        PaperAccount(cash=1_000),
        tmp_path,
        signal_date,
        ticket_path=ticket_path,
    )
    assert repeated.fill_path == result.fill_path


def test_paper_option_overlay_uses_fill_basis_and_saved_ranking(
    tmp_path, monkeypatch
) -> None:
    repo_root, signal_date = _paper_repo(tmp_path)
    calendar = xcals.get_calendar(
        "XNYS",
        start=signal_date - pd.Timedelta("7D"),
        end=signal_date + pd.Timedelta("30D"),
    )
    execution_date = calendar.next_session(signal_date)
    for ticker in ("AAA", "BBB", "CCC"):
        path = repo_root / "data/raw/prices" / f"{ticker}.parquet"
        frame = pd.read_parquet(path)
        row = frame.iloc[-1].copy()
        row["date"] = execution_date
        row[["open", "high", "low", "close"]] = 100.0
        pd.concat([frame, row.to_frame().T], ignore_index=True).to_parquet(
            path,
            index=False,
        )

    write_ticket_csv(
        repo_root / "paper/tickets" / f"{signal_date.date()}.csv",
        [OrderTicket("AAA", "buy", 200)],
    )
    write_fill_csv(
        repo_root / "paper/fills" / f"{execution_date.date()}.csv",
        [Fill("AAA", 200, 100.0, f"{execution_date.date()} 09:30", 100.0)],
    )
    log_path = repo_root / "experiments/log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(
            {
                "mode": "paper",
                "status": "PAPER_TICKET_READY",
                "period": {"end": str(signal_date.date())},
                "results": {
                    "ranking": ["AAA", "BBB", "CCC"],
                    "selected": ["AAA"],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    received: dict[str, object] = {}
    plan = OverlayPlan(
        orders=(
            OptionOrder(
                underlying="AAA",
                strategy="covered_call",
                contract_symbol="AAA261016C00110000",
                expiration=date(2026, 10, 16),
                strike=110.0,
                contracts=2,
                bid=1.0,
                ask=1.1,
                delta=0.25,
                delta_source="chain",
                max_loss=19_800.0,
                upside_cap=110.0,
                cash_usage=0.0,
                covered_shares=200,
            ),
        ),
        skipped=(SkippedOverlay("BBB", "cash_secured_put", "no liquid put"),),
        summary=OverlaySummary(max_loss=19_800.0, cash_usage=0.0, csp_notional=0.0),
    )

    def build(**kwargs):
        received.update(kwargs)
        return plan

    monkeypatch.setattr("shm.paper.option_overlay.build_overlay_plan", build)
    account = PaperAccount(cash=80_000.0, positions={"AAA": 200})

    result = run_paper_option_overlay(
        account,
        repo_root,
        signal_date,
        execution_date,
    )

    assert received["holdings"][0].cost_basis_per_share == 100.0
    assert [candidate.ticker for candidate in received["candidates"]] == ["BBB", "CCC"]
    assert received["portfolio_equity"] == 100_000.0
    assert result.ticket_path.name == f"{execution_date.date()}-options.csv"
    assert result.ticket_path.exists()
    audit = json.loads(result.audit_path.read_text(encoding="utf-8"))
    assert audit["paper_only"] is True
    assert audit["orders"][0]["strategy"] == "covered_call"
    repeated = run_paper_option_overlay(
        account,
        repo_root,
        signal_date,
        execution_date,
    )
    assert repeated.ticket_path == result.ticket_path


def test_paper_status_counts_only_complete_cycles(tmp_path) -> None:
    repo_root, _ = _paper_repo(tmp_path)
    (repo_root / "paper").mkdir(exist_ok=True)
    (repo_root / "paper/p4.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "paper",
                "provider": "local_offline_simulator",
                "forward_test_start": "2026-09-05",
            }
        ),
        encoding="utf-8",
    )

    initial = build_paper_progress(repo_root)
    signal_date = initial.next_rebalance_date
    calendar = xcals.get_calendar(
        "XNYS",
        start=signal_date - pd.Timedelta("7D"),
        end=signal_date + pd.Timedelta("30D"),
    )
    execution_date = calendar.next_session(signal_date)
    write_ticket_csv(
        repo_root / "paper/tickets" / f"{signal_date.date()}.csv",
        [OrderTicket("AAA", "buy", 1)],
    )
    write_fill_csv(
        repo_root / "paper/fills" / f"{execution_date.date()}.csv",
        [Fill("AAA", 1, 100.0, f"{execution_date.date()} 09:30", 100.0)],
    )
    account_path = repo_root / "paper/accounts" / f"{execution_date.date()}.json"
    account_path.parent.mkdir(parents=True, exist_ok=True)
    account_path.write_text(
        json.dumps(
            {
                "as_of": str(execution_date.date()),
                "cash": 900.0,
                "mode": "paper",
                "positions": {"AAA": 1},
            }
        ),
        encoding="utf-8",
    )
    report_path = repo_root / "reports/paper-2026-09.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("observed\n", encoding="utf-8")

    after_first = build_paper_progress(repo_root)
    pending_signal = after_first.next_rebalance_date
    write_ticket_csv(
        repo_root / "paper/tickets" / f"{pending_signal.date()}.csv",
        [OrderTicket("BBB", "buy", 1)],
    )

    progress = build_paper_progress(repo_root)

    assert progress.completed_cycles == (str(signal_date.date()),)
    assert progress.pending_cycles == (str(pending_signal.date()),)
    assert progress.monthly_reports == ("2026-09",)
    assert progress.p4_evidence_complete is False
    assert progress.gate_ready is False
    assert "paper cycles 1/3" in progress.gate_blockers
    assert "monthly reports 1/3" in progress.gate_blockers
    assert len(progress.missing_owner_notes) == 4


def test_paper_status_advances_past_recorded_missed_cycle(tmp_path) -> None:
    repo_root, _ = _paper_repo(tmp_path)
    (repo_root / "paper").mkdir(exist_ok=True)
    (repo_root / "paper/p4.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "paper",
                "provider": "local_offline_simulator",
                "forward_test_start": "2026-09-05",
            }
        ),
        encoding="utf-8",
    )
    initial = build_paper_progress(repo_root)
    marker = repo_root / "paper/missed" / f"{initial.next_rebalance_date.date()}.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}\n", encoding="utf-8")

    progress = build_paper_progress(repo_root)

    assert progress.missed_cycles == (str(initial.next_rebalance_date.date()),)
    assert progress.next_rebalance_date > initial.next_rebalance_date


def test_paper_status_does_not_leave_a_missed_fill_pending(tmp_path) -> None:
    repo_root, _ = _paper_repo(tmp_path)
    (repo_root / "paper").mkdir(exist_ok=True)
    (repo_root / "paper/p4.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "paper",
                "provider": "local_offline_simulator",
                "forward_test_start": "2026-09-05",
            }
        ),
        encoding="utf-8",
    )
    initial = build_paper_progress(repo_root)
    signal = initial.next_rebalance_date
    write_ticket_csv(
        repo_root / "paper/tickets" / f"{signal.date()}.csv",
        [OrderTicket("AAA", "buy", 1)],
    )
    marker = repo_root / "paper/missed" / f"{signal.date()}-fill.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}\n", encoding="utf-8")

    progress = build_paper_progress(repo_root)

    assert progress.pending_cycles == ()
    assert progress.missed_cycles == (str(signal.date()),)
