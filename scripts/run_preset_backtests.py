from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from a_share_quant.backtest import run_rotation_backtest, write_report
from a_share_quant.config import apply_universe_filters, load_project_config, load_yaml
from a_share_quant.data import build_close_matrix, load_cached_histories


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run named preset backtests from config/presets.yaml.")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parents[1] / "config" / "universe.yaml"),
        help="Path to the universe YAML config.",
    )
    parser.add_argument(
        "--presets-file",
        default=str(Path(__file__).resolve().parents[1] / "config" / "presets.yaml"),
        help="Path to the preset YAML file.",
    )
    parser.add_argument("--preset", help="Run a single preset by name.")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "reports" / "presets"),
        help="Directory for preset backtest outputs.",
    )
    parser.add_argument("--include-disabled", action="store_true", help="Include disabled watchlist rows.")
    return parser.parse_args()


def sanitize_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "_", value).strip("_") or "default"


def load_presets(path: str | Path) -> dict[str, dict]:
    raw = load_yaml(path)
    presets = raw.get("presets", {})
    if not presets:
        raise ValueError("no presets found in presets file")
    return presets


def build_constituents_frame(universe: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(universe).copy()
    sort_columns: list[str] = []
    ascending: list[bool] = []
    if "priority" in frame.columns:
        sort_columns.append("priority")
        ascending.append(True)
    sort_columns.append("symbol")
    ascending.append(True)
    return frame.sort_values(sort_columns, ascending=ascending, na_position="last").reset_index(drop=True)


def summarize_universe_metadata(universe: list[dict[str, object]]) -> dict[str, object]:
    frame = build_constituents_frame(universe)
    summary: dict[str, object] = {}

    if "priority" in frame.columns:
        priority_series = pd.to_numeric(frame["priority"], errors="coerce").dropna()
        if not priority_series.empty:
            summary["priority_min"] = int(priority_series.min())
            summary["priority_max"] = int(priority_series.max())
            summary["priority_avg"] = round(float(priority_series.mean()), 4)
            top_priority = frame[frame["priority"] == priority_series.min()]["symbol"].astype(str).tolist()
            summary["top_priority_symbols"] = ",".join(top_priority)

    if "target_weight_hint" in frame.columns:
        weight_series = pd.to_numeric(frame["target_weight_hint"], errors="coerce").dropna()
        if not weight_series.empty:
            summary["target_weight_hint_sum"] = round(float(weight_series.sum()), 6)
            summary["target_weight_hint_avg"] = round(float(weight_series.mean()), 6)

    return summary


def run_single_preset(
    root: Path,
    config: dict,
    preset_name: str,
    preset_filters: dict,
    output_dir: Path,
    include_disabled: bool,
) -> dict[str, object]:
    universe = apply_universe_filters(
        config["universe"],
        groups=preset_filters.get("groups"),
        strategy_tags=preset_filters.get("strategy_tags"),
        instrument_types=preset_filters.get("instrument_types"),
        symbols=preset_filters.get("symbols"),
        include_disabled=include_disabled,
    )
    constituents = build_constituents_frame(universe)
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
    constituents.to_csv(output_dir / "constituents.csv", index=False, encoding="utf-8-sig")
    summary_row: dict[str, object] = {
        "preset": preset_name,
        "instrument_count": len(symbols),
        "symbols": ",".join(symbols),
    }
    summary_row.update(summarize_universe_metadata(universe))
    summary_row.update(result.metrics)
    return summary_row


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    config = load_project_config(args.config)
    presets = load_presets(args.presets_file)
    if args.preset and args.preset not in presets:
        raise ValueError(f"unknown preset: {args.preset}")
    selected_presets = {args.preset: presets[args.preset]} if args.preset else presets

    output_root = Path(args.output_dir)
    summary_rows: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for preset_name, preset_filters in selected_presets.items():
        report_dir = output_root / sanitize_name(preset_name)
        try:
            summary_row = run_single_preset(
                root=root,
                config=config,
                preset_name=preset_name,
                preset_filters=preset_filters,
                output_dir=report_dir,
                include_disabled=args.include_disabled,
            )
            summary_rows.append(summary_row)
            print(f"completed preset={preset_name} -> {report_dir}")
        except Exception as error:
            failures.append({"preset": preset_name, "error": str(error)})
            print(f"failed preset={preset_name}: {error}")

    if not summary_rows:
        raise RuntimeError("all preset backtests failed")

    summary_frame = pd.DataFrame(summary_rows).sort_values("preset").reset_index(drop=True)
    summary_csv = output_root / "summary_by_preset.csv"
    summary_json = output_root / "summary_by_preset.json"
    summary_frame.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    with summary_json.open("w", encoding="utf-8") as handle:
        json.dump(summary_rows, handle, ensure_ascii=False, indent=2)

    print(f"summary csv -> {summary_csv}")
    print(f"summary json -> {summary_json}")
    print(summary_frame.to_string(index=False))

    if failures:
        raise RuntimeError(f"preset backtests failed for: {', '.join(item['preset'] for item in failures)}")


if __name__ == "__main__":
    main()
