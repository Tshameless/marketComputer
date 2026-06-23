# A-Share ETF Research Starter

This project is a minimal A-share ETF research stack for the path we discussed:

- `AKShare` for domestic ETF data
- a local ETF rotation backtest that runs without a vendor data bundle
- a Python 3.11 environment that can later be extended toward `RQAlpha` or `vn.py`

## What is included

- `config/universe.yaml`: strategy and data parameters
- `config/etf_watchlist.csv`: your editable ETF watchlist
- `scripts/fetch_etf_history.py`: fetch and cache ETF daily history from AKShare
- `scripts/run_rotation_backtest.py`: run a simple momentum rotation backtest
- `reports/rotation/`: generated equity curve, weights, and summary metrics

## Sample universe

The default ETF basket lives in `config/etf_watchlist.csv`:

- `510300` 沪深300ETF
- `510500` 中证500ETF
- `159915` 创业板ETF
- `588000` 科创50ETF
- `513100` 纳指ETF

You can replace these with your own ETF or fund pool by editing `config/etf_watchlist.csv`.

The CSV format is:

```csv
symbol,name
510300,沪深300ETF
159915,创业板ETF
```

## Environment

Use Python 3.11 for this project.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Fetch ETF data

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\fetch_etf_history.py
```

This writes cached CSV files under `data/cache/`.

## Run the sample backtest

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\run_rotation_backtest.py
```

The sample strategy rebalances every 5 trading days, ranks ETFs by 20-day momentum, and holds the top 1 ETF when its momentum is positive. Transaction costs are approximated with commission and slippage in basis points.

## Next steps

- Expand the ETF universe with sectors, bonds, commodities, or cross-border products
- Add fund-specific filters like turnover, size, or premium/discount
- Add stock universes later by reusing the same cache and backtest structure
- Introduce `RQAlpha` once you want a more formal event-driven engine
