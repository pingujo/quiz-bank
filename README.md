# 考古題入口（quiz-bank）

把各校**自己公開**的段考考古題頁面（學校官網、學校 Google 雲端硬碟／協作平台）整理成單一入口，
加上國中會考、高中學測官方歷屆試題。無廣告、不追蹤、不轉存試卷，點擊直接連回原始來源。

## 檔案
- `index.html`：入口頁（純前端，可直接放 GitHub Pages 等靜態空間）
- `data/sources.json`：來源清單（要新增或修改學校就改這裡）
- `data/sources.js`：由腳本自動產生，給網頁讀取，不要手改
- `tools/check_links.py`：重新檢查所有連結並產生 `sources.js`

## 本機預覽
```bash
cd quiz-bank && python3 -m http.server 8765
```
打開 http://localhost:8765 。也可以直接雙擊 index.html 開啟。

## 新增學校
在 `data/sources.json` 加一筆：
```json
{"level":"國中","city":"臺北市","school":"某某國中","subject":null,"kind":"學校網站",
 "official_exam":false,"url":"https://...","page_title":"","status":"ok","checked":""}
```
然後執行 `python3 tools/check_links.py`。

## 資料來源說明
清單（2026-11-22）彙整自 tcool.cc 與 exambank.darrenlu.com 公開列出的學校連結（每筆的 via 欄位記錄來源），逐一連線確認都是學校官方頁面或學校的雲端資料夾後才收錄。

## 逐校掃描（補新學校）
1. 下載教育部學校名錄（含官網網址）：
   - 國小：`https://stats.moe.gov.tw/files/school/115/e1_new.csv`
   - 國中：`https://stats.moe.gov.tw/files/school/113/j1_new.csv`（114 起此檔已下架，改年份試試）
2. 掃描（全國約 3,300 校、約 10 分鐘）：
   `python3 tools/scan_schools.py e1_new.csv j1_new.csv --out candidates.json`
   可加 `--only 雲林縣,金門縣` 只掃特定縣市。
3. 掃描結果雜訊多（會考連結、出版社題庫、命題辦法…），先人工看過再併入：
   `python3 tools/merge_scan.py candidates.json`
4. 最後跑 `python3 tools/check_links.py`。

2026-11-22 全國掃描結果：3,344 校中 3,128 校可連線，145 校有候選，過濾後新增 31 校。
