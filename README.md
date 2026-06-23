# A-Share ETF Research Starter

This project is a minimal A-share ETF research stack for the path we discussed:

- `AKShare` for domestic ETF data
- a local ETF rotation backtest that runs without a vendor data bundle
- a Python 3.11 environment that can later be extended toward `RQAlpha` or `vn.py`

## What is included

- `config/universe.yaml`: strategy and data parameters
- `config/etf_watchlist.csv`: your editable ETF watchlist with grouping fields
- `config/presets.yaml`: named portfolio presets built from your watchlist tags
- `scripts/fetch_etf_history.py`: fetch and cache ETF daily history from AKShare
- `scripts/run_rotation_backtest.py`: run a simple momentum rotation backtest
- `scripts/run_grouped_backtests.py`: batch backtest every ETF group or strategy tag
- `scripts/run_preset_backtests.py`: batch backtest named preset portfolios
- `scripts/export_watchlist_view.py`: export a manual rebalance view from the watchlist metadata
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
symbol,name,enabled,priority,target_weight_hint,instrument_type,group,strategy_tag,notes
510300,沪深300ETF,1,1,0.30,ETF,broad,core,宽基核心仓位
164701,汇添富黄金及贵金属(QDII-LOF-FOF)A,1,3,0.05,LOF,commodity,candidate,黄金主题补充
```

Suggested meaning:

- `enabled`: `1` means the symbol is active in normal fetches and backtests; `0` keeps it in the watchlist but skips it by default
- `priority`: lower numbers mean higher research or trading priority
- `target_weight_hint`: optional placeholder weight for research organization; it does not change the current backtest engine
- `instrument_type`: currently supports `ETF` and `LOF`
- `group`: your pool grouping such as `broad`, `dividend`, `bond`, `commodity`
- `strategy_tag`: your usage tag such as `core`, `satellite`, `rotation`
- `notes`: free-form reminders about why this ETF is in the pool

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

You can fetch only part of the watchlist:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\fetch_etf_history.py --group broad
python .\scripts\fetch_etf_history.py --strategy-tag core
python .\scripts\fetch_etf_history.py --strategy-tag candidate --include-disabled
```

## Run the sample backtest

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\run_rotation_backtest.py
```

You can also run a grouped backtest:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\run_rotation_backtest.py --group broad
python .\scripts\run_rotation_backtest.py --strategy-tag satellite
python .\scripts\run_rotation_backtest.py --strategy-tag candidate --include-disabled
```

Grouped reports are written into subfolders such as `reports/rotation/group_broad/`.

If you want a summary table across every watchlist group:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\run_grouped_backtests.py --group-field group
python .\scripts\run_grouped_backtests.py --group-field strategy_tag
```

You can also limit the batch run:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\run_grouped_backtests.py --group-field group --values broad,growth
```

This writes aggregate files such as `reports/rotation/summary_by_group.csv`.

## Run named presets

The repository also includes named preset portfolios in `config/presets.yaml`, for example:

- `core_base`
- `broad_rotation`
- `overseas_mix`
- `candidate_pool`

Run all presets:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\run_preset_backtests.py
```

Run a single preset:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\run_preset_backtests.py --preset candidate_pool
python .\scripts\run_preset_backtests.py --preset candidate_pool --include-disabled
```

This writes aggregate files such as `reports/presets/summary_by_preset.csv`.

Each preset folder also includes a `constituents.csv` file with the watchlist metadata for that preset.

## Export a manual watchlist view

You can export a sorted watchlist table for manual review or rebalancing:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\export_watchlist_view.py
python .\scripts\export_watchlist_view.py --preset candidate_pool
python .\scripts\export_watchlist_view.py --group overseas
```

This writes both `csv` and `md` files under `reports/views/`, sorted by:

- enabled status
- priority
- target weight hint
- group and symbol

The sample strategy rebalances every 5 trading days, ranks ETFs by 20-day momentum, and holds the top 1 ETF when its momentum is positive. Transaction costs are approximated with commission and slippage in basis points.

## Next steps

- Expand the ETF universe with sectors, bonds, commodities, or cross-border products
- Add fund-specific filters like turnover, size, or premium/discount
- Add stock universes later by reusing the same cache and backtest structure
- Introduce `RQAlpha` once you want a more formal event-driven engine
