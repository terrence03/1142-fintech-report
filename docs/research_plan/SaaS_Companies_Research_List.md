# SaaS 企業研究名單：候選樣本宇宙與 2 週驗證樣本

本文件不再使用人工 A/B 分組，而是將樣本拆成兩層：

1. **候選樣本宇宙**：正式報告可擴展的公開 SaaS 公司池
2. **2 週驗證樣本**：用於 feasibility prototype 的 12-15 家公司

研究原則為：優先保留在事件窗口前後資料較完整、業務模式具代表性、且能取得公開股價與公開財報的公司。

## 1. 候選樣本宇宙
以下公司可作為正式報告的候選樣本池。名單刻意保留跨子領域配置，以便後續由資料自行形成集群，而不是先驗分類。

| 序號 | 公司名稱 | 股票代碼 (Ticker) | 核心領域 | 備註 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | CrowdStrike | CRWD | 網絡安全 | 代表性高、資料完整度預期較佳 |
| 2 | Zscaler | ZS | 網絡安全 | 企業級安全平台 |
| 3 | Palo Alto Networks | PANW | 網絡安全 | 平台型安全廠商 |
| 4 | Datadog | DDOG | 可觀測性 | 雲端基礎設施監測 |
| 5 | Dynatrace | DT | 可觀測性 | 全棧監控與 AI 診斷 |
| 6 | Snowflake | SNOW | 數據雲 | 資料平台代表 |
| 7 | Veeva Systems | VEEV | 垂直 SaaS | 高合規垂直軟體 |
| 8 | Autodesk | ADSK | 設計軟體 | 專業工作流與格式壁壘 |
| 9 | ServiceNow | NOW | ITSM / Workflow | 大型企業流程平台 |
| 10 | Workday | WDAY | HCM / Finance | 核心人資與財務系統 |
| 11 | Cloudflare | NET | 網路與安全 | 邊緣計算與安全網關 |
| 12 | Okta | OKTA | 身份管理 | IAM 代表廠商 |
| 13 | Guidewire | GWRE | 保險軟體 | 垂直企業軟體 |
| 14 | Manhattan Associates | MANH | 供應鏈軟體 | 物流與倉儲工作流 |
| 15 | Asana | ASAN | 專案管理 | 協作型 SaaS |
| 16 | Monday.com | MNDY | 專案管理 | 通用工作管理 |
| 17 | HubSpot | HUBS | CRM / Marketing | 通用 CRM 代表 |
| 18 | Freshworks | FRSH | 客服 / CRM | 中型企業 SaaS |
| 19 | Dropbox | DBX | 文件協作 | 文件平台代表 |
| 20 | Box | BOX | 內容管理 | 企業文件管理 |
| 21 | DocuSign | DOCU | 電子簽名 | 單點工作流代表 |
| 22 | Zoom | ZM | 視訊協作 | 協作與通訊平台 |
| 23 | Sprout Social | SPT | 社群管理 | 社群工具代表 |
| 24 | Atlassian | TEAM | 開發協作 | 開發工作流平台 |
| 25 | Braze | BRZE | 客戶互動 | 行銷自動化 |
| 26 | Twilio | TWLO | 通訊 API | 開發者平台型 SaaS |

## 2. 建議排除或暫緩納入樣本
以下公司不建議作為 2 週驗證樣本主體，原因是公開資料連續性、上市狀態或可比性較弱。

| 公司名稱 | 原因 |
| :--- | :--- |
| Zendesk | 已私有化，無法作為公開市場事件研究主樣本 |
| Slack | 已被 Salesforce 收購，無獨立公開市場價格 |
| HashiCorp | 若事件窗口內上市狀態或資料連續性不足，應移出主樣本 |
| Smartsheet | 若事件窗口內發生交易或上市狀態變化，應暫緩納入 |

## 3. 2 週驗證樣本建議名單
2 週 feasibility prototype 以 14 家公司為建議起點，兼顧資料完整度、子領域多樣性與後續集群可解釋性。

| 序號 | 公司名稱 | 股票代碼 (Ticker) | 角色 |
| :--- | :--- | :--- | :--- |
| 1 | CrowdStrike | CRWD | 高成長安全平台代表 |
| 2 | Zscaler | ZS | 安全與網路基礎設施代表 |
| 3 | Datadog | DDOG | 可觀測性代表 |
| 4 | Snowflake | SNOW | 數據雲代表 |
| 5 | ServiceNow | NOW | 大型企業工作流代表 |
| 6 | Workday | WDAY | 企業核心系統代表 |
| 7 | Cloudflare | NET | 邊緣運算與安全代表 |
| 8 | Asana | ASAN | 專案管理代表 |
| 9 | Monday.com | MNDY | 工作管理代表 |
| 10 | HubSpot | HUBS | CRM / 行銷代表 |
| 11 | Dropbox | DBX | 文件協作代表 |
| 12 | DocuSign | DOCU | 單點工作流代表 |
| 13 | Atlassian | TEAM | 開發協作代表 |
| 14 | Twilio | TWLO | API / 通訊平台代表 |

## 4. 欄位字典與資料來源規則
2 週驗證階段建議只保留 6-8 個核心欄位，全部來自公開來源。

| 欄位 | 定義 | 主要來源 |
| :--- | :--- | :--- |
| `revenue_growth` | YoY 營收成長率 | 10-Q / 10-K / earnings release |
| `gross_margin` | 毛利率 | 10-Q / 10-K |
| `operating_margin` | 營業利益率 | 10-Q / 10-K |
| `rd_to_revenue` | 研發費用 / 營收 | 10-Q / 10-K |
| `sm_to_revenue` | 銷售與行銷費用 / 營收 | 10-Q / 10-K |
| `fcf_margin` | 自由現金流 / 營收 | earnings release 或現金流量表推估 |
| `ps_ratio` | 市銷率 | 公開股價 + 營收資料推算 |
| `market_cap` | 市值 | 公開股價資料 |

## 5. 資料處理原則
- 若公司未穩定揭露 `fcf_margin`，可在 2 週驗證版中先排除該欄位。
- 若事件日前後缺少完整季度資料，保留於市場面分析，但不納入基本面比較。
- 集群分析先以標準化後的公開欄位為主，不加入主觀質化分數。
- 正式報告擴樣前，需先完成每家公司資料可得性檢查表。
