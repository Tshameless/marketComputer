from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    weights: pd.DataFrame
    metrics: dict[str, float]


def run_rotation_backtest(
    close_prices: pd.DataFrame,
    start_date: str,
    end_date: str,
    lookback_days: int,
    rebalance_every: int,
    top_n: int,
    min_momentum: float,
    commission_bps: float,
    slippage_bps: float,
    initial_capital: float,
) -> BacktestResult:
    price_frame = close_prices.sort_index().loc[start_date:end_date].ffill().dropna(how="all")
    if price_frame.empty:
        raise ValueError("no price data available in requested date range")

    asset_returns = price_frame.pct_change().fillna(0.0)
    momentum = price_frame.pct_change(lookback_days)

    current_weights = pd.Series(0.0, index=price_frame.columns, dtype=float)
    portfolio_value = float(initial_capital)
    equity_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []

    fee_rate = (commission_bps + slippage_bps) / 10000.0

    for idx, current_date in enumerate(price_frame.index):
        if idx >= lookback_days and (idx - lookback_days) % rebalance_every == 0:
            scores = momentum.iloc[idx].dropna().sort_values(ascending=False)
            target_weights = pd.Series(0.0, index=price_frame.columns, dtype=float)
            selected = scores[scores > min_momentum].head(top_n)
            if not selected.empty:
                target_weights.loc[selected.index] = 1.0 / len(selected)

            turnover = float((target_weights - current_weights).abs().sum())
            portfolio_value *= max(0.0, 1.0 - turnover * fee_rate)
            current_weights = target_weights

        daily_return = float((current_weights * asset_returns.iloc[idx]).sum())
        portfolio_value *= 1.0 + daily_return

        equity_rows.append(
            {
                "date": current_date,
                "portfolio_value": portfolio_value,
                "daily_return": daily_return,
            }
        )

        weight_record = {"date": current_date}
        weight_record.update({symbol: float(weight) for symbol, weight in current_weights.items()})
        weight_rows.append(weight_record)

    equity_curve = pd.DataFrame(equity_rows).set_index("date")
    weights = pd.DataFrame(weight_rows).set_index("date")
    metrics = calculate_metrics(equity_curve["portfolio_value"], equity_curve["daily_return"])
    return BacktestResult(equity_curve=equity_curve, weights=weights, metrics=metrics)


def calculate_metrics(equity: pd.Series, daily_returns: pd.Series) -> dict[str, float]:
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    periods = max(len(equity), 1)
    annualized_return = float((equity.iloc[-1] / equity.iloc[0]) ** (TRADING_DAYS_PER_YEAR / periods) - 1.0)
    annualized_volatility = float(daily_returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))
    sharpe = 0.0
    if annualized_volatility > 0:
        sharpe = annualized_return / annualized_volatility

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_drawdown = float(drawdown.min())
    win_rate = float((daily_returns > 0).mean())

    return {
        "total_return": round(total_return, 6),
        "annualized_return": round(annualized_return, 6),
        "annualized_volatility": round(annualized_volatility, 6),
        "sharpe": round(sharpe, 6),
        "max_drawdown": round(max_drawdown, 6),
        "win_rate": round(win_rate, 6),
    }


def write_report(result: BacktestResult, output_dir: str | Path) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    result.equity_curve.to_csv(output_path / "equity_curve.csv", encoding="utf-8-sig")
    result.weights.to_csv(output_path / "weights.csv", encoding="utf-8-sig")
    with (output_path / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(result.metrics, handle, ensure_ascii=False, indent=2)

    figure = plt.figure(figsize=(10, 5))
    axis = figure.add_subplot(111)
    result.equity_curve["portfolio_value"].plot(ax=axis, title="ETF Rotation Equity Curve")
    axis.set_ylabel("Portfolio Value")
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(output_path / "equity_curve.png", dpi=160)
    plt.close(figure)
