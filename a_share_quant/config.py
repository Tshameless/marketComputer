from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_project_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    config = load_yaml(config_path)

    universe = config.get("universe", [])
    universe_file = config.get("universe_file")
    if universe_file:
        universe = load_universe_csv(config_path.parent / universe_file)

    if not universe:
        raise ValueError("universe is empty; provide inline universe items or a universe_file")

    config["universe"] = universe
    return config


def load_universe_csv(path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for index, row in enumerate(reader, start=2):
            symbol = (row.get("symbol") or "").strip()
            name = (row.get("name") or "").strip()
            if not symbol or not name:
                raise ValueError(f"invalid universe row at line {index}: symbol and name are required")
            rows.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "instrument_type": ((row.get("instrument_type") or "ETF").strip() or "ETF").upper(),
                    "group": (row.get("group") or "").strip(),
                    "strategy_tag": (row.get("strategy_tag") or "").strip(),
                    "notes": (row.get("notes") or "").strip(),
                }
            )
    return rows


def filter_universe(
    universe: list[dict[str, str]],
    group: str | None = None,
    strategy_tag: str | None = None,
) -> list[dict[str, str]]:
    filtered = universe
    if group:
        filtered = [item for item in filtered if item.get("group") == group]
    if strategy_tag:
        filtered = [item for item in filtered if item.get("strategy_tag") == strategy_tag]
    if not filtered:
        raise ValueError("no instruments matched the requested universe filters")
    return filtered


def apply_universe_filters(
    universe: list[dict[str, str]],
    *,
    groups: list[str] | None = None,
    strategy_tags: list[str] | None = None,
    instrument_types: list[str] | None = None,
    symbols: list[str] | None = None,
) -> list[dict[str, str]]:
    filtered = universe
    if groups:
        allowed_groups = set(groups)
        filtered = [item for item in filtered if item.get("group") in allowed_groups]
    if strategy_tags:
        allowed_tags = set(strategy_tags)
        filtered = [item for item in filtered if item.get("strategy_tag") in allowed_tags]
    if instrument_types:
        allowed_types = {value.upper() for value in instrument_types}
        filtered = [item for item in filtered if item.get("instrument_type", "").upper() in allowed_types]
    if symbols:
        allowed_symbols = set(symbols)
        filtered = [item for item in filtered if item.get("symbol") in allowed_symbols]
    if not filtered:
        raise ValueError("no instruments matched the requested preset filters")
    return filtered
