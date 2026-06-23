from __future__ import annotations

import argparse
import json
from pathlib import Path

from a_share_quant.backtest import run_rotation_backtest, write_report
from a_share_quant.config import load_project_config
from a_share_quant.data import build_close_matrix, load_cached_histories


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the sample ETF rotation backtest.")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parents[1] / "config" / "universe.yaml"),
        help="Path to the universe YAML config.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "reports" / "rotation"),
        help="Directory for backtest outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    config = load_project_config(args.config)
    symbols = [item["symbol"] for item in config["universe"]]
    history_map = load_cached_histories(root / "data" / "cache", symbols)
    close_matrix = build_close_matrix(history_map)

    settings = config["backtest"]
    result = run_rotation_backtest(
        close_prices=close_matrix,
        start_date=settings["start_date"],
        end_date=settings["end_date"],
        lookback_days=int(settings["lookback_days"]),
        rebalance_every=int(settings["rebalance_every"]),
        top_n=int(settings["top_n"]),
        min_momentum=float(settings["min_momentum"]),
        commission_bps=float(settings["commission_bps"]),
        slippage_bps=float(settings["slippage_bps"]),
        initial_capital=float(settings["initial_capital"]),
    )
    write_report(result, args.output_dir)
    print(json.dumps(result.metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
