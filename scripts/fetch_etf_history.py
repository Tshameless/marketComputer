from __future__ import annotations

import argparse
from pathlib import Path

from a_share_quant.config import filter_universe, load_project_config
from a_share_quant.data import fetch_fund_history, fetch_lof_spot, save_history, save_spot_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch A-share ETF daily history with AKShare.")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parents[1] / "config" / "universe.yaml"),
        help="Path to the universe YAML config.",
    )
    parser.add_argument("--start-date", help="Override fetch start date, format YYYYMMDD.")
    parser.add_argument("--end-date", help="Override fetch end date, format YYYYMMDD.")
    parser.add_argument("--group", help="Only fetch ETFs from the specified group.")
    parser.add_argument("--strategy-tag", help="Only fetch ETFs with the specified strategy tag.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    config = load_project_config(args.config)

    start_date = args.start_date or config["data"]["start_date"]
    end_date = args.end_date or config["data"]["end_date"]
    adjust = config["data"].get("adjust", "qfq")
    cache_dir = root / "data" / "cache"
    universe = filter_universe(config["universe"], group=args.group, strategy_tag=args.strategy_tag)

    etf_snapshot_path = save_spot_snapshot(root / "data" / "etf_spot_snapshot.csv")
    print(f"saved ETF spot snapshot -> {etf_snapshot_path}")
    try:
        lof_snapshot = fetch_lof_spot()
        lof_snapshot_path = root / "data" / "lof_spot_snapshot.csv"
        lof_snapshot.to_csv(lof_snapshot_path, index=False, encoding="utf-8-sig")
        print(f"saved LOF spot snapshot -> {lof_snapshot_path}")
    except Exception as error:
        print(f"skip LOF spot snapshot: {error}")
    print(f"fetch universe size: {len(universe)}")

    succeeded = 0
    failures: list[str] = []
    for item in universe:
        symbol = item["symbol"]
        name = item["name"]
        instrument_type = item.get("instrument_type", "ETF")
        try:
            frame = fetch_fund_history(
                symbol=symbol,
                instrument_type=instrument_type,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            output_path = save_history(frame, cache_dir / f"{symbol}.csv")
            succeeded += 1
            print(f"saved {symbol} {name} [{instrument_type}] -> {output_path}")
        except Exception as error:
            failures.append(symbol)
            print(f"failed {symbol} {name} [{instrument_type}]: {error}")

    print(f"fetch completed: {succeeded} succeeded, {len(failures)} failed")
    if failures:
        raise RuntimeError(f"failed symbols: {', '.join(failures)}")


if __name__ == "__main__":
    main()
