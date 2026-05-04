"""Quality check: missing-value audit and numeric validity for the prototype dataset."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import PROCESSED_DATA_DIR, PROTOTYPE_PROCESSED_PATH

FEATURE_COLS = [
    "market_cap",
    "ps_ratio",
    "revenue_growth",
    "gross_margin",
    "operating_margin",
    "rd_to_revenue",
    "sm_to_revenue",
    "fcf_margin",
]

MARKET_IMPACT_COLS = [
    "cumulative_return",
    "benchmark_return",
    "excess_return",
]


def _missing_rate(series: pd.Series) -> float:
    return series.isna().mean()


def column_report(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for col in cols:
        if col not in df.columns:
            rows.append({"column": col, "present": 0, "missing": len(df), "missing_rate": 1.0, "status": "欄位不存在"})
            continue
        missing = int(df[col].isna().sum())
        present = len(df) - missing
        rate = missing / len(df)
        if rate == 0:
            status = "OK"
        elif rate < 0.3:
            status = "輕微缺值"
        elif rate < 0.7:
            status = "中度缺值"
        else:
            status = "嚴重缺值"
        rows.append({
            "column": col,
            "present": present,
            "missing": missing,
            "missing_rate": round(rate, 2),
            "status": status,
        })
    return pd.DataFrame(rows)


def company_report(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    available_cols = [c for c in cols if c in df.columns]
    rows = []
    for _, row in df.iterrows():
        missing_fields = [c for c in available_cols if pd.isna(row[c])]
        rate = len(missing_fields) / len(available_cols) if available_cols else 0
        rows.append({
            "ticker": row["ticker"],
            "company_name": row["company_name"],
            "missing_fields": len(missing_fields),
            "total_fields": len(available_cols),
            "missing_rate": round(rate, 2),
            "missing_list": ", ".join(missing_fields) if missing_fields else "-",
        })
    return pd.DataFrame(rows).sort_values("missing_rate", ascending=False)


def print_table(title: str, df: pd.DataFrame) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(df.to_string(index=False))


_SIGN_EXPECTATIONS = {
    "gross_margin": ("正值", lambda v: v > 0),
    "rd_to_revenue": ("正值", lambda v: v > 0),
    "sm_to_revenue": ("正值", lambda v: v > 0),
    "market_cap": ("正值", lambda v: v > 0),
    "ps_ratio": ("正值", lambda v: v > 0),
}

_RANGE_EXPECTATIONS = {
    "gross_margin": (0.0, 1.0),
    "operating_margin": (-2.0, 1.0),
    "rd_to_revenue": (0.0, 2.0),
    "sm_to_revenue": (0.0, 2.0),
    "fcf_margin": (-3.0, 1.5),
    "revenue_growth": (-1.0, 5.0),
    "ps_ratio": (0.0, 100.0),
    "cumulative_return": (-1.0, 2.0),
    "excess_return": (-1.0, 2.0),
}


def validity_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*60}")
    print("  數值合理性檢查")
    print(f"{'='*60}")

    all_clear = True

    # sign check
    for col, (label, check) in _SIGN_EXPECTATIONS.items():
        if col not in df.columns:
            continue
        bad = df[df[col].notna() & ~df[col].apply(check)][["ticker", col]]
        if not bad.empty:
            all_clear = False
            print(f"[符號異常] {col} 預期{label}，以下公司不符：")
            print(bad.to_string(index=False))

    # range check
    for col, (lo, hi) in _RANGE_EXPECTATIONS.items():
        if col not in df.columns:
            continue
        bad = df[df[col].notna() & ((df[col] < lo) | (df[col] > hi))][["ticker", col]]
        if not bad.empty:
            all_clear = False
            print(f"[範圍異常] {col} 預期 [{lo}, {hi}]，以下公司超出：")
            print(bad.to_string(index=False))

    # MNDY data staleness check
    if "MNDY" in df["ticker"].values:
        print("\n[特殊說明] MNDY (Monday.com) 為外國私人發行人，申報 6-K（半年報）")
        print("  最新 SEC 資料期間為 2025-H1，距主事件日 2026-01-31 約 7 個月")
        print("  財務特徵欄位計算係以 2025-H1 數值年化，適用於趨勢方向判斷，不建議直接比較絕對值")

    if all_clear:
        print("所有欄位通過符號與範圍檢查，未發現異常。")


def numeric_summary(df: pd.DataFrame, cols: list[str]) -> None:
    available = [c for c in cols if c in df.columns]
    summary = df[available].describe().T[["mean", "std", "min", "max"]].round(4)
    print_table("特徵欄位描述統計", summary.reset_index().rename(columns={"index": "column"}))


def main() -> None:
    df = pd.read_csv(PROTOTYPE_PROCESSED_PATH)
    n = len(df)
    print(f"\n樣本數：{n} 家公司")

    col_rpt = column_report(df, FEATURE_COLS)
    print_table("特徵欄位缺值率", col_rpt)

    impact_rpt = column_report(df, MARKET_IMPACT_COLS)
    print_table("市場衝擊欄位缺值率", impact_rpt)

    company_rpt = company_report(df, FEATURE_COLS)
    print_table("公司層級缺值率（依缺值率排序）", company_rpt)

    numeric_summary(df, FEATURE_COLS + MARKET_IMPACT_COLS)

    validity_report(df)

    output_path = PROCESSED_DATA_DIR / "quality_check_report.csv"
    col_rpt.to_csv(output_path, index=False)
    print(f"\n[quality_check] 欄位缺值報告已儲存至 {output_path}")

    high_risk_cols = col_rpt[col_rpt["missing_rate"] >= 0.7]["column"].tolist()
    high_risk_companies = company_rpt[company_rpt["missing_rate"] >= 0.5]["ticker"].tolist()
    print(f"\n高風險欄位（缺值率 ≥ 70%）：{high_risk_cols if high_risk_cols else '無'}")
    print(f"高風險公司（特徵缺值率 ≥ 50%）：{high_risk_companies if high_risk_companies else '無'}")


if __name__ == "__main__":
    main()
