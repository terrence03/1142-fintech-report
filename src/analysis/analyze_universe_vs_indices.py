"""Analyze a company universe basket versus major US indices."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def df_to_markdown(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = []
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            vals.append("" if pd.isna(v) else str(v))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join([header, sep, *rows])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze company basket versus indices.")
    parser.add_argument("--template-path", required=True, help="Universe template CSV path.")
    parser.add_argument("--price-dir", default="data/raw/prices", help="Price CSV directory.")
    parser.add_argument(
        "--output-csv",
        default="results/tables/universe_vs_indices_summary.csv",
        help="Output summary CSV path.",
    )
    parser.add_argument(
        "--output-md",
        default="results/reports/universe_vs_indices_summary.md",
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--indices",
        nargs="*",
        default=["GSPC", "IXIC", "DJI"],
        help="Index symbols stored as CSV filenames without '^'.",
    )
    return parser.parse_args()


def load_price_frame(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    frame = raw.iloc[2:].copy()
    frame = frame.rename(columns={"Price": "Date"})
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    frame = frame[["Date", "Close"]].dropna().sort_values("Date").reset_index(drop=True)
    frame["ret"] = frame["Close"].pct_change()
    return frame


def nearest_idx(frame: pd.DataFrame, anchor: pd.Timestamp) -> int:
    candidates = frame.index[frame["Date"] >= anchor]
    if len(candidates) == 0:
        return len(frame) - 1
    return int(candidates[0])


def event_window_return(frame: pd.DataFrame, col: str, anchor: pd.Timestamp, pre: int = 5, post: int = 5) -> float:
    i = nearest_idx(frame, anchor)
    s = max(0, i - pre)
    e = min(len(frame) - 1, i + post)
    return float(frame.iloc[e][col] / frame.iloc[s][col] - 1.0)


def main() -> None:
    args = parse_args()
    template = pd.read_csv(args.template_path)
    tickers = template["ticker"].astype(str).str.upper().tolist()
    price_dir = Path(args.price_dir)

    series = []
    available_tickers: list[str] = []
    missing_tickers: list[str] = []
    for ticker in tickers:
        path = price_dir / f"{ticker}.csv"
        if not path.exists():
            missing_tickers.append(ticker)
            continue
        d = load_price_frame(path).rename(columns={"Close": ticker})
        series.append(d[["Date", ticker]])
        available_tickers.append(ticker)

    if not series:
        raise RuntimeError("No company price files found for analysis.")

    panel = series[0]
    for s in series[1:]:
        panel = panel.merge(s, on="Date", how="inner")

    norm = panel.copy()
    for ticker in available_tickers:
        norm[ticker] = norm[ticker] / norm[ticker].iloc[0] * 100.0
    norm["basket_mean"] = norm[available_tickers].mean(axis=1)

    index_norm: dict[str, pd.DataFrame] = {}
    index_rets: dict[str, pd.DataFrame] = {}
    missing_indices: list[str] = []
    for idx in args.indices:
        idx_path = price_dir / f"{idx}.csv"
        if not idx_path.exists():
            missing_indices.append(idx)
            continue
        d = load_price_frame(idx_path)
        d["norm"] = d["Close"] / d["Close"].iloc[0] * 100.0
        index_norm[idx] = d[["Date", "norm"]]
        index_rets[idx] = d[["Date", "ret"]]

    compare = norm[["Date", "basket_mean"]].copy()
    for idx, d in index_norm.items():
        compare = compare.merge(d.rename(columns={"norm": idx}), on="Date", how="inner")

    primary = pd.to_datetime(template["market_attention_anchor_date"].iloc[0], errors="coerce")
    secondary = pd.to_datetime(template["github_launch_date"].iloc[0], errors="coerce")

    rows = []
    for name in ["basket_mean", *index_norm.keys()]:
        total_ret = float(compare.iloc[-1][name] / compare.iloc[0][name] - 1.0)
        primary_ret = event_window_return(compare, name, primary)
        secondary_ret = event_window_return(compare, name, secondary)
        rows.append(
            {
                "series": name,
                "period_return": round(total_ret, 6),
                "primary_window_return": round(primary_ret, 6),
                "secondary_window_return": round(secondary_ret, 6),
            }
        )

    ret_panel = load_price_frame(price_dir / f"{available_tickers[0]}.csv")[["Date", "ret"]].rename(
        columns={"ret": available_tickers[0]}
    )
    for ticker in available_tickers[1:]:
        ret_panel = ret_panel.merge(
            load_price_frame(price_dir / f"{ticker}.csv")[["Date", "ret"]].rename(columns={"ret": ticker}),
            on="Date",
            how="inner",
        )
    ret_panel["basket_ret"] = ret_panel[available_tickers].mean(axis=1)

    vol_rows = [{"series": "basket_mean", "daily_volatility": round(float(ret_panel["basket_ret"].std()), 6)}]
    corr_rows = []
    for idx, d in index_rets.items():
        merged = ret_panel[["Date", "basket_ret"]].merge(d.rename(columns={"ret": idx}), on="Date", how="inner").dropna()
        vol_rows.append({"series": idx, "daily_volatility": round(float(merged[idx].std()), 6)})
        corr_rows.append(
            {"series": idx, "basket_index_correlation": round(float(merged["basket_ret"].corr(merged[idx])), 6)}
        )

    summary_df = pd.DataFrame(rows)
    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(output_csv, index=False)

    md_lines = [
        "# Universe vs Indices Summary",
        "",
        f"- Universe size (requested): {len(tickers)}",
        f"- Universe size (available prices): {len(available_tickers)}",
        f"- Date range used: {compare['Date'].min().date()} to {compare['Date'].max().date()}",
        f"- Primary event date: {primary.date()}",
        f"- Secondary event date: {secondary.date()}",
        "",
        "## Return Summary",
        "",
        df_to_markdown(summary_df),
        "",
        "## Daily Volatility",
        "",
        df_to_markdown(pd.DataFrame(vol_rows)),
        "",
        "## Basket Correlation With Indices",
        "",
        df_to_markdown(pd.DataFrame(corr_rows)),
    ]
    if missing_tickers:
        md_lines.extend(["", "## Missing Tickers", "", ", ".join(missing_tickers)])
    if missing_indices:
        md_lines.extend(["", "## Missing Indices", "", ", ".join(missing_indices)])

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"[analyze] wrote {output_csv}")
    print(f"[analyze] wrote {output_md}")
    if missing_tickers:
        print(f"[analyze] missing tickers: {', '.join(missing_tickers)}")
    if missing_indices:
        print(f"[analyze] missing indices: {', '.join(missing_indices)}")


if __name__ == "__main__":
    main()
