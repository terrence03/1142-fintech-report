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
COST_OF_REVENUE_TAGS = ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"]
RD_EXPENSE_TAGS = ["ResearchAndDevelopmentExpense"]
SM_EXPENSE_TAGS = ["SellingAndMarketingExpense"]
SHARES_OUTSTANDING_TAGS = [
    "CommonStockSharesOutstanding",
    "EntityCommonStockSharesOutstanding",
]
OCF_TAGS = ["NetCashProvidedByUsedInOperatingActivities"]
CAPEX_TAGS = ["PaymentsToAcquirePropertyPlantAndEquipment"]

# 6-K/6-K/A included for foreign private issuers (e.g. Monday.com)
VALID_FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A", "6-K", "6-K/A"}

# Multipliers to annualize cumulative-from-fiscal-year-start figures
_FP_ANNUALIZE = {"Q1": 4.0, "Q2": 2.0, "Q3": 4.0 / 3.0, "Q4": 1.0, "FY": 1.0}


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


def get_dei_shares(company_facts: dict, anchor: pd.Timestamp) -> float | None:
    """Return most recent shares outstanding from the DEI namespace before anchor."""
    dei = company_facts.get("facts", {}).get("dei", {})
    tag = "EntityCommonStockSharesOutstanding"
    if tag not in dei:
        return None
    rows = dei[tag].get("units", {}).get("shares", [])
    valid = [
        r for r in rows
        if pd.to_datetime(r.get("end", "1900-01-01"), errors="coerce") <= anchor
        and r.get("val", 0) > 0
    ]
    if not valid:
        return None
    latest = max(valid, key=lambda x: x["end"])
    # only use if within 18 months of anchor to avoid stale data
    if (anchor - pd.Timestamp(latest["end"])).days > 548:
        return None
    return float(latest["val"])


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
            "fcf_margin": None,
            "market_cap": None,
            "ttm_revenue": None,
        }

    gross_lookup = build_point_lookup(iter_metric_points(company_facts, GROSS_PROFIT_TAGS))
    cost_lookup = build_point_lookup(iter_metric_points(company_facts, COST_OF_REVENUE_TAGS))
    op_lookup = build_point_lookup(iter_metric_points(company_facts, OPERATING_INCOME_TAGS))
    rd_lookup = build_point_lookup(iter_metric_points(company_facts, RD_EXPENSE_TAGS))
    sm_lookup = build_point_lookup(iter_metric_points(company_facts, SM_EXPENSE_TAGS))
    ocf_lookup = build_point_lookup(iter_metric_points(company_facts, OCF_TAGS))
    capex_lookup = build_point_lookup(iter_metric_points(company_facts, CAPEX_TAGS))
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
    ttm_revenue = revenue * _FP_ANNUALIZE.get(selected.fp, 1.0)

    gross_profit = gross_lookup.get(selected_key)
    if gross_profit is None:
        # fallback: revenue - cost_of_revenue
        cost = cost_lookup.get(selected_key)
        if cost is not None:
            gross_profit = revenue - cost

    operating_income = op_lookup.get(selected_key)
    rd_expense = rd_lookup.get(selected_key)
    sm_expense = sm_lookup.get(selected_key)

    ocf = ocf_lookup.get(selected_key)
    capex = capex_lookup.get(selected_key)
    fcf: float | None = None
    if ocf is not None and capex is not None:
        fcf = ocf - capex
    elif ocf is not None:
        fcf = ocf

    revenue_growth = None
    if previous_revenue not in (None, 0):
        revenue_growth = (revenue / previous_revenue) - 1

    shares: float | None = shares_points[0].val if shares_points else None
    if not shares or shares <= 0:
        shares = get_dei_shares(company_facts, anchor)
    market_cap = None
    if shares and shares > 0:
        market_cap = shares  # placeholder; multiplied by price in main()

    return {
        "revenue_growth": revenue_growth,
        "gross_margin": safe_ratio(gross_profit, revenue),
        "operating_margin": safe_ratio(operating_income, revenue),
        "rd_to_revenue": safe_ratio(rd_expense, revenue),
        "sm_to_revenue": safe_ratio(sm_expense, revenue),
        "fcf_margin": safe_ratio(fcf, ttm_revenue),
        "market_cap": market_cap,
        "ttm_revenue": ttm_revenue,
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
        for col in ("revenue_growth", "gross_margin", "operating_margin", "rd_to_revenue", "sm_to_revenue", "fcf_margin"):
            df.at[idx, col] = to_pct(ratios[col]) if ratios[col] is not None else None

        computed_market_cap: float | None = None
        if ratios["market_cap"] is not None and primary_window:
            computed_market_cap = round(
                float(ratios["market_cap"]) * float(primary_window["post_close"]),
                3,
            )
            df.at[idx, "market_cap"] = computed_market_cap

        ttm_revenue = ratios.get("ttm_revenue")
        if computed_market_cap is not None and ttm_revenue:
            df.at[idx, "ps_ratio"] = round(computed_market_cap / ttm_revenue, 4)

        note_parts = [f"benchmark={args.benchmark}"]
        # 6-K filers use a different revenue base in XBRL; nullify cross-tag derived ratios
        sec_forms = {
            row.get("form", "")
            for facts_ns in company_facts.get("facts", {}).values()
            for concept in facts_ns.values()
            for unit_rows in concept.get("units", {}).values()
            for row in unit_rows
        }
        if "6-K" in sec_forms or "6-K/A" in sec_forms:
            for ratio_col in ("gross_margin", "operating_margin", "rd_to_revenue", "sm_to_revenue", "fcf_margin"):
                df.at[idx, ratio_col] = None
            note_parts.append("6-K filer: margin ratios nulled (XBRL revenue base mismatch)")
        df.at[idx, "data_completeness_notes"] = "; ".join(note_parts)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"[build] wrote {output_path}")
    if notes:
        print("[build] warnings:")
        for line in notes:
            print(f"- {line}")


if __name__ == "__main__":
    main()
