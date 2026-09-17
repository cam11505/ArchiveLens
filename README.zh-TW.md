# ArchiveLens 1.2 — 本機圖片、漫畫、資料夾與 PDF 閱讀器

本機、唯讀、無遙測。直接閱讀圖片壓縮檔、圖片資料夾與 PDF，不修改來源，
也不把整本內容解壓或複製到暫存資料夾。

## 功能

- ZIP／CBZ、7Z、RAR／CBR、一般／遞迴圖片資料夾與本機 PDF。
- JPG／JPEG、PNG、WebP、BMP、TIFF（第一幀）、AVIF、JPEG 2000、靜態／動畫 GIF。
- ZipCrypto／AES ZIP、加密 7Z／RAR，以及 QtPdf 可處理的密碼 PDF；密碼僅留在
  目前工作階段記憶體，不寫入設定或閱讀紀錄。
- 每個來源的續讀位置、有限筆數的最近閱讀與應用程式層頁面書籤。
- 單頁／雙頁、第一頁封面、由左至右／由右至左與延遲載入縮圖。
- 符合頁面／跨頁、符合寬度、符合高度、實體像素 100%、縮放、旋轉、拖移及全螢幕。
- 保守的黑／白邊自動裁切，以及四邊獨立百分比手動裁切；所有裁切都只影響顯示。
- Windows x64 可攜 ZIP 與每使用者安裝程式，內含影像 codec、UnRAR 與 QtPdf。

## 開始使用

可攜版解開 ZIP 後執行 `ArchiveLens.exe`，並保留旁邊的 `_internal`。安裝版不需
管理員權限，會加入開始功能表與「開啟方式」，但不變更壓縮檔或 PDF 的預設程式。

| 操作 | 功能 |
| --- | --- |
| Ctrl+O | 開啟支援的壓縮檔或 PDF 檔案 |
| Ctrl+Shift+O | 開啟圖片資料夾 |
| 拖入單一支援檔案或資料夾 | 開啟內容，或安全切換目前內容來源 |
| ←／→ | 依閱讀方向翻頁 |
| PageUp／Backspace；PageDown／Space | 邏輯上一頁／下一頁或跨頁 |
| Home／End | 第一組／最後一組 |
| 0／2／3／1 | 符合頁面／寬度／高度／實體像素 100% |
| +／-／Ctrl+滾輪 | 縮放 |
| R／Shift+R | 向右／向左旋轉 |
| F／F11／Esc | 全螢幕／退出 |
| T | 縮圖側欄 |
| Ctrl+B | 加入／移除目前頁書籤 |

「檔案 > 開啟內容」保留原生檔案／資料夾選擇器；「檢視」選單可設定版面、Fit 與邊框裁切；「閱讀」選單可設定方向、封面、
遞迴資料夾、書籤與最近閱讀。

## 限制與資源界線

HEIC／HEIF 與 JPEG XL（JXL）未通過 v1.2 的授權、預檢或封裝成本門檻，因此不支援。
不支援多卷／巢狀壓縮檔、內容修改、PDF 註解／表單／OCR、保存密碼或解密後永久快取。
7Z 重複檔名不支援；RAR 連結項目略過；solid 壓縮檔不預讀鄰頁，翻頁可能較慢。

- 壓縮檔／資料夾／PDF 最多 100,000 個項目或頁面；遞迴資料夾最多 32 層，
  不追蹤 symlink、junction 或 reparse point。
- 單筆解壓 128 MiB、solid catalog 1 GiB、圖片 4,000 萬像素。
- PDF render 最多 1,600 萬像素、單邊 8,192 像素；每個 worker 只有一個可替換請求。
- 圖片快取 256 MiB、縮圖快取 64 MiB、單一 GIF 32 MiB。
- 自動裁切只分析最長邊 512 像素的縮圖，遇到不明確頁面會保留完整內容。

以上是個別元件限制，不代表程序總 RAM 上限，也不是惡意檔案沙箱。密碼不會進入
命令列、日誌、設定、閱讀狀態或 manifest；Python／原生函式庫無法保證清除所有
程序內不可變副本。

原始碼執行與封裝指令見 [English README](README.md)。另見
[DEVELOPMENT](docs/DEVELOPMENT.md)、[顯示政策](docs/READER_DISPLAY.md)、
[v1.2 QA](docs/V1.2_QA.md) 與 [v1.2 計畫](docs/V1.2_PLAN.md)。

## 授權

**ArchiveLens 自有應用程式原始碼採 MIT 授權，屬於自由／開放原始碼軟體。**
官方 binary 則是**混合授權（mixed-license）發行物**：Python、Qt／PySide、Pillow、
壓縮函式庫、UnRAR、Microsoft runtime 與其他隨附元件都保留各自授權，不會因為
ArchiveLens 採 MIT 就一起變成 MIT。

其中 Windows 版隨附的 UnRAR 依上游 freeware license 再散布；由於該授權包含用途／
逆向工程限制，ArchiveLens 不把這個元件分類為 FOSS。Microsoft Visual C++ runtime
也依 Microsoft 自有條款散布。

Release 會附完整第三方 notices、對應來源、SPDX SBOM 與經人工審核的 dependency
policy。詳見 [授權與散布政策](docs/LICENSING.md)、
[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md) 與 `license-policy.json`。
