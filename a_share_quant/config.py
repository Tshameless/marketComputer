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
            rows.append({"symbol": symbol, "name": name})
    return rows
