# Data Collection Code

此資料夾存放資料蒐集與清理腳本。

目前已提供：

- `fetch_a_grade_data.py`：抓取 prototype 階段的 A 級公開資料
  - 股價資料：公司樣本與基準指數日資料
  - SEC 結構化資料：公司 `companyfacts` JSON 與可得性摘要
- `build_prototype_dataset.py`：整理原始股價與 SEC 資料，輸出 prototype 資料表
- `fetch_market_indices.py`：抓取美股三大指數（S&P 500 / NASDAQ / DJIA）日資料

建議後續檔案：

- `fetch_sec_filings.py`
- `build_feature_table.py`
