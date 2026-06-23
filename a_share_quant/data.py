from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd


ETF_HIST_COLUMNS = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "turnover",
    "振幅": "amplitude",
    "涨跌幅": "change_pct",
    "涨跌额": "change",
    "换手率": "turnover_rate",
}


def fetch_etf_spot() -> pd.DataFrame:
    return ak.fund_etf_spot_em()


def fetch_etf_history(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
    retries: int = 5,
    sleep_seconds: float = 3.0,
) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            frame = ak.fund_etf_hist_em(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            return normalize_etf_history(frame, symbol=symbol)
        except Exception as error:  # pragma: no cover - network instability depends on upstream
            last_error = error
            if attempt == retries:
                break
            time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"failed to fetch ETF history for {symbol}") from last_error


def normalize_etf_history(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame.empty:
        raise ValueError(f"no history returned for {symbol}")

    normalized = frame.rename(columns=ETF_HIST_COLUMNS).copy()
    missing = set(ETF_HIST_COLUMNS.values()) - set(normalized.columns)
    if missing:
        raise ValueError(f"unexpected ETF history columns for {symbol}: missing {sorted(missing)}")

    normalized["date"] = pd.to_datetime(normalized["date"])
    numeric_columns = [
        "open",
        "close",
        "high",
        "low",
        "volume",
        "turnover",
        "amplitude",
        "change_pct",
        "change",
        "turnover_rate",
    ]
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized["symbol"] = symbol
    normalized = normalized.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    return normalized


def save_history(frame: pd.DataFrame, destination: str | Path) -> Path:
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination_path, index=False, encoding="utf-8-sig")
    return destination_path


def load_cached_histories(cache_dir: str | Path, symbols: list[str]) -> dict[str, pd.DataFrame]:
    cache_path = Path(cache_dir)
    histories: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        file_path = cache_path / f"{symbol}.csv"
        if not file_path.exists():
            raise FileNotFoundError(f"missing cached history: {file_path}")
        frame = pd.read_csv(file_path, parse_dates=["date"])
        histories[symbol] = frame.sort_values("date").reset_index(drop=True)
    return histories


def build_close_matrix(histories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    close_frames: list[pd.DataFrame] = []
    for symbol, frame in histories.items():
        close_frames.append(frame.loc[:, ["date", "close"]].rename(columns={"close": symbol}))

    merged = close_frames[0]
    for frame in close_frames[1:]:
        merged = merged.merge(frame, on="date", how="outer")
    merged = merged.sort_values("date").set_index("date")
    return merged


def save_spot_snapshot(destination: str | Path) -> Path:
    snapshot = fetch_etf_spot()
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot.to_csv(destination_path, index=False, encoding="utf-8-sig")
    return destination_path
