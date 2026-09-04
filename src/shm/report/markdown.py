from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from shm.report.metrics import PerformanceMetrics


def _pct(value: float) -> str:
    return f"{value:.2%}"


def _sparkline(values: pd.Series, width: int = 60) -> str:
    bars = "▁▂▃▄▅▆▇█"
    clean = values.dropna().astype(float)
    if clean.empty:
        return "(no data)"
    if len(clean) > width:
        positions = [round(index * (len(clean) - 1) / (width - 1)) for index in range(width)]
        clean = clean.iloc[positions]
    low, high = float(clean.min()), float(clean.max())
    if high == low:
        return bars[0] * len(clean)
    return "".join(bars[min(7, int((value - low) / (high - low) * 7))] for value in clean)


def render_report(
    *,
    run_id: str,
    status: str,
    warnings: list[str],
    hypothesis: str,
    expected: str,
    verdict: str,
    metadata: Mapping[str, Any],
    params: Mapping[str, Any],
    strategy: PerformanceMetrics,
    stress: PerformanceMetrics,
    benchmark: PerformanceMetrics,
    strategy_yearly: pd.Series,
    benchmark_yearly: pd.Series,
    equity: pd.Series,
    exposure: pd.Series,
    checks: Mapping[str, Any],
    reproduce: str,
) -> str:
    warning_text = ", ".join(warnings) if warnings else "none"
    lines = [
        f"# {run_id} — {status}",
        "",
        f"Warnings: {warning_text}",
        "",
        "## Hypothesis",
        "",
        f"- Hypothesis: {hypothesis}",
        f"- Expected: {expected}",
        f"- Verdict: {verdict}",
        "",
        "## Run identity",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in metadata.items())
    lines.extend(
        [
            "",
            "## Parameters",
            "",
            "```json",
            json.dumps(params, indent=2, sort_keys=True, default=str),
            "```",
            "",
            "## Metrics",
            "",
            "| Metric | Strategy 10 bps | Strategy 25 bps | SPY |",
            "|---|---:|---:|---:|",
            f"| CAGR | {_pct(strategy.cagr)} | {_pct(stress.cagr)} | {_pct(benchmark.cagr)} |",
            f"| MaxDD | {_pct(strategy.maxdd)} | {_pct(stress.maxdd)} | {_pct(benchmark.maxdd)} |",
            f"| Sharpe | {strategy.sharpe:.3f} | {stress.sharpe:.3f} | {benchmark.sharpe:.3f} |",
            f"| Calmar | {strategy.calmar:.3f} | {stress.calmar:.3f} | {benchmark.calmar:.3f} |",
            f"| Annual turnover | {_pct(strategy.turnover)} | {_pct(stress.turnover)} | {_pct(benchmark.turnover)} |",
            f"| Average exposure | {_pct(strategy.avg_exposure)} | {_pct(stress.avg_exposure)} | {_pct(benchmark.avg_exposure)} |",
            f"| Average holding days | {strategy.avg_holding_days:.1f} | {stress.avg_holding_days:.1f} | {benchmark.avg_holding_days:.1f} |",
            "",
            "## Calendar-year returns",
            "",
            "| Year | Strategy | SPY |",
            "|---:|---:|---:|",
        ]
    )
    years = sorted(set(strategy_yearly.index) | set(benchmark_yearly.index))
    for year in years:
        strategy_value = strategy_yearly.get(year, float("nan"))
        benchmark_value = benchmark_yearly.get(year, float("nan"))
        lines.append(f"| {year} | {_pct(strategy_value)} | {_pct(benchmark_value)} |")
    lines.extend(
        [
            "",
            "## Daily equity and exposure",
            "",
            f"- Equity: `{_sparkline(equity)}`",
            f"- Exposure: `{_sparkline(exposure)}`",
            "",
            "## Automated checks",
            "",
            "| Check | Result | Detail |",
            "|---|---|---|",
        ]
    )
    for name in sorted(checks):
        result = checks[name]
        if hasattr(result, "status"):
            check_status, detail = result.status, result.detail
        else:
            check_status, detail = result, ""
        lines.append(f"| {name} | {check_status} | {detail} |")
    lines.extend(["", "## Reproduce", "", f"`{reproduce}`", ""])
    return "\n".join(lines)


def write_report(path: Path | str, content: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
