from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from a_share_quant.config import apply_universe_filters, load_project_config, load_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a lightweight research dashboard from watchlist metadata and preset summaries.")
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
    parser.add_argument(
        "--preset-reports-dir",
        default=str(Path(__file__).resolve().parents[1] / "reports" / "presets"),
        help="Directory containing preset report folders and summary.json files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "reports" / "dashboard"),
        help="Directory for dashboard outputs.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top-priority symbols to show in the dashboard.",
    )
    return parser.parse_args()


def build_watchlist_frame(universe: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(universe).copy()
    if frame.empty:
        raise ValueError("watchlist is empty")

    frame = frame[frame["enabled"].astype(bool)].copy()
    frame["priority"] = pd.to_numeric(frame["priority"], errors="coerce")
    frame["target_weight_hint"] = pd.to_numeric(frame["target_weight_hint"], errors="coerce")
    frame = frame.sort_values(
        ["priority", "target_weight_hint", "group", "strategy_tag", "symbol"],
        ascending=[True, False, True, True, True],
        na_position="last",
    ).reset_index(drop=True)
    return frame


def sanitize_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"_", "-"} else "_" for character in value).strip("_") or "default"


def load_presets(path: str | Path) -> dict[str, dict]:
    raw = load_yaml(path)
    return raw.get("presets", {})


def summarize_preset_metadata(universe: list[dict[str, object]]) -> dict[str, object]:
    frame = pd.DataFrame(universe).copy()
    if frame.empty:
        return {}
    summary: dict[str, object] = {"instrument_count": int(len(frame)), "symbols": ",".join(frame["symbol"].astype(str).tolist())}

    priority_series = pd.to_numeric(frame.get("priority"), errors="coerce").dropna()
    if not priority_series.empty:
        summary["priority_min"] = int(priority_series.min())
        summary["priority_max"] = int(priority_series.max())
        summary["priority_avg"] = round(float(priority_series.mean()), 4)

    weight_series = pd.to_numeric(frame.get("target_weight_hint"), errors="coerce").dropna()
    if not weight_series.empty:
        summary["target_weight_hint_sum"] = round(float(weight_series.sum()), 6)
        summary["target_weight_hint_avg"] = round(float(weight_series.mean()), 6)

    return summary


