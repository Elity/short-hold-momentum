from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError
from yaml import YAMLError

from shm.config import load_config_bundle, load_universe_config
from shm.paper import (
    PaperAccount,
    generate_monthly_report,
    ingest_fills,
    read_fill_csv,
    read_ticket_csv,
    run_paper_option_overlay,
    run_paper_rebalance,
    simulate_next_open_fills,
)
from shm.runner import run_development_backtest, update_development_data


def _load_paper_account(path: Path) -> PaperAccount:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("paper account snapshot must be a JSON object")
    return PaperAccount(
        cash=payload["cash"],
        positions=payload.get("positions", {}),
        mode=payload.get("mode", "paper"),
    )


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _write_paper_account(
    path: Path,
    account: PaperAccount,
    *,
    as_of: object | None = None,
) -> Path:
    payload: dict[str, Any] = {
        "mode": account.mode,
        "cash": account.cash,
        "positions": dict(sorted(account.positions.items())),
    }
    if as_of is not None:
        payload["as_of"] = str(pd.Timestamp(as_of).date())
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shm")
    commands = parser.add_subparsers(dest="command", required=True)

    config = commands.add_parser("config", help="Configuration operations")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    validate = config_commands.add_parser("validate", help="Validate P0 config files")
    validate.add_argument("--config-dir", type=Path, default=Path("config"))
    validate.add_argument(
        "--require-universe",
        action="store_true",
        help="also require and validate the owner-controlled universe.yaml",
    )

    data = commands.add_parser("data", help="Market-data cache operations")
    data_commands = data.add_subparsers(dest="data_command", required=True)
    update = data_commands.add_parser("update", help="Update the market-data cache")
    update.add_argument("--config-dir", type=Path, default=Path("config"))
    update.add_argument("--cache-dir", type=Path, default=Path("data/raw/prices"))
    update.add_argument("--skip-pit", action="store_true", help="skip CHK-02 reference ticker caches")
    update.add_argument(
        "--through-oos",
        action="store_true",
        help="update through the configured OOS end or the latest available date",
    )

    backtest = commands.add_parser("backtest", help="Research backtest operations")
    backtest_commands = backtest.add_subparsers(dest="backtest_command", required=True)
    run = backtest_commands.add_parser("run", help="Run an approved development or OOS backtest")
    run.add_argument("--repo-root", type=Path, default=Path("."))
    run.add_argument("--prereg", type=Path, default=Path("experiments/prereg/V00.md"))
    run.add_argument("--unlock-oos", action="store_true", help="run the selected OOS period")
    run.add_argument("--reason", help="required audit reason when unlocking OOS")

    paper = commands.add_parser("paper", help="Offline paper-trading operations")
    paper_commands = paper.add_subparsers(dest="paper_command", required=True)
    rebalance = paper_commands.add_parser(
        "rebalance", help="Generate a paper-only whole-share ticket"
    )
    rebalance.add_argument("--repo-root", type=Path, default=Path("."))
    rebalance.add_argument("--account", type=Path, required=True)
    rebalance.add_argument("--as-of", required=True, help="completed XNYS signal date")
    fills = paper_commands.add_parser(
        "ingest-fills", help="Apply confirmed paper fills to an account snapshot"
    )
    fills.add_argument("--repo-root", type=Path, default=Path("."))
    fills.add_argument("--account", type=Path, required=True)
    fills.add_argument("--tickets", type=Path, required=True)
    fills.add_argument("--fills", type=Path, required=True)
    fills.add_argument("--output-account", type=Path, required=True)
    simulate = paper_commands.add_parser(
        "simulate-fills", help="Fill a stock paper ticket at the next official open"
    )
    simulate.add_argument("--repo-root", type=Path, default=Path("."))
    simulate.add_argument("--account", type=Path, required=True)
    simulate.add_argument("--signal-date", required=True)
    simulate.add_argument("--tickets", type=Path)
    simulate.add_argument("--output-account", type=Path, required=True)
    monthly = paper_commands.add_parser(
        "monthly-report", help="Generate an observed paper-versus-model monthly report"
    )
    monthly.add_argument("--repo-root", type=Path, default=Path("."))
    monthly.add_argument("--month", required=True, help="completed month in YYYY-MM format")
    options = paper_commands.add_parser(
        "option-overlay", help="Generate a paper-only CC/CSP draft after stock fills"
    )
    options.add_argument("--repo-root", type=Path, default=Path("."))
    options.add_argument("--account", type=Path, required=True)
    options.add_argument("--signal-date", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "config" and args.config_command == "validate":
        try:
            load_config_bundle(args.config_dir)
            if args.require_universe:
                load_universe_config(args.config_dir)
        except (FileNotFoundError, ValueError, ValidationError, YAMLError) as exc:
            print(f"configuration invalid: {exc}", file=sys.stderr)
            return 2
        files = "dates.yaml, params.yaml, costs.yaml"
        if args.require_universe:
            files += ", universe.yaml"
        print(f"configuration valid: {files}")
        return 0
    if args.command == "data" and args.data_command == "update":
        try:
            summary = update_development_data(
                config_dir=args.config_dir,
                cache_dir=args.cache_dir,
                include_pit=not args.skip_pit,
                through_oos=args.through_oos,
            )
        except Exception as exc:
            print(f"data update failed: {exc}", file=sys.stderr)
            return 2
        failure_ratio = summary.core_failures / summary.core_total if summary.core_total else 1.0
        print(
            "data update complete: "
            f"core_total={summary.core_total}, core_failures={summary.core_failures}, "
            f"core_ratio={failure_ratio:.2%}, pit_total={summary.pit_total}, "
            f"pit_failures={summary.pit_failures}"
        )
        return 0 if failure_ratio < 0.05 else 2
    if args.command == "backtest" and args.backtest_command == "run":
        try:
            root = args.repo_root.resolve()
            prereg = args.prereg if args.prereg.is_absolute() else root / args.prereg
            outcome = run_development_backtest(
                repo_root=root,
                prereg_path=prereg,
                unlock_oos=args.unlock_oos,
                reason=args.reason,
            )
        except Exception as exc:
            print(f"backtest failed: {exc}", file=sys.stderr)
            return 2
        print(
            f"backtest complete: run_id={outcome.run_id}, status={outcome.status}, "
            f"report={outcome.report_path}"
        )
        return 0
    if args.command == "paper" and args.paper_command == "rebalance":
        try:
            root = args.repo_root.resolve()
            account_path = _resolve(root, args.account)
            account = _load_paper_account(account_path)
            outcome = run_paper_rebalance(account, root, args.as_of)
        except Exception as exc:
            print(f"paper rebalance failed: {exc}", file=sys.stderr)
            return 2
        print(
            "paper ticket ready: "
            f"as_of={outcome.as_of.date()}, params_hash={outcome.params_hash}, "
            f"selected={len(outcome.selected)}, tickets={len(outcome.ticket_plan.tickets)}, "
            f"path={outcome.ticket_path}"
        )
        return 0
    if args.command == "paper" and args.paper_command == "ingest-fills":
        try:
            root = args.repo_root.resolve()
            account = _load_paper_account(_resolve(root, args.account))
            tickets = read_ticket_csv(_resolve(root, args.tickets))
            fills = read_fill_csv(_resolve(root, args.fills))
            outcome = ingest_fills(account, tickets, fills)
            account_as_of = max((fill.fill_time for fill in fills), default=None)
            output = _write_paper_account(
                _resolve(root, args.output_account),
                outcome.account,
                as_of=account_as_of,
            )
        except Exception as exc:
            print(f"paper fill ingestion failed: {exc}", file=sys.stderr)
            return 2
        cost = (
            "not observed"
            if outcome.realized_cost_bps is None
            else f"{outcome.realized_cost_bps:.2f} bps"
        )
        print(
            "paper fills recorded: "
            f"fills={len(outcome.applied_fills)}, realized_cost={cost}, "
            f"cash={outcome.account.cash:.2f}, account={output}"
        )
        return 0
    if args.command == "paper" and args.paper_command == "simulate-fills":
        try:
            root = args.repo_root.resolve()
            account = _load_paper_account(_resolve(root, args.account))
            ticket_path = None if args.tickets is None else _resolve(root, args.tickets)
            outcome = simulate_next_open_fills(
                account,
                root,
                args.signal_date,
                ticket_path=ticket_path,
            )
            output = _write_paper_account(
                _resolve(root, args.output_account),
                outcome.ingestion.account,
                as_of=outcome.execution_date,
            )
        except Exception as exc:
            print(f"paper fill simulation failed: {exc}", file=sys.stderr)
            return 2
        print(
            "paper fills simulated: "
            f"execution_date={outcome.execution_date.date()}, "
            f"fills={len(outcome.ingestion.applied_fills)}, "
            f"cash={outcome.ingestion.account.cash:.2f}, fills_path={outcome.fill_path}, "
            f"account={output}"
        )
        return 0
    if args.command == "paper" and args.paper_command == "monthly-report":
        try:
            outcome = generate_monthly_report(args.repo_root.resolve(), args.month)
        except Exception as exc:
            print(f"paper monthly report failed: {exc}", file=sys.stderr)
            return 2
        print(
            "paper monthly report ready: "
            f"month={outcome.inputs.month}, path={outcome.report_path}"
        )
        return 0
    if args.command == "paper" and args.paper_command == "option-overlay":
        try:
            root = args.repo_root.resolve()
            account_path = _resolve(root, args.account)
            account = _load_paper_account(account_path)
            payload = json.loads(account_path.read_text(encoding="utf-8"))
            outcome = run_paper_option_overlay(
                account,
                root,
                args.signal_date,
                payload["as_of"],
            )
        except Exception as exc:
            print(f"paper option overlay failed: {exc}", file=sys.stderr)
            return 2
        print(
            "paper option overlay ready: "
            f"as_of={outcome.as_of.date()}, orders={len(outcome.plan.orders)}, "
            f"skipped={len(outcome.plan.skipped)}, path={outcome.ticket_path}"
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
