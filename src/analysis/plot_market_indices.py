"""Plot a comparison chart for the three major US equity indices."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.utils.config import DEFAULT_MARKET_INDEX_TICKERS, FIGURES_DIR, PRICE_OUTPUT_DIR

INDEX_LABELS = {
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ Composite",
    "^DJI": "Dow Jones Industrial Average",
}


def sanitize_symbol(symbol: str) -> str:
    return symbol.replace("^", "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot major US index performance.")
    parser.add_argument(
        "--price-dir",
        default=str(PRICE_OUTPUT_DIR),
        help="Directory containing index CSV files.",
    )
    parser.add_argument(
        "--output-path",
        default=str(FIGURES_DIR / "price_event_charts" / "us_major_indices_comparison.png"),
        help="Output path for the chart image.",
    )
    parser.add_argument(
        "--tickers",
        nargs="*",
        default=list(DEFAULT_MARKET_INDEX_TICKERS),
        help="Tickers to include in the chart.",
    )
    parser.add_argument(
        "--price-column",
        default="Close",
        choices=["Adj Close", "Close", "Open", "High", "Low"],
        help="Price column used in the chart.",
    )
    parser.add_argument(
        "--normalize-to-100",
        action="store_true",
        help="Normalize each index to 100 at the first available date.",
    )
    return parser.parse_args()


def load_price_series(price_path: Path, price_column: str) -> pd.DataFrame:
    raw = pd.read_csv(price_path)
    if raw.empty or len(raw) < 3:
        raise ValueError(f"Price file has no usable rows: {price_path}")

    frame = raw.iloc[2:].copy()
    frame = frame.rename(columns={"Price": "Date"})
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame[price_column] = pd.to_numeric(frame[price_column], errors="coerce")
    frame = frame.dropna(subset=["Date", price_column])
    return frame[["Date", price_column]].sort_values("Date").reset_index(drop=True)


def main() -> None:
    args = parse_args()
    price_dir = Path(args.price_dir)
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    missing: list[str] = []

    for ticker in args.tickers:
        csv_path = price_dir / f"{sanitize_symbol(ticker)}.csv"
        if not csv_path.exists():
            missing.append(ticker)
            continue

        series = load_price_series(csv_path, args.price_column)
        if series.empty:
            missing.append(ticker)
            continue

        label = INDEX_LABELS.get(ticker, ticker)
        y = series[args.price_column]
        if args.normalize_to_100:
            base = float(y.iloc[0])
            if base == 0:
                missing.append(ticker)
                continue
            y = (y / base) * 100.0
            ax.set_ylabel(f"{args.price_column} (Indexed=100)")
        else:
            ax.set_ylabel(args.price_column)

        ax.plot(series["Date"], y, linewidth=2, label=label)

    ax.set_title("Major US Indices Comparison")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    print(f"[plot] wrote {output_path}")

    if missing:
        print("[plot] warnings:")
        for ticker in missing:
            print(f"- missing data for {ticker}")


if __name__ == "__main__":
    main()
