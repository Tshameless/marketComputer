from __future__ import annotations

import argparse
import csv
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch update rows in config/etf_watchlist.csv.")
    parser.add_argument(
        "--watchlist",
        default=str(Path(__file__).resolve().parents[1] / "config" / "etf_watchlist.csv"),
        help="Path to the watchlist CSV.",
    )
    parser.add_argument(
        "--symbols",
        required=True,
        help="Comma-separated list of symbols to update, for example 513500,159941.",
    )
    parser.add_argument("--enabled", help="Set enabled to 1/0, true/false, yes/no.")
    parser.add_argument("--priority", help="Set the priority integer.")
    parser.add_argument("--target-weight-hint", help="Set the target weight hint float.")
    parser.add_argument("--instrument-type", help="Set instrument_type, such as ETF or LOF.")
    parser.add_argument("--group", help="Set the group field.")
    parser.add_argument("--strategy-tag", help="Set the strategy_tag field.")
    parser.add_argument("--notes", help="Set the notes field.")
    parser.add_argument("--dry-run", action="store_true", help="Preview updates without writing the CSV.")
    return parser.parse_args()


def parse_symbol_list(raw_value: str) -> list[str]:
    symbols = [value.strip() for value in raw_value.split(",") if value.strip()]
    if not symbols:
        raise ValueError("at least one symbol is required")
    return symbols


def build_updates(args: argparse.Namespace) -> dict[str, str]:
    updates: dict[str, str] = {}
    if args.enabled is not None:
        updates["enabled"] = "1" if parse_enabled_value(args.enabled) else "0"
    if args.priority is not None:
        updates["priority"] = str(parse_priority_value(args.priority))
    if args.target_weight_hint is not None:
        updates["target_weight_hint"] = str(parse_target_weight_hint_value(args.target_weight_hint))
    if args.instrument_type is not None:
        updates["instrument_type"] = args.instrument_type.strip().upper()
    if args.group is not None:
        updates["group"] = args.group.strip()
    if args.strategy_tag is not None:
        updates["strategy_tag"] = args.strategy_tag.strip()
    if args.notes is not None:
        updates["notes"] = args.notes.strip()
    if not updates:
        raise ValueError("no update fields were provided")
    return updates


def load_rows(path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def save_rows(path: str | Path, rows: list[dict[str, str]]) -> None:
    csv_path = Path(path)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    symbols = parse_symbol_list(args.symbols)
    updates = build_updates(args)
    rows = load_rows(args.watchlist)

    matched_symbols: list[str] = []
    preview_rows: list[dict[str, str]] = []
    for row in rows:
        if row.get("symbol") in symbols:
            matched_symbols.append(row["symbol"])
            for field, value in updates.items():
                row[field] = value
            preview_rows.append({field: row.get(field, "") for field in FIELDNAMES})

    missing_symbols = sorted(set(symbols) - set(matched_symbols))
    if missing_symbols:
        raise ValueError(f"symbols not found in watchlist: {', '.join(missing_symbols)}")

    if not args.dry_run:
        save_rows(args.watchlist, rows)

    action = "preview" if args.dry_run else "updated"
    print(f"{action} symbols: {', '.join(matched_symbols)}")
    print(f"applied fields: {', '.join(f'{key}={value}' for key, value in updates.items())}")
    for row in preview_rows:
        print(",".join(str(row.get(field, "")) for field in FIELDNAMES))


if __name__ == "__main__":
    main()
