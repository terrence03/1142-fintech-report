"""Fetch major US equity indices into raw price storage."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import DEFAULT_MARKET_INDEX_TICKERS, PRICE_OUTPUT_DIR

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - runtime safeguard
    yf = None


def sanitize_symbol(symbol: str) -> str:
    return symbol.replace("^", "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch major US market indices.")
    parser.add_argument(
        "--start-date",
        default="2025-09-01",
        help="Inclusive start date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end-date",
        default="2026-03-31",
        help="Exclusive end date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--tickers",
        nargs="*",
        default=list(DEFAULT_MARKET_INDEX_TICKERS),
        help="Index tickers (default: ^GSPC ^IXIC ^DJI).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PRICE_OUTPUT_DIR),
        help="Directory for CSV outputs.",
    )
    return parser.parse_args()


def main() -> None:
    if yf is None:
        raise RuntimeError("Missing optional dependency 'yfinance'. Install it first.")

    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for ticker in args.tickers:
        history = yf.download(
            ticker,
            start=args.start_date,
            end=args.end_date,
            auto_adjust=False,
            progress=False,
            interval="1d",
            threads=False,
        )
        if history.empty:
            print(f"[indices] no data returned for {ticker}")
            continue

        output_path = output_dir / f"{sanitize_symbol(ticker)}.csv"
        history.to_csv(output_path)
        print(f"[indices] wrote {output_path}")


if __name__ == "__main__":
    main()
