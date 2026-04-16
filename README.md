# OpenClaw SaaS Research

本專案使用常見研究專案目錄結構，將研究文件、對話記錄、程式碼與資料分開管理，方便後續擴充、版本控制與協作。

## 目錄結構

```text
1142-fintech-report/
├── docs/
│   ├── chat_logs/
│   └── research_plan/
├── src/
│   ├── analysis/
│   ├── data_collection/
│   └── utils/
├── data/
│   ├── external/
│   ├── interim/
│   ├── processed/
│   ├── raw/
│   └── templates/
├── results/
│   ├── figures/
│   ├── reports/
│   └── tables/
└── README.md
```

## 使用原則

- `docs/chat_logs/`：放對話記錄、決策備忘與工作紀錄
- `docs/research_plan/`：放研究計畫、樣本清單、進度追蹤與 feasibility memo
- `src/data_collection/`：放資料蒐集與整理腳本
- `src/analysis/`：放事件研究、集群分析與報告分析腳本
- `src/utils/`：放共用函式與工具
- `data/raw/`：放原始下載資料
- `data/interim/`：放清理中的中繼資料
- `data/processed/`：放分析用整理後資料
- `data/external/`：放外部參考資料
- `data/templates/`：放資料模板
- `results/`：放圖表、表格與研究輸出
