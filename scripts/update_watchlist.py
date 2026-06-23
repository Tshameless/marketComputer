from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

from a_share_quant.config import (
    parse_enabled_value,
    parse_priority_value,
    parse_target_weight_hint_value,
)


FIELDNAMES = [
    "symbol",
    "name",
    "enabled",
    "priority",
    "target_weight_hint",
    "instrument_type",
    "group",
    "strategy_tag",
    "notes",
]

EDITABLE_FIELDS = [
    "enabled",
    "priority",
    "target_weight_hint",
    "instrument_type",
    "group",
    "strategy_tag",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch update rows in config/etf_watchlist.csv.")
    parser.add_argument(
        "--watchlist",
        default=str(Path(__file__).resolve().parents[1] / "config" / "etf_watchlist.csv"),
        help="Path to the watchlist CSV.",
    )
    parser.add_argument(
        "--symbols",
        help="Comma-separated list of symbols to update, for example 513500,159941.",
    )
    parser.add_argument(
        "--updates-file",
        help="Path to a CSV containing symbol plus one or more editable fields to update.",
    )
    parser.add_argument("--enabled", help="Set enabled to 1/0, true/false, yes/no.")
    parser.add_argument("--priority", help="Set the priority integer.")
    parser.add_argument("--target-weight-hint", help="Set the target weight hint float.")
    parser.add_argument("--instrument-type", help="Set instrument_type, such as ETF or LOF.")
    parser.add_argument("--group", help="Set the group field.")
    parser.add_argument("--strategy-tag", help="Set the strategy_tag field.")
    parser.add_argument("--notes", help="Set the notes field.")
    parser.add_argument(
        "--post-refresh",
        choices=["none", "view", "dashboard", "all"],
        default="none",
        help="Optional post-update refresh: watchlist view, research dashboard, or both.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview updates without writing the CSV.")
    return parser.parse_args()


def parse_symbol_list(raw_value: str) -> list[str]:
    symbols = [value.strip() for value in raw_value.split(",") if value.strip()]
    if not symbols:
        raise ValueError("at least one symbol is required")
    return symbols


def normalize_field_update(field_name: str, raw_value: str) -> str:
    if field_name == "enabled":
        return "1" if parse_enabled_value(raw_value) else "0"
    if field_name == "priority":
        return str(parse_priority_value(raw_value))
    if field_name == "target_weight_hint":
        return str(parse_target_weight_hint_value(raw_value))
    if field_name == "instrument_type":
        return raw_value.strip().upper()
    if field_name in {"group", "strategy_tag", "notes"}:
        return raw_value.strip()
    raise ValueError(f"unsupported update field: {field_name}")


def build_cli_updates(args: argparse.Namespace) -> dict[str, str]:
    updates: dict[str, str] = {}
    if args.enabled is not None:
        updates["enabled"] = normalize_field_update("enabled", args.enabled)
    if args.priority is not None:
        updates["priority"] = normalize_field_update("priority", args.priority)
    if args.target_weight_hint is not None:
        updates["target_weight_hint"] = normalize_field_update("target_weight_hint", args.target_weight_hint)
    if args.instrument_type is not None:
        updates["instrument_type"] = normalize_field_update("instrument_type", args.instrument_type)
    if args.group is not None:
        updates["group"] = normalize_field_update("group", args.group)
    if args.strategy_tag is not None:
        updates["strategy_tag"] = normalize_field_update("strategy_tag", args.strategy_tag)
    if args.notes is not None:
        updates["notes"] = normalize_field_update("notes", args.notes)
    if not updates:
        raise ValueError("no update fields were provided")
    return updates


def load_updates_file(path: str | Path) -> list[tuple[str, dict[str, str]]]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "symbol" not in reader.fieldnames:
            raise ValueError("updates file must include a symbol column")

        updates_by_symbol: list[tuple[str, dict[str, str]]] = []
        for index, row in enumerate(reader, start=2):
            symbol = (row.get("symbol") or "").strip()
            if not symbol:
                raise ValueError(f"missing symbol in updates file line {index}")

            updates: dict[str, str] = {}
            for field_name in EDITABLE_FIELDS:
                raw_value = row.get(field_name)
                if raw_value is None:
                    continue
                if not str(raw_value).strip():
                    continue
                updates[field_name] = normalize_field_update(field_name, str(raw_value))

            if not updates:
                raise ValueError(f"no editable fields provided for symbol {symbol} in line {index}")
            updates_by_symbol.append((symbol, updates))

    return updates_by_symbol


def load_rows(path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def save_rows(path: str | Path, rows: list[dict[str, str]]) -> None:
    csv_path = Path(path)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def run_post_refresh(args: argparse.Namespace) -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)

    # Reuse the current interpreter so the refresh scripts run in the same environment.
    commands: list[list[str]] = []
    if args.post_refresh in {"view", "all"}:
        commands.append([sys.executable, str(root / "scripts" / "export_watchlist_view.py")])
    if args.post_refresh in {"dashboard", "all"}:
        commands.append([sys.executable, str(root / "scripts" / "export_research_dashboard.py")])

    for command in commands:
        subprocess.run(command, cwd=root, check=True, env=env)


def apply_updates_to_rows(
    rows: list[dict[str, str]],
    updates_by_symbol: list[tuple[str, dict[str, str]]],
) -> tuple[list[str], list[dict[str, str]]]:
    row_map = {row.get("symbol", ""): row for row in rows}
    matched_symbols: list[str] = []
    preview_rows: list[dict[str, str]] = []

    for symbol, updates in updates_by_symbol:
        row = row_map.get(symbol)
        if row is None:
            continue
        matched_symbols.append(symbol)
        for field, value in updates.items():
            row[field] = value
        preview_rows.append({field: row.get(field, "") for field in FIELDNAMES})

    return matched_symbols, preview_rows


def ensure_mode_is_valid(args: argparse.Namespace) -> None:
    if args.updates_file and args.symbols:
        raise ValueError("use either --symbols or --updates-file, not both")
    if not args.updates_file and not args.symbols:
        raise ValueError("either --symbols or --updates-file is required")


def main() -> None:
    args = parse_args()
    ensure_mode_is_valid(args)
    rows = load_rows(args.watchlist)

    if args.updates_file:
        updates_by_symbol = load_updates_file(args.updates_file)
    else:
        symbols = parse_symbol_list(args.symbols)
        updates_by_symbol = [(symbol, build_cli_updates(args)) for symbol in symbols]

    matched_symbols, preview_rows = apply_updates_to_rows(rows, updates_by_symbol)
    missing_symbols = sorted({symbol for symbol, _ in updates_by_symbol} - set(matched_symbols))
    if missing_symbols:
        raise ValueError(f"symbols not found in watchlist: {', '.join(missing_symbols)}")

    if not args.dry_run:
        save_rows(args.watchlist, rows)
        if args.post_refresh != "none":
            run_post_refresh(args)

    action = "preview" if args.dry_run else "updated"
    print(f"{action} symbols: {', '.join(matched_symbols)}")
    if args.updates_file:
        print(f"applied updates file: {args.updates_file}")
    else:
        updates = build_cli_updates(args)
        print(f"applied fields: {', '.join(f'{key}={value}' for key, value in updates.items())}")
    for row in preview_rows:
        print(",".join(str(row.get(field, "")) for field in FIELDNAMES))


if __name__ == "__main__":
    main()
