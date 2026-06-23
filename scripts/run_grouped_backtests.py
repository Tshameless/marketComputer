from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from a_share_quant.backtest import run_rotation_backtest, write_report
from a_share_quant.config import filter_universe, load_project_config
from a_share_quant.data import build_close_matrix, load_cached_histories


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run batch ETF rotation backtests by group or strategy tag.")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parents[1] / "config" / "universe.yaml"),
        help="Path to the universe YAML config.",
    )
    parser.add_argument(
        "--group-field",
        choices=["group", "strategy_tag"],
        default="group",
        help="Universe field used to batch the backtests.",
    )
    parser.add_argument(
        "--values",
        help="Optional comma-separated subset of group values to run, such as broad,growth.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "reports" / "rotation"),
        help="Directory for backtest outputs.",
    )
    parser.add_argument("--include-disabled", action="store_true", help="Include disabled watchlist rows.")
    return parser.parse_args()


def parse_requested_values(raw_values: str | None) -> list[str] | None:
    if not raw_values:
        return None
    values = [value.strip() for value in raw_values.split(",") if value.strip()]
    return values or None


def collect_field_values(universe: list[dict[str, str]], field_name: str) -> list[str]:
    values = sorted({item.get(field_name, "").strip() for item in universe if item.get(field_name, "").strip()})
    if not values:
        raise ValueError(f"no non-empty values found for field '{field_name}'")
    return values


def sanitize_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "_", value).strip("_") or "default"


def run_single_batch(
    root: Path,
    config: dict,
    field_name: str,
    field_value: str,
    output_dir: Path,
    include_disabled: bool,
) -> dict[str, object]:
    if field_name == "group":
        universe = filter_universe(config["universe"], group=field_value, include_disabled=include_disabled)
    else:
        universe = filter_universe(
            config["universe"],
            strategy_tag=field_value,
            include_disabled=include_disabled,
        )

    symbols = [item["symbol"] for item in universe]
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
    write_report(result, output_dir)
    summary_row: dict[str, object] = {
        "field": field_name,
        "value": field_value,
        "instrument_count": len(symbols),
        "symbols": ",".join(symbols),
    }
    summary_row.update(result.metrics)
    return summary_row


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    config = load_project_config(args.config)
    requested_values = parse_requested_values(args.values)
    base_universe = config["universe"] if args.include_disabled else [
        item for item in config["universe"] if item.get("enabled", True)
    ]
    available_values = collect_field_values(base_universe, args.group_field)
    values_to_run = requested_values or available_values

    missing_values = sorted(set(values_to_run) - set(available_values))
    if missing_values:
        raise ValueError(f"requested values not found in watchlist: {', '.join(missing_values)}")

    output_root = Path(args.output_dir)
    summary_rows: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for field_value in values_to_run:
        folder_name = f"{args.group_field}_{sanitize_name(field_value)}"
        report_dir = output_root / folder_name
        try:
            summary_row = run_single_batch(
                root=root,
                config=config,
                field_name=args.group_field,
                field_value=field_value,
                output_dir=report_dir,
                include_disabled=args.include_disabled,
            )
            summary_rows.append(summary_row)
            print(f"completed {args.group_field}={field_value} -> {report_dir}")
        except Exception as error:
            failures.append({"field": args.group_field, "value": field_value, "error": str(error)})
            print(f"failed {args.group_field}={field_value}: {error}")

    if not summary_rows:
        raise RuntimeError("all grouped backtests failed")

    summary_frame = pd.DataFrame(summary_rows).sort_values("value").reset_index(drop=True)
    summary_csv = output_root / f"summary_by_{args.group_field}.csv"
    summary_json = output_root / f"summary_by_{args.group_field}.json"
    summary_frame.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    with summary_json.open("w", encoding="utf-8") as handle:
        json.dump(summary_rows, handle, ensure_ascii=False, indent=2)

    print(f"summary csv -> {summary_csv}")
    print(f"summary json -> {summary_json}")
    print(summary_frame.to_string(index=False))

    if failures:
        raise RuntimeError(f"grouped backtests failed for: {', '.join(item['value'] for item in failures)}")


if __name__ == "__main__":
    main()
