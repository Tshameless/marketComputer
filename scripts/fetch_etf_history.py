from __future__ import annotations

import argparse
from pathlib import Path

from a_share_quant.config import load_project_config
from a_share_quant.data import fetch_etf_history, save_history, save_spot_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch A-share ETF daily history with AKShare.")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parents[1] / "config" / "universe.yaml"),
        help="Path to the universe YAML config.",
    )
    parser.add_argument("--start-date", help="Override fetch start date, format YYYYMMDD.")
    parser.add_argument("--end-date", help="Override fetch end date, format YYYYMMDD.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    config = load_project_config(args.config)

    start_date = args.start_date or config["data"]["start_date"]
    end_date = args.end_date or config["data"]["end_date"]
    adjust = config["data"].get("adjust", "qfq")
    cache_dir = root / "data" / "cache"

    snapshot_path = save_spot_snapshot(root / "data" / "etf_spot_snapshot.csv")
    print(f"saved ETF spot snapshot -> {snapshot_path}")

    for item in config["universe"]:
        symbol = item["symbol"]
        name = item["name"]
        frame = fetch_etf_history(symbol=symbol, start_date=start_date, end_date=end_date, adjust=adjust)
        output_path = save_history(frame, cache_dir / f"{symbol}.csv")
        print(f"saved {symbol} {name} -> {output_path}")


if __name__ == "__main__":
    main()
