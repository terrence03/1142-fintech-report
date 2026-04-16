"""Fetch A-grade public data for the OpenClaw SaaS prototype.

A-grade data in this project means:
- Daily price history for the prototype company universe
- Benchmark index price history
- Core SEC company facts needed to derive revenue growth and operating metrics

This script intentionally stays small and explicit so the feasibility stage is easy
to audit and adjust when a company uses slightly different XBRL tags.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import (
    DEFAULT_BENCHMARK_TICKERS,
    DEFAULT_REQUEST_TIMEOUT,
    PRICE_OUTPUT_DIR,
    PROTOTYPE_TEMPLATE_PATH,
    SEC_OUTPUT_DIR,
)

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - handled at runtime
    yf = None


SEC_TICKER_CIK_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"

PRIMARY_SEC_METRICS = {
    "revenue": [
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomer",
        "SalesRevenueGoodsNet",
        "SalesRevenueNet",
        "SalesRevenueServicesNet",
        "Revenues",
        "RevenueMineralSales",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
        "IncomeLossFromOperations",
    ],
}


@dataclass(frozen=True)
class Company:
    company_name: str
    ticker: str
    sector_bucket: str


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        # Respect values that are already set by the runtime environment.
        os.environ.setdefault(key, value)


def load_companies(template_path: Path) -> list[Company]:
    with template_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            Company(
                company_name=row["company_name"].strip(),
                ticker=row["ticker"].strip().upper(),
                sector_bucket=row["sector_bucket"].strip(),
            )
            for row in reader
            if row.get("ticker")
        ]


def ensure_output_dirs() -> None:
    PRICE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SEC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_price_history(
    tickers: Iterable[str],
    start: str,
    end: str,
    benchmark_tickers: Iterable[str],
) -> None:
    if yf is None:
        raise RuntimeError(
            "Missing optional dependency 'yfinance'. Install it before fetching price data."
        )

    all_tickers = list(dict.fromkeys([*tickers, *benchmark_tickers]))
    for ticker in all_tickers:
        history = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False,
            interval="1d",
            threads=False,
        )
        if history.empty:
            print(f"[prices] no data returned for {ticker}")
            continue

        output_path = PRICE_OUTPUT_DIR / f"{sanitize_symbol(ticker)}.csv"
        history.to_csv(output_path)
        print(f"[prices] wrote {output_path}")


def sanitize_symbol(symbol: str) -> str:
    return symbol.replace("^", "")


def build_sec_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
    )
    return session


def fetch_ticker_cik_map(session: requests.Session) -> dict[str, str]:
    response = session.get(SEC_TICKER_CIK_URL, timeout=DEFAULT_REQUEST_TIMEOUT)
    response.raise_for_status()

    payload = response.json()
    mapping: dict[str, str] = {}
    for item in payload.values():
        ticker = item["ticker"].upper()
        cik = str(item["cik_str"]).zfill(10)
        mapping[ticker] = cik
    return mapping


def fetch_company_facts(session: requests.Session, cik: str) -> dict:
    url = SEC_COMPANY_FACTS_URL.format(cik=cik)
    response = session.get(url, timeout=DEFAULT_REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def select_metric_units(company_facts: dict, concept_names: list[str]) -> tuple[list[dict], str]:
    us_gaap = company_facts.get("facts", {}).get("us-gaap", {})
    for concept_name in concept_names:
        concept = us_gaap.get(concept_name)
        if not concept:
            continue
        units = concept.get("units", {})
        for unit_name in ("USD", "USD/shares", "shares"):
            if unit_name in units:
                return units[unit_name], concept_name
        if units:
            first_unit_name = next(iter(units))
            return units[first_unit_name], concept_name
    return [], ""


def collect_available_metrics(company_facts: dict) -> dict[str, dict[str, str | list[dict]]]:
    available: dict[str, dict[str, str | list[dict]]] = {}
    for metric_name, concept_names in PRIMARY_SEC_METRICS.items():
        points, source_tag = select_metric_units(company_facts, concept_names)
        available[metric_name] = {"points": points, "source_tag": source_tag}
    return available


def write_company_facts(output_path: Path, payload: dict) -> None:
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def fetch_sec_data(companies: Iterable[Company], user_agent: str, pause_seconds: float) -> None:
    if not user_agent:
        raise RuntimeError(
            "SEC requests require a descriptive user agent. Pass --sec-user-agent or set SEC_USER_AGENT."
        )

    session = build_sec_session(user_agent)
    ticker_to_cik = fetch_ticker_cik_map(session)

    summary_rows: list[dict[str, str]] = []
    for company in companies:
        cik = ticker_to_cik.get(company.ticker)
        if not cik:
            summary_rows.append(
                {
                    "ticker": company.ticker,
                    "company_name": company.company_name,
                    "cik": "",
                    "status": "ticker_not_found",
                    "revenue_points": "0",
                    "operating_income_points": "0",
                    "revenue_tag": "",
                    "operating_income_tag": "",
                }
            )
            print(f"[sec] missing CIK for {company.ticker}")
            continue

        try:
            facts = fetch_company_facts(session, cik)
        except requests.HTTPError as exc:
            summary_rows.append(
                {
                    "ticker": company.ticker,
                    "company_name": company.company_name,
                    "cik": cik,
                    "status": f"http_error_{exc.response.status_code}",
                    "revenue_points": "0",
                    "operating_income_points": "0",
                    "revenue_tag": "",
                    "operating_income_tag": "",
                }
            )
            print(f"[sec] failed for {company.ticker}: {exc}")
            time.sleep(pause_seconds)
            continue

        output_path = SEC_OUTPUT_DIR / f"{company.ticker.lower()}_companyfacts.json"
        write_company_facts(output_path, facts)

        metrics = collect_available_metrics(facts)
        summary_rows.append(
            {
                "ticker": company.ticker,
                "company_name": company.company_name,
                "cik": cik,
                "status": "ok",
                "revenue_points": str(len(metrics["revenue"]["points"])),
                "operating_income_points": str(len(metrics["operating_income"]["points"])),
                "revenue_tag": str(metrics["revenue"]["source_tag"]),
                "operating_income_tag": str(metrics["operating_income"]["source_tag"]),
            }
        )
        print(f"[sec] wrote {output_path}")
        time.sleep(pause_seconds)

    summary_path = SEC_OUTPUT_DIR / "availability_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ticker",
                "company_name",
                "cik",
                "status",
                "revenue_points",
                "operating_income_points",
                "revenue_tag",
                "operating_income_tag",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"[sec] wrote {summary_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch A-grade public research data.")
    parser.add_argument(
        "--template-path",
        default=str(PROTOTYPE_TEMPLATE_PATH),
        help="Path to the prototype company template CSV.",
    )
    parser.add_argument(
        "--start-date",
        default="2025-09-01",
        help="Inclusive price history start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end-date",
        default="2026-03-31",
        help="Exclusive price history end date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--benchmarks",
        nargs="*",
        default=list(DEFAULT_BENCHMARK_TICKERS),
        help="Benchmark tickers to fetch alongside the company universe.",
    )
    parser.add_argument(
        "--skip-prices",
        action="store_true",
        help="Skip the price history download step.",
    )
    parser.add_argument(
        "--skip-sec",
        action="store_true",
        help="Skip the SEC company facts download step.",
    )
    parser.add_argument(
        "--sec-user-agent",
        default=os.environ.get("SEC_USER_AGENT", ""),
        help="Descriptive SEC user agent, e.g. 'Your Name your_email@example.com'.",
    )
    parser.add_argument(
        "--sec-pause-seconds",
        type=float,
        default=0.25,
        help="Pause between SEC requests to stay polite.",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file(DEFAULT_ENV_PATH)
    args = parse_args()
    companies = load_companies(Path(args.template_path))
    ensure_output_dirs()

    if not args.skip_prices:
        fetch_price_history(
            tickers=[company.ticker for company in companies],
            start=args.start_date,
            end=args.end_date,
            benchmark_tickers=args.benchmarks,
        )

    if not args.skip_sec:
        fetch_sec_data(
            companies=companies,
            user_agent=args.sec_user_agent,
            pause_seconds=args.sec_pause_seconds,
        )


if __name__ == "__main__":
    main()
