"""Project-wide configuration for the OpenClaw SaaS research pipeline."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
TEMPLATES_DIR = DATA_DIR / "templates"
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"

PROTOTYPE_TEMPLATE_PATH = TEMPLATES_DIR / "prototype_data_sheet_template.csv"
PROTOTYPE_PROCESSED_PATH = PROCESSED_DATA_DIR / "prototype_data_sheet.csv"

PRICE_OUTPUT_DIR = RAW_DATA_DIR / "prices"
SEC_OUTPUT_DIR = RAW_DATA_DIR / "sec"

DEFAULT_BENCHMARK_TICKERS = ("^IXIC", "^GSPC")
DEFAULT_MARKET_INDEX_TICKERS = ("^GSPC", "^IXIC", "^DJI")
DEFAULT_REQUEST_TIMEOUT = 30