def load_preset_summary_from_reports(
    universe: list[dict[str, object]],
    presets: dict[str, dict],
    reports_dir: str | Path,
) -> pd.DataFrame:
    reports_path = Path(reports_dir)
    rows: list[dict[str, object]] = []

    for preset_name, preset_filters in presets.items():
        summary_json = reports_path / sanitize_name(preset_name) / "summary.json"
        if not summary_json.exists():
            continue

        preset_universe = apply_universe_filters(
            universe,
            groups=preset_filters.get("groups"),
            strategy_tags=preset_filters.get("strategy_tags"),
            instrument_types=preset_filters.get("instrument_types"),
            symbols=preset_filters.get("symbols"),
            include_disabled=False,
        )
        with summary_json.open("r", encoding="utf-8") as handle:
            metrics = json.load(handle)

        row = {"preset": preset_name}
        row.update(summarize_preset_metadata(preset_universe))
        row.update(metrics)
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    numeric_columns = [
        "instrument_count",
        "priority_min",
        "priority_max",
        "priority_avg",
        "target_weight_hint_sum",
        "target_weight_hint_avg",
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "sharpe",
        "max_drawdown",
        "win_rate",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def build_overview_frame(watchlist: pd.DataFrame, preset_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = [
        {"metric": "enabled_symbol_count", "value": int(len(watchlist))},
        {"metric": "enabled_group_count", "value": int(watchlist["group"].nunique())},
        {"metric": "enabled_strategy_tag_count", "value": int(watchlist["strategy_tag"].nunique())},
        {"metric": "target_weight_hint_sum", "value": round(float(watchlist["target_weight_hint"].fillna(0.0).sum()), 6)},
        {"metric": "top_priority_value", "value": float(watchlist["priority"].min()) if not watchlist["priority"].isna().all() else ""},
        {"metric": "top_priority_symbols", "value": ",".join(watchlist.loc[watchlist["priority"] == watchlist["priority"].min(), "symbol"].astype(str).tolist()) if not watchlist["priority"].isna().all() else ""},
    ]
    if not preset_summary.empty:
        best_sharpe = preset_summary.sort_values("sharpe", ascending=False).iloc[0]
        best_return = preset_summary.sort_values("annualized_return", ascending=False).iloc[0]
        rows.extend(
            [
                {"metric": "best_preset_by_sharpe", "value": str(best_sharpe["preset"])},
                {"metric": "best_preset_sharpe", "value": round(float(best_sharpe["sharpe"]), 6)},
                {"metric": "best_preset_by_annualized_return", "value": str(best_return["preset"])},
                {"metric": "best_preset_annualized_return", "value": round(float(best_return["annualized_return"]), 6)},
            ]
        )
    return pd.DataFrame(rows)


def build_group_frame(watchlist: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        watchlist.groupby("group", dropna=False)
        .agg(
            instrument_count=("symbol", "count"),
            priority_min=("priority", "min"),
            target_weight_hint_sum=("target_weight_hint", "sum"),
            symbols=("symbol", lambda values: ",".join(values.astype(str).tolist())),
        )
        .reset_index()
        .sort_values(["priority_min", "target_weight_hint_sum", "group"], ascending=[True, False, True], na_position="last")
    )
    grouped["target_weight_hint_sum"] = grouped["target_weight_hint_sum"].round(6)
    return grouped


def build_top_priority_frame(watchlist: pd.DataFrame, top_n: int) -> pd.DataFrame:
    frame = watchlist.loc[:, ["symbol", "name", "priority", "target_weight_hint", "group", "strategy_tag", "instrument_type", "notes"]].copy()
    return frame.head(top_n).reset_index(drop=True)


def build_preset_leaderboard_frame(preset_summary: pd.DataFrame) -> pd.DataFrame:
    if preset_summary.empty:
        return preset_summary
    columns = [
        "preset",
        "instrument_count",
        "priority_min",
        "target_weight_hint_sum",
        "annualized_return",
        "sharpe",
        "max_drawdown",
        "win_rate",
    ]
    available_columns = [column for column in columns if column in preset_summary.columns]
    return preset_summary.loc[:, available_columns].sort_values(
        ["sharpe", "annualized_return"],
        ascending=[False, False],
        na_position="last",
    ).reset_index(drop=True)


def section_to_markdown(title: str, frame: pd.DataFrame) -> str:
    if frame.empty:
        return f"## {title}\n\n_No data available._\n"
    return f"## {title}\n\n{frame.to_markdown(index=False)}\n"


def export_dashboard_markdown(
    destination: Path,
    overview: pd.DataFrame,
    groups: pd.DataFrame,
    top_priority: pd.DataFrame,
    preset_leaderboard: pd.DataFrame,
) -> None:
    sections = [
        "# Research Dashboard",
        "",
        section_to_markdown("Overview", overview),
        section_to_markdown("Group Summary", groups),
        section_to_markdown("Top Priority Watchlist", top_priority),
        section_to_markdown("Preset Leaderboard", preset_leaderboard),
    ]
    destination.write_text("\n".join(sections), encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = load_project_config(args.config)
    watchlist = build_watchlist_frame(config["universe"])
    presets = load_presets(args.presets_file)
    preset_summary = load_preset_summary_from_reports(config["universe"], presets, args.preset_reports_dir)

    overview = build_overview_frame(watchlist, preset_summary)
    groups = build_group_frame(watchlist)
    top_priority = build_top_priority_frame(watchlist, args.top_n)
    preset_leaderboard = build_preset_leaderboard_frame(preset_summary)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    overview_path = output_dir / "dashboard_overview.csv"
    groups_path = output_dir / "dashboard_groups.csv"
    top_priority_path = output_dir / "dashboard_top_priority.csv"
    preset_path = output_dir / "dashboard_presets.csv"
    markdown_path = output_dir / "research_dashboard.md"

    overview.to_csv(overview_path, index=False, encoding="utf-8-sig")
    groups.to_csv(groups_path, index=False, encoding="utf-8-sig")
    top_priority.to_csv(top_priority_path, index=False, encoding="utf-8-sig")
    preset_leaderboard.to_csv(preset_path, index=False, encoding="utf-8-sig")
    export_dashboard_markdown(markdown_path, overview, groups, top_priority, preset_leaderboard)

    print(f"dashboard overview -> {overview_path}")
    print(f"dashboard groups -> {groups_path}")
    print(f"dashboard top priority -> {top_priority_path}")
    print(f"dashboard presets -> {preset_path}")
    print(f"dashboard markdown -> {markdown_path}")
    print(section_to_markdown("Overview", overview))
    print(section_to_markdown("Group Summary", groups))
    print(section_to_markdown("Top Priority Watchlist", top_priority))
    print(section_to_markdown("Preset Leaderboard", preset_leaderboard))


if __name__ == "__main__":
    main()
