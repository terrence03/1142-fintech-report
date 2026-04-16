"""Build prototype dataset from raw SEC facts and price history."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import (
    PRICE_OUTPUT_DIR,
    PROCESSED_DATA_DIR,
    PROTOTYPE_PROCESSED_PATH,
    PROTOTYPE_TEMPLATE_PATH,
    SEC_OUTPUT_DIR,
)

REVENUE_TAGS = [
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomer",
    "SalesRevenueGoodsNet",
    "SalesRevenueNet",
    "SalesRevenueServicesNet",
    "Revenues",
]
OPERATING_INCOME_TAGS = ["OperatingIncomeLoss", "IncomeLossFromOperations"]
GROSS_PROFIT_TAGS = ["GrossProfit"]
RD_EXPENSE_TAGS = ["ResearchAndDevelopmentExpense"]
SM_EXPENSE_TAGS = ["SellingAndMarketingExpense"]
SHARES_OUTSTANDING_TAGS = [
    "CommonStockSharesOutstanding",
    "EntityCommonStockSharesOutstanding",
]

VALID_FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A"}


@dataclass(frozen=True)
class MetricPoint:
    end: pd.Timestamp
    val: float
    form: str
    fy: int | None
    fp: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build prototype dataset from raw sources.")
    parser.add_argument(
        "--template-path",
        default=str(PROTOTYPE_TEMPLATE_PATH),
        help="Path to the prototype template CSV.",
    )
    parser.add_argument(
        "--price-dir",
        default=str(PRICE_OUTPUT_DIR),
        help="Directory that stores raw price CSV files.",
    )
    parser.add_argument(
        "--sec-dir",
        default=str(SEC_OUTPUT_DIR),
        help="Directory that stores SEC companyfacts JSON files.",
    )
    parser.add_argument(
        "--output-path",
        default=str(PROTOTYPE_PROCESSED_PATH),
        help="Output path for the built prototype CSV.",
    )
    parser.add_argument(
        "--primary-pre-days",
        type=int,
        default=5,
        help="Trading days before anchor date for primary event window start.",
    )
    parser.add_argument(
        "--primary-post-days",
        type=int,
        default=5,
        help="Trading days after anchor date for primary event window end.",
    )
    parser.add_argument(
        "--secondary-pre-days",
        type=int,
        default=5,
        help="Trading days before anchor date for secondary event window start.",
    )
    parser.add_argument(
        "--secondary-post-days",
        type=int,
        default=5,
        help="Trading days after anchor date for secondary event window end.",
    )
    parser.add_argument(
        "--benchmark",
        default="GSPC",
        help="Benchmark CSV symbol in price dir (default: GSPC).",
    )
    return parser.parse_args()


def load_price_frame(price_path: Path) -> pd.DataFrame:
    raw = pd.read_csv(price_path)
    if raw.empty or len(raw) < 3:
        raise ValueError(f"Price file has no usable rows: {price_path}")

    data = raw.iloc[2:].copy()
    data = data.rename(columns={"Price": "Date"})
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])

    for column in ["Adj Close", "Close", "High", "Low", "Open", "Volume"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    data = data.sort_values("Date").reset_index(drop=True)
    return data


def compute_event_window(
    prices: pd.DataFrame,
    anchor: pd.Timestamp,
    pre_days: int,
    post_days: int,
) -> dict[str, Any] | None:
    if prices.empty:
        return None

    event_candidates = prices.index[prices["Date"] >= anchor]
    if len(event_candidates) == 0:
        event_idx = len(prices) - 1
    else:
        event_idx = int(event_candidates[0])

    start_idx = max(0, event_idx - pre_days)
    end_idx = min(len(prices) - 1, event_idx + post_days)

    start_row = prices.iloc[start_idx]
    end_row = prices.iloc[end_idx]
    pre_close = float(start_row["Close"])
    post_close = float(end_row["Close"])
    if pre_close == 0 or math.isnan(pre_close) or math.isnan(post_close):
        return None

    return {
        "window_start": start_row["Date"].date().isoformat(),
        "window_end": end_row["Date"].date().isoformat(),
        "pre_close": pre_close,
        "post_close": post_close,
        "return": (post_close / pre_close) - 1,
    }


def iter_metric_points(company_facts: dict, tags: list[str]) -> list[MetricPoint]:
    us_gaap = company_facts.get("facts", {}).get("us-gaap", {})
    points: list[MetricPoint] = []
    for tag in tags:
        concept = us_gaap.get(tag, {})
        units = concept.get("units", {})
        for unit_name in ("USD", "shares", "USD/shares"):
            if unit_name not in units:
                continue
            for row in units[unit_name]:
                form = row.get("form", "")
                if form and form not in VALID_FORMS:
                    continue
                end = pd.to_datetime(row.get("end"), errors="coerce")
                val = row.get("val")
                if pd.isna(end) or val is None:
                    continue
                points.append(
                    MetricPoint(
                        end=end,
                        val=float(val),
                        form=form,
                        fy=row.get("fy"),
                        fp=row.get("fp", ""),
                    )
                )
            if points:
                return points
    return points


def build_point_lookup(points: list[MetricPoint]) -> dict[tuple[pd.Timestamp, str, int | None, str], float]:
    lookup: dict[tuple[pd.Timestamp, str, int | None, str], float] = {}
    for p in points:
        lookup[(p.end.normalize(), p.form, p.fy, p.fp)] = p.val
    return lookup


def select_latest_period_metrics(company_facts: dict, anchor: pd.Timestamp) -> dict[str, float | None]:
    revenue_points = [p for p in iter_metric_points(company_facts, REVENUE_TAGS) if p.end <= anchor]
    revenue_points = sorted(revenue_points, key=lambda x: x.end, reverse=True)
    if not revenue_points:
        return {
            "revenue_growth": None,
            "gross_margin": None,
            "operating_margin": None,
            "rd_to_revenue": None,
            "sm_to_revenue": None,
            "market_cap": None,
            "ps_ratio": None,
        }

    gross_lookup = build_point_lookup(iter_metric_points(company_facts, GROSS_PROFIT_TAGS))
    op_lookup = build_point_lookup(iter_metric_points(company_facts, OPERATING_INCOME_TAGS))
    rd_lookup = build_point_lookup(iter_metric_points(company_facts, RD_EXPENSE_TAGS))
    sm_lookup = build_point_lookup(iter_metric_points(company_facts, SM_EXPENSE_TAGS))
    shares_points = [p for p in iter_metric_points(company_facts, SHARES_OUTSTANDING_TAGS) if p.end <= anchor]
    shares_points = sorted(shares_points, key=lambda x: x.end, reverse=True)

    selected = revenue_points[0]
    selected_key = (selected.end.normalize(), selected.form, selected.fy, selected.fp)

    previous_revenue = None
    for p in revenue_points[1:]:
        if p.fp == selected.fp and p.end < selected.end:
            previous_revenue = p.val
            break

    def safe_ratio(num: float | None, den: float | None) -> float | None:
        if num is None or den in (None, 0):
            return None
        return num / den

    revenue = selected.val
    gross_profit = gross_lookup.get(selected_key)
    operating_income = op_lookup.get(selected_key)
    rd_expense = rd_lookup.get(selected_key)
    sm_expense = sm_lookup.get(selected_key)

    revenue_growth = None
    if previous_revenue not in (None, 0):
        revenue_growth = (revenue / previous_revenue) - 1

    shares = shares_points[0].val if shares_points else None
    market_cap = None
    if shares and shares > 0:
        market_cap = shares  # placeholder; multiplied by price later

    return {
        "revenue_growth": revenue_growth,
        "gross_margin": safe_ratio(gross_profit, revenue),
        "operating_margin": safe_ratio(operating_income, revenue),
        "rd_to_revenue": safe_ratio(rd_expense, revenue),
        "sm_to_revenue": safe_ratio(sm_expense, revenue),
        "market_cap": market_cap,
        "ps_ratio": None,
    }


def to_pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)


def main() -> None:
    args = parse_args()

    template_path = Path(args.template_path)
    price_dir = Path(args.price_dir)
    sec_dir = Path(args.sec_dir)
    output_path = Path(args.output_path)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(template_path)
    for col in (
        "primary_event_window_start",
        "primary_event_window_end",
        "secondary_event_window_start",
        "secondary_event_window_end",
        "data_completeness_notes",
    ):
        if col in df.columns:
            df[col] = df[col].astype("object")

    benchmark_prices = load_price_frame(price_dir / f"{args.benchmark}.csv")
    notes: list[str] = []

    for idx, row in df.iterrows():
        ticker = str(row["ticker"]).upper()
        primary_anchor = pd.to_datetime(row["market_attention_anchor_date"], errors="coerce")
        secondary_anchor = pd.to_datetime(row["github_launch_date"], errors="coerce")

        price_path = price_dir / f"{ticker}.csv"
        sec_path = sec_dir / f"{ticker.lower()}_companyfacts.json"
        if not price_path.exists():
            notes.append(f"{ticker}: missing price file")
            continue
        if not sec_path.exists():
            notes.append(f"{ticker}: missing SEC facts file")
            continue

        prices = load_price_frame(price_path)
        primary_window = compute_event_window(
            prices=prices,
            anchor=primary_anchor,
            pre_days=args.primary_pre_days,
            post_days=args.primary_post_days,
        )
        secondary_window = compute_event_window(
            prices=prices,
            anchor=secondary_anchor,
            pre_days=args.secondary_pre_days,
            post_days=args.secondary_post_days,
        )

        benchmark_window = compute_event_window(
            prices=benchmark_prices,
            anchor=primary_anchor,
            pre_days=args.primary_pre_days,
            post_days=args.primary_post_days,
        )

        if primary_window:
            df.at[idx, "primary_event_window_start"] = primary_window["window_start"]
            df.at[idx, "primary_event_window_end"] = primary_window["window_end"]
            df.at[idx, "pre_event_close"] = round(primary_window["pre_close"], 6)
            df.at[idx, "post_event_close"] = round(primary_window["post_close"], 6)
            df.at[idx, "cumulative_return"] = to_pct(primary_window["return"])

        if secondary_window:
            df.at[idx, "secondary_event_window_start"] = secondary_window["window_start"]
            df.at[idx, "secondary_event_window_end"] = secondary_window["window_end"]

        if benchmark_window:
            benchmark_return = to_pct(benchmark_window["return"])
            df.at[idx, "benchmark_return"] = benchmark_return
            if primary_window and benchmark_return is not None:
                df.at[idx, "excess_return"] = to_pct(
                    float(primary_window["return"]) - float(benchmark_return)
                )

        company_facts = json.loads(sec_path.read_text(encoding="utf-8"))
        ratios = select_latest_period_metrics(company_facts=company_facts, anchor=primary_anchor)
        for col in ("revenue_growth", "gross_margin", "operating_margin", "rd_to_revenue", "sm_to_revenue"):
            df.at[idx, col] = to_pct(ratios[col]) if ratios[col] is not None else None

        if ratios["market_cap"] is not None and primary_window:
            df.at[idx, "market_cap"] = round(
                float(ratios["market_cap"]) * float(primary_window["post_close"]),
                3,
            )

        df.at[idx, "data_completeness_notes"] = f"benchmark={args.benchmark}"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"[build] wrote {output_path}")
    if notes:
        print("[build] warnings:")
        for line in notes:
            print(f"- {line}")


if __name__ == "__main__":
    main()
