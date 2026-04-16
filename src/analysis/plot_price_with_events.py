"""Plot per-company price trends and mark research event dates."""

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

from src.utils.config import FIGURES_DIR, PRICE_OUTPUT_DIR, PROTOTYPE_TEMPLATE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot company prices with primary and secondary event dates."
    )
    parser.add_argument(
        "--template-path",
        default=str(PROTOTYPE_TEMPLATE_PATH),
        help="Path to prototype template that contains event dates and tickers.",
    )
    parser.add_argument(
        "--price-dir",
        default=str(PRICE_OUTPUT_DIR),
        help="Directory containing per-ticker price CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(FIGURES_DIR / "price_event_charts"),
        help="Directory to save chart images.",
    )
    parser.add_argument(
        "--normalize-to-100",
        action="store_true",
        help="If set, normalize the selected price column to 100 at the first row.",
    )
    parser.add_argument(
        "--price-column",
        default="Close",
        choices=["Adj Close", "Close", "Open", "High", "Low"],
        help="Price column to visualize.",
    )
    return parser.parse_args()


def load_price_frame(price_path: Path) -> pd.DataFrame:
    raw = pd.read_csv(price_path)
    if raw.empty or len(raw) < 3:
        raise ValueError(f"Price file has no usable rows: {price_path}")

    frame = raw.iloc[2:].copy()
    frame = frame.rename(columns={"Price": "Date"})
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.dropna(subset=["Date"])

    for col in ["Adj Close", "Close", "Open", "High", "Low", "Volume"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    frame = frame.sort_values("Date").reset_index(drop=True)
    return frame


def plot_company(
    company_name: str,
    ticker: str,
    frame: pd.DataFrame,
    primary_event: pd.Timestamp,
    secondary_event: pd.Timestamp,
    output_path: Path,
    price_column: str,
    normalize_to_100: bool,
) -> None:
    series = frame[["Date", price_column]].dropna().copy()
    if series.empty:
        raise ValueError(f"No valid {price_column} values for {ticker}")

    y_label = price_column
    if normalize_to_100:
        base = float(series[price_column].iloc[0])
        if base == 0:
            raise ValueError(f"Cannot normalize {ticker}: first price is zero")
        series[price_column] = (series[price_column] / base) * 100.0
        y_label = f"{price_column} (Indexed=100)"

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(series["Date"], series[price_column], label=ticker, linewidth=2.0)

    ax.axvline(
        primary_event,
        color="tab:red",
        linestyle="--",
        linewidth=1.5,
        label=f"Primary Event ({primary_event.date().isoformat()})",
    )
    ax.axvline(
        secondary_event,
        color="tab:blue",
        linestyle=":",
        linewidth=1.5,
        label=f"Secondary Event ({secondary_event.date().isoformat()})",
    )

    ax.set_title(f"{company_name} ({ticker}) Price Trend")
    ax.set_xlabel("Date")
    ax.set_ylabel(y_label)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    args = parse_args()

    template_path = Path(args.template_path)
    price_dir = Path(args.price_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    template = pd.read_csv(template_path)
    missing: list[str] = []

    for _, row in template.iterrows():
        ticker = str(row["ticker"]).upper()
        company_name = str(row["company_name"])
        primary_event = pd.to_datetime(row["market_attention_anchor_date"], errors="coerce")
        secondary_event = pd.to_datetime(row["github_launch_date"], errors="coerce")
        if pd.isna(primary_event) or pd.isna(secondary_event):
            missing.append(f"{ticker}: invalid event dates")
            continue

        price_path = price_dir / f"{ticker}.csv"
        if not price_path.exists():
            missing.append(f"{ticker}: missing {price_path.name}")
            continue

        frame = load_price_frame(price_path)
        output_path = output_dir / f"{ticker}_price_with_events.png"
        plot_company(
            company_name=company_name,
            ticker=ticker,
            frame=frame,
            primary_event=primary_event,
            secondary_event=secondary_event,
            output_path=output_path,
            price_column=args.price_column,
            normalize_to_100=args.normalize_to_100,
        )
        print(f"[plot] wrote {output_path}")

    if missing:
        print("[plot] warnings:")
        for item in missing:
            print(f"- {item}")


if __name__ == "__main__":
    main()
