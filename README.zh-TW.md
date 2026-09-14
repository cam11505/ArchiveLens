# ArchiveLens 1.1 — 壓縮檔圖片與漫畫瀏覽器

本機、唯讀、無遙測。直接瀏覽 ZIP／CBZ、7Z、RAR／CBR 內圖片，不整包解壓到資料夾。

## 功能

- JPG／JPEG、PNG、WebP、BMP、靜態／動畫 GIF；EXIF 自動方向。
- ZipCrypto、AES ZIP（128／192／256）、加密 7Z、加密 RAR4／RAR5。
- 密碼遮蔽、顯示密碼、重試與取消；密碼僅存在目前工作階段記憶體。
- 自然排序、符合視窗、實體像素 100%、縮放、旋轉、拖移及全螢幕。
- 單頁／雙頁、第一頁封面、由左至右／由右至左閱讀。
- 延遲載入縮圖側欄，點擊縮圖跳頁；保留非敏感檢視偏好。
- Windows x64 可攜 ZIP 與每使用者安裝程式，內含 UnRAR 後端，不需另裝解壓工具。

## 開始使用

可攜版解開 ZIP 後執行 `ArchiveLens.exe`，保留旁邊的 `_internal`。
安裝版預設安裝在 `%LocalAppData%\Programs\ArchiveLens`，不需管理員權限。
建立開始功能表捷徑；桌面捷徑可選。不更改 ZIP／RAR／7Z 等預設關聯，透過「開啟方式」選用。

| 操作 | 功能 |
| --- | --- |
| Ctrl+O／拖入壓縮檔 | 開啟 |
| ←／→ | 依閱讀方向翻頁 |
| PageUp／Backspace；PageDown／Space | 邏輯上一頁／下一頁（雙頁時為上一組／下一組） |
| Home／End | 第一組／最後一組 |
| 0／1 | 符合完整跨頁／100% 實體像素 |
| +／-／Ctrl+滾輪 | 縮放 |
| R／Shift+R | 向右／向左旋轉 |
| F／F11／Esc | 全螢幕／退出 |
| T | 縮圖側欄 |

「檢視」與「閱讀」選單可設定雙頁、封面及閱讀方向。GIF 自動播放，離開頁面即停止。

## 限制

只支援單一檔案壓縮檔，不支援多卷、巢狀壓縮檔、修改／刪除內容或儲存密碼。
7Z 重複檔名不支援；RAR 連結項目略過。solid 壓縮檔不預讀鄰頁，翻頁可能較慢。
7Z 與部分舊式加密格式無法完全區分密碼錯誤和資料損壞。

最多 100,000 個項目、單筆解壓 128 MiB、圖片 4,000 萬像素；圖片快取 256 MiB、
縮圖快取 64 MiB、單一 GIF 32 MiB；7Z／RAR 解壓大小總計上限 1 GiB。
這些是個別元件限制，不代表程序總 RAM 上限，也不是惡意檔案沙箱。
密碼不寫入設定、命令列或日誌；Python 無法保證清除後端所有不可變記憶體副本。

原始碼執行與打包指令見 [English README](README.md)。開發及驗證狀態见
[DEVELOPMENT](docs/DEVELOPMENT.md)、[v1.1 QA](docs/V1.1_QA.md)。

## 授權

ArchiveLens 採 MIT；第三方元件保留各自授權。Qt 與部分解壓函式庫為 LGPL，
發布時附精確版本來源及授權。詳見 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)。
