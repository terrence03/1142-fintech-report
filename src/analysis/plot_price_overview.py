"""Build a small-multiples overview chart for all company price series."""

from __future__ import annotations

import argparse
import math
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
    parser = argparse.ArgumentParser(description="Plot small-multiples price overview chart.")
    parser.add_argument(
        "--template-path",
        default=str(PROTOTYPE_TEMPLATE_PATH),
        help="Path to prototype template with tickers and event dates.",
    )
    parser.add_argument(
        "--price-dir",
        default=str(PRICE_OUTPUT_DIR),
        help="Directory containing per-ticker price CSV files.",
    )
    parser.add_argument(
        "--output-path",
        default=str(FIGURES_DIR / "price_event_charts" / "all_companies_overview.png"),
        help="Output image path.",
    )
    parser.add_argument(
        "--price-column",
        default="Close",
        choices=["Adj Close", "Close", "Open", "High", "Low"],
        help="Price column to plot.",
    )
    parser.add_argument(
        "--normalize-to-100",
        action="store_true",
        help="Normalize each ticker to 100 at first available date.",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=4,
        help="Number of subplot columns.",
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


def main() -> None:
    args = parse_args()

    template = pd.read_csv(args.template_path)
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    price_dir = Path(args.price_dir)

    n = len(template)
    cols = max(1, args.cols)
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4.6, rows * 3.1), sharex=False)
    if hasattr(axes, "flatten"):
        axes_list = list(axes.flatten())
    else:
        axes_list = [axes]

    missing: list[str] = []
    for i, (_, row) in enumerate(template.iterrows()):
        ax = axes_list[i]
        ticker = str(row["ticker"]).upper()
        company_name = str(row["company_name"])
        primary_event = pd.to_datetime(row["market_attention_anchor_date"], errors="coerce")
        secondary_event = pd.to_datetime(row["github_launch_date"], errors="coerce")
        price_path = price_dir / f"{ticker}.csv"
        if not price_path.exists() or pd.isna(primary_event) or pd.isna(secondary_event):
            ax.set_title(f"{ticker} (missing)")
            ax.axis("off")
            missing.append(ticker)
            continue

        frame = load_price_frame(price_path)
        series = frame[["Date", args.price_column]].dropna().copy()
        if series.empty:
            ax.set_title(f"{ticker} (no data)")
            ax.axis("off")
            missing.append(ticker)
            continue

        if args.normalize_to_100:
            base = float(series[args.price_column].iloc[0])
            if base != 0:
                series[args.price_column] = (series[args.price_column] / base) * 100.0

        ax.plot(series["Date"], series[args.price_column], color="tab:gray", linewidth=1.4)
        ax.axvline(primary_event, color="tab:red", linestyle="--", linewidth=1.0)
        ax.axvline(secondary_event, color="tab:blue", linestyle=":", linewidth=1.0)
        ax.set_title(f"{ticker} | {company_name}", fontsize=9)
        ax.grid(True, alpha=0.25)
        ax.tick_params(axis="x", labelrotation=35, labelsize=7)
        ax.tick_params(axis="y", labelsize=7)

    for j in range(n, len(axes_list)):
        axes_list[j].axis("off")

    y_label = f"{args.price_column} (Indexed=100)" if args.normalize_to_100 else args.price_column
    fig.suptitle("SaaS Price Overview with Event Markers", fontsize=14, y=0.995)
    fig.text(0.01, 0.5, y_label, va="center", rotation="vertical", fontsize=10)
    fig.text(
        0.5,
        0.01,
        "Red dashed line: primary event (2026-01-31) | Blue dotted line: secondary event (2025-11-24)",
        ha="center",
        fontsize=9,
    )
    handles = [
        plt.Line2D([0], [0], color="tab:red", linestyle="--", linewidth=1.2, label="Primary Event"),
        plt.Line2D([0], [0], color="tab:blue", linestyle=":", linewidth=1.2, label="Secondary Event"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.972), frameon=False)
    fig.tight_layout(rect=[0.03, 0.04, 1.0, 0.955])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    print(f"[plot] wrote {output_path}")
    if missing:
        print("[plot] warnings:")
        for ticker in missing:
            print(f"- missing data for {ticker}")


if __name__ == "__main__":
    main()
