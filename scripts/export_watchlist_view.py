from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from a_share_quant.config import apply_universe_filters, filter_universe, load_project_config, load_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a manual rebalance watchlist view.")
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
    parser.add_argument("--preset", help="Optional preset name to filter the watchlist.")
    parser.add_argument("--group", help="Optional group filter.")
    parser.add_argument("--strategy-tag", help="Optional strategy tag filter.")
    parser.add_argument("--include-disabled", action="store_true", help="Include disabled watchlist rows.")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "reports" / "views"),
        help="Directory for exported watchlist views.",
    )
    return parser.parse_args()


def load_presets(path: str | Path) -> dict[str, dict]:
    raw = load_yaml(path)
    return raw.get("presets", {})


def sanitize_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"_", "-"} else "_" for character in value).strip("_") or "default"


def build_watchlist_frame(universe: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(universe).copy()
    if frame.empty:
        raise ValueError("watchlist view is empty")

    frame["enabled_rank"] = frame["enabled"].astype(int).map({1: 0, 0: 1})
    frame["priority_sort"] = pd.to_numeric(frame["priority"], errors="coerce")
    frame["weight_sort"] = pd.to_numeric(frame["target_weight_hint"], errors="coerce")
    frame = frame.sort_values(
        ["enabled_rank", "priority_sort", "weight_sort", "group", "strategy_tag", "symbol"],
        ascending=[True, True, False, True, True, True],
        na_position="last",
    ).reset_index(drop=True)
    frame.insert(0, "rank", range(1, len(frame) + 1))
    frame["target_weight_hint_cum"] = pd.to_numeric(frame["target_weight_hint"], errors="coerce").fillna(0.0).cumsum().round(6)
    frame["enabled"] = frame["enabled"].map({True: 1, False: 0})
    return frame.drop(columns=["enabled_rank", "priority_sort", "weight_sort"])


def resolve_output_label(args: argparse.Namespace) -> str:
    if args.preset:
        return f"preset_{sanitize_name(args.preset)}"
    parts: list[str] = []
    if args.group:
        parts.append(f"group_{sanitize_name(args.group)}")
    if args.strategy_tag:
        parts.append(f"tag_{sanitize_name(args.strategy_tag)}")
    if not parts:
        return "all_enabled"
    return "__".join(parts)


def filter_view_universe(args: argparse.Namespace, config: dict) -> list[dict[str, object]]:
    if args.preset:
        presets = load_presets(args.presets_file)
        if args.preset not in presets:
            raise ValueError(f"unknown preset: {args.preset}")
        preset_filters = presets[args.preset]
        return apply_universe_filters(
            config["universe"],
            groups=preset_filters.get("groups"),
            strategy_tags=preset_filters.get("strategy_tags"),
            instrument_types=preset_filters.get("instrument_types"),
            symbols=preset_filters.get("symbols"),
            include_disabled=args.include_disabled,
        )

    return filter_universe(
        config["universe"],
        group=args.group,
        strategy_tag=args.strategy_tag,
        include_disabled=args.include_disabled,
    )


def export_markdown(frame: pd.DataFrame, destination: Path) -> None:
    destination.write_text(frame.to_markdown(index=False), encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = load_project_config(args.config)
    universe = filter_view_universe(args, config)
    frame = build_watchlist_frame(universe)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    label = resolve_output_label(args)

    csv_path = output_dir / f"watchlist_view_{label}.csv"
    md_path = output_dir / f"watchlist_view_{label}.md"

    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    export_markdown(frame, md_path)

    print(f"watchlist csv -> {csv_path}")
    print(f"watchlist md -> {md_path}")
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
