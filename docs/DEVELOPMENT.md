# ArchiveLens 1.0 開發與驗收

## 本次範圍

依原始提示詞完成 Milestone 1–5 的 ZIP／CBZ 圖片瀏覽 MVP。
不修改使用者原始壓縮檔、不將其中圖片整包解壓到硬碟。

## 架構決策

- `ArchiveProvider` 為唯讀介面，ZIP 實作隱藏 `ZipInfo`。
- `ArchiveEntry.index` 是 archive directory 內的原始索引，不是排序後頁碼。
  以 entry 身分驗證所屬開啟工作階段，重名檔案亦可分別讀取。
- 圖片清單依完整路徑逐層自然排序；副檔名不分大小寫。
- Qt 透過 `QByteArray`／`QBuffer` 解碼，目前 GIF 僅第一幀。
- 單一背景載入執行緒擁有 provider，GUI 不直接存取壓縮檔。
  尚未開始的請求只保留最新一筆；已開始的讀取結束後，以 request ID 防止舊結果覆蓋。
- 背景載入只建立 `QImage`；`QPixmap` 與所有 widget 更新在主執行緒。
- 快取以 `QImage.sizeInBytes()` 計算，LRU 上限 256 MiB；僅保留目前、前一張及後兩張。
  預讀在目前圖片結果送出後執行；有新導覽請求就停止後續預讀。
  預讀不會為了儲存鄰頁而淘汰目前頁；重新開檔會清除快取。
- 縮放範圍 1%–1600%，100% 為圖片像素對應螢幕實體像素；Fit 依視窗與旋轉後邊界計算。
  翻頁保留縮放模式與比例、重設旋轉；全螢幕退出恢復先前最大化／一般視窗狀態。
- ZIP 限制為單筆解壓資料 128 MiB、壓縮比 1000、圖片 4,000 萬像素；
  Qt 解碼配置上限 256 MiB。這些並非整個程序的 RAM 上限，也不是對任意惡意檔案的完整沙箱。
- ZIP 檔名遵循 Python zipfile 的 UTF-8 flag／CP437 規則；尚無舊式 Big5／CP932 手動選碼功能。

## v1.0 已涵蓋

- Milestone 1：ArchiveProvider、ZIP provider、篩選、自然排序、CLI。
- Milestone 2：主視窗、開檔／拖放、第一張、前後導覽、頁碼、快捷鍵。
- Milestone 3：Fit、100%、zoom、pan、rotate、fullscreen、EXIF 自動方向。
- Milestone 4：LRU、鄰頁預讀、背景載入、資源限制與競態防護。
- Milestone 5：錯誤提示、狀態列、說明、版本資訊、有限大小的本機 logging、
  中英文 README、MIT／第三方授權、Windows 可攜打包、GitHub CI。
- 最近檔案依原規格留待 v1.1；RAR／7Z、密碼、縮圖、雙頁等留待後續版本。

## 驗收範圍

本次測試涵蓋後端、Qt 記憶體解碼，以及 GUI 開啟、上一張／下一張、頁碼、
鍵盤、拖放事件和過期結果防護。自動 Qt 測試不代表已完成實際 Explorer 拖曳、
不同螢幕間移動或所有相機 EXIF 的人工驗收。Windows 11 原生與打包版本已有自動 GUI
端到端驗收；Windows 10 實機與 macOS 尚未驗收，Linux 由 CI 驗證原始碼測試。

## 2026-09-13 驗證結果

- Python 3.12.14、PySide6 6.11.2、pytest 9.1.1、ruff 0.16.7。
- 已在本專案 `.venv` 安裝 `.[dev]`；系統 `python` 為無法啟動的 WindowsApps
  alias，因此本機虛擬環境使用 Codex 隨附 Python 建立。
- Milestone 1 後端：23 項測試通過。
- v1.0 全套測試：59 項通過（約 1.7 秒；單次本機測量，不是效能基準）。
- `ruff check src tests scripts`：通過。
- `ruff format --check src tests scripts`：通過。
- `scripts/smoke_gui.py`：Windows 原生 Qt 視窗開啟示範 CBZ、切換第 2 頁、
  頁碼 `2 / 3` 通過；已檢視 `outputs/smoke/ArchiveLens-window.png`。
- CLI 對示範 CBZ 列出 `1.png`、`2.png`、`10.png`，順序正確。
- 測試確認來源 archive SHA-256 未變、沒有建立解壓圖片資料夾。
- EXIF 已測一個程式產生的 Orientation=6 JPEG；其他相機實檔仍待驗收。
- 原始碼與 frozen EXE 都通過八項端到端檢查：解碼器、拖放事件、排序、
  下一張／下一張／上一張與頁碼、100%／縮放／旋轉／Fit、全螢幕／Esc、
  WebP／末頁邊界、原始 archive SHA-256 不變與無圖片解壓。
- 可攜 ZIP 解壓至獨立目錄，移除 Python／Qt 環境變數及 Python PATH 後驗收通過。
- 打包曾誤收 PATH 中其他工具的 ICU DLL，與 Qt 使用的 Windows 系統 ICU ABI 不相容；
  spec 已排除，release verifier 亦拒絕含該 DLL 的套件。
- 套件每個檔案都有 manifest SHA-256，另記錄來源 commit、建置版本及編譯來源指紋。

## 發布門檻

1. 本機測試、Ruff、原生與可攜版 GUI 驗收通過。
2. 原始碼提交後，乾淨 checkout 重建；來源指紋不符就拒絕封裝。
3. GitHub 同一 commit 的 Windows／Linux 測試與 Windows portable job 通過。
4. 下載 CI 產物，驗證檔案 manifest、來源 commit、SHA-256 並再執行 packaged self-test。
5. `v1.0.0` tag 指向已驗證的 commit，再發布 portable ZIP、wheel、sdist、
   對應 Qt／PySide source archives、build-info 與 SHA256SUMS。

## 立即試用

1. 開發環境雙擊根目錄 `Start-ArchiveLens.cmd`；可攜版執行 `ArchiveLens.exe`。
2. 拖入自己的 ZIP／CBZ，或 `outputs/smoke/ArchiveLens-demo.cbz`。
3. 使用方向鍵切換圖片。完整操作及開發指令見根目錄 `README.md`。

可攜版保留 EXE 與 `_internal` 的相對位置；不需要使用者安裝 Python。
