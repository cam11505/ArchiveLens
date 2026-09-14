# ArchiveLens 1.0

直接瀏覽 ZIP／CBZ 內的圖片，不必先將整份壓縮檔解壓。

## 開始使用

1. 從 [GitHub Releases](https://github.com/cam11505/ArchiveLens/releases) 下載
   `ArchiveLens-1.0.0-windows-x64.zip`。
2. 解壓**程式套件**，保留 `ArchiveLens.exe` 與 `_internal` 資料夾的相對位置。
3. 執行 `ArchiveLens.exe`，拖入自己的 ZIP／CBZ，或按「開啟」。

不需要安裝 Python。解壓程式套件與解壓照片檔案是不同的事情：程式只將目前與少量鄰頁
圖片讀入 RAM，不會將照片解壓到資料夾，也不會修改原始壓縮檔。

## v1.0 功能

- ZIP／CBZ 唯讀瀏覽、自然排序、Unicode 路徑。
- JPG、JPEG、PNG、WebP、BMP、GIF 第一幀；自動套用 EXIF Orientation。
- 上一張／下一張、頁碼、符合視窗、100%、縮放、拖移、左右旋轉、全螢幕。
- 背景載入與預讀，快速翻頁時舊結果不覆蓋目前頁面。
- 256 MiB LRU 快取，最多保留目前、前一張及後兩張。
- 加密、損壞、無圖片、過大 entry／圖片等可恢復錯誤提示。
- 本機執行，無圖片上傳、遙測、帳號或自動更新。

## 快捷鍵

| 操作 | 按鍵 |
| --- | --- |
| 開啟 | Ctrl+O |
| 下一張 | → / PageDown / Space |
| 上一張 | ← / PageUp / Backspace |
| 第一張／最後一張 | Home / End |
| 放大／縮小 | + / = / - |
| 符合視窗／100% | 0 / 1 |
| 向右／向左旋轉 | R / Shift+R |
| 全螢幕／離開全螢幕 | F / F11 / Esc |
| 縮放 | Ctrl+滑鼠滾輪 |
| 捲動／拖移 | 一般滾輪／按住左鍵拖曳 |
| 操作說明／結束 | F1 / Ctrl+Q |

100% 代表一個圖片像素對應一個螢幕實體像素，會考慮 Windows 顯示縮放比例。
翻頁保留 Fit／手動縮放模式，但重設旋轉角度。開啟新壓縮檔時回到 Fit。
在第一張／最後一張繼續翻頁會停留原頁。

## 限制

- Windows 10／11 x64 為目標；可攜版不包含簽章、安裝精靈或檔案關聯。
- 單 entry 解壓上限 128 MiB、壓縮比上限 1000、圖片上限 4,000 萬像素；
  Qt 單次解碼配置上限 256 MiB。這些不是整個程序的總 RAM 上限。
- 大型目錄、慢速磁碟及複雜壓縮資料仍可能需要等待；關閉時會等目前工作安全結束。
- GIF 只顯示第一幀。加密 ZIP、RAR／7Z、縮圖、雙頁、書籤與最近檔案不屬於 v1.0。
- ZIP 檔名依 UTF-8 flag／CP437 解讀，尚未提供舊式 Big5／CP932 手動選碼。
- 本機診斷紀錄位於作業系統的應用程式資料目錄，每檔 1 MiB、最多三檔；
  `--debug` 可能包含本機檔名，不記錄圖片內容。

## 從原始碼啟動與開發

需要 Python 3.12+。於專案目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-build.txt -e ".[dev,build]"
.\.venv\Scripts\python.exe -m archivelens
.\.venv\Scripts\python.exe -m pytest -q
```

也可雙擊 `Start-ArchiveLens.cmd`。安裝需要下載相依套件，程式本身可離線操作。
完整架構、打包與檢查指令見 [英文 README](README.md) 及
[開發與驗收紀錄](docs/DEVELOPMENT.md)。

## 授權

ArchiveLens 原始碼使用 MIT License。Python／Qt／PySide6 等保留原授權；
詳見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
