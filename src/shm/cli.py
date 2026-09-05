from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError
from yaml import YAMLError

from shm.config import load_config_bundle, load_universe_config
from shm.runner import run_development_backtest, update_development_data


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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
