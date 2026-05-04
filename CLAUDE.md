# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a research project analyzing the **market impact of OpenClaw on SaaS enterprises**. The core question: which SaaS companies experienced higher market impact following OpenClaw's market expansion (anchored on 2026-01-31), and what characteristics do they share?

Methodology: event study analysis + cluster analysis using public stock price data (Yahoo Finance) and SEC XBRL financial data.

- Primary event date: 2026-01-31 (market recognition expansion)
- Secondary event date: 2025-11-24 (technology launch)
- Initial sample: 14–30 SaaS companies across sectors
- Analysis is descriptive and associational, not causal

Current status is tracked in [docs/research_plan/Research_Progress_Status.md](docs/research_plan/Research_Progress_Status.md).

## Environment Setup

Uses `uv` for package management and Python 3.14.

```bash
uv sync                  # install dependencies
uv run python <script>   # run any script
```

Requires a `.env` file with:
```
SEC_USER_AGENT="Your Name email@example.com"
```

## Running Scripts

### Data Collection

```bash
# Download stock prices + SEC XBRL data for all companies in template
uv run python src/data_collection/fetch_a_grade_data.py \
  --template-path data/templates/company_universe_30_template.csv

# Download major market indices (S&P 500, NASDAQ, DJIA)
uv run python src/data_collection/fetch_market_indices.py
```

### Data Processing

```bash
# Build the integrated analytics table (event window returns + financial metrics)
uv run python src/data_collection/build_prototype_dataset.py

# Audit missing values in the processed dataset
uv run python src/analysis/quality_check.py
```

### Analysis & Visualization

```bash
# Compare SaaS basket vs. major indices
uv run python src/analysis/analyze_universe_vs_indices.py \
  --template-path data/templates/company_universe_30_template.csv

# Per-company price charts with event date markers
uv run python src/analysis/plot_price_with_events.py

# Small-multiples overview of all companies
uv run python src/analysis/plot_price_overview.py

# Index comparison chart
uv run python src/analysis/plot_market_indices.py
```

## Architecture

### Data Flow

```
Templates (data/templates/)
  → fetch_a_grade_data.py → data/raw/prices/*.csv + data/raw/sec/*.json
  → build_prototype_dataset.py → data/processed/prototype_data_sheet.csv
  → analysis scripts → results/figures/ + results/tables/
```

### Key Files

| File | Purpose |
|------|---------|
| [src/utils/config.py](src/utils/config.py) | All path constants, benchmark tickers, XBRL tag mappings — import this instead of hardcoding paths |
| [data/templates/company_universe_30_template.csv](data/templates/company_universe_30_template.csv) | Master company list with tickers and anchor dates; drives all downstream scripts |
| [data/processed/prototype_data_sheet.csv](data/processed/prototype_data_sheet.csv) | Integrated analytics table: 23 columns covering event window returns + financial metrics |
| [docs/research_plan/Research_Progress_Status.md](docs/research_plan/Research_Progress_Status.md) | Live tracker for completed/in-progress/upcoming tasks |

### `build_prototype_dataset.py` — Core Processing Logic

This script is the most complex. It:
1. Loads prices and SEC XBRL JSON per company
2. Computes cumulative returns over configurable pre/post event windows
3. Extracts financial metrics from XBRL (revenue growth, gross/operating/FCF margins, R&D intensity, S&M intensity, market cap, P/S ratio)
4. Handles edge cases: 6-K filers (foreign issuers like MNDY), missing XBRL tags (WDAY), stale share counts

### Known Data Quality Issues

- **MNDY** (Monday.com): 6-K filer — XBRL revenue mismatch; margin ratios are nulled
- **WDAY** (Workday): Missing `GrossProfit`/`CostOfRevenue` XBRL tags
- **DDOG**: Missing market cap and P/S ratio
- Valid cluster analysis sample: ~13–14 companies out of 30

## Dependencies

| Package | Purpose |
|---------|---------|
| `pandas` | Data manipulation |
| `numpy` | Numerical computing |
| `matplotlib` | Visualization (Agg backend for headless rendering) |
| `yfinance` | Yahoo Finance historical prices |
| `requests` | SEC EDGAR API calls |

External APIs:
- **SEC EDGAR**: `https://data.sec.gov/api/xbrl/companyfacts/{CIK}.json`
- **SEC ticker map**: `https://www.sec.gov/files/company_tickers.json`
