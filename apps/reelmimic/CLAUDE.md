# ReelMimic — 參考影片風格克隆工作區

使用者給一支參考影片（檔案 / 螢幕錄影 / YouTube 連結）＋一句需求 → 產出同風格的新影片。

## 入口
- **一律先載入 `/video-clone`**（`.claude/skills/video-clone/SKILL.md`），照它的流程走：拆解 → 選風格 → 交給製作 skill → 分鏡 → 製作 → 逐格審查 → 輸出 → 依回饋修改。
- 風格對應表在 `.claude/skills/video-clone/styles/`，一種風格一個檔；新增風格就加一個檔（範本 `_TEMPLATE.md`）。

## 規則
- 媒材：目前只做 2D（3D 賽道暫停，blender-product-film 保留但不選用）。3D 參考片用 2D 重現並明講；不生成真人實拍影像或真實人物。
- 角色：使用者自己擁有的角色（提供設計圖）可直接用；或是我們根據此使用者所述自行去抓取的腳色可以直接使用；素材可以自己上網找（記來源與授權，不明的要標示）；歌詞只用使用者提供的文字或 LRC；參考片只學手法不抄素材；使用者自己的產品照片可以用來重建產品。
- 企劃逐鏡對照參考片（ref_shot + camera），完成後用 compare.py 並排比較、每鏡評分 ≥ 4 才交件。
- 每次渲染後抽影格用 Read 看，有問題修完再出片。

## 工具
- 需要的程式與安裝方式見 README（`npm run doctor` 會逐項檢查）：Node 22.18+、Python 3.10+（requirements.txt）、FFmpeg、Chrome、Claude Code 或 Codex CLI。
- 找不到 FFmpeg 時看環境變數 `FFMPEG_DIR`；Chrome 看 `CHROME_PATH`；Blender 看 `BLENDER`；API 金鑰在 `~/.reelmimic/secrets.json`（伺服器啟動時載入）。
- yt-dlp：`python -m yt_dlp`；截圖一律用 `.claude/skills/video-clone/scripts/hf_frames.py`（HyperFrames 專案）或引擎自己的 render 指令。

## 資料夾
- `app/` — ReelMimic 網站（server + React 前端）
- `projects/<代號>/` — 每支影片一個專案（`analysis/`、`plan.json`、`build/`、`out/video.mp4`）；不進版本控制
- `.claude/skills/` — skills：`video-clone` 是核心（流程、合約、風格表、工具），其他是製作引擎
- `docs/` — 架構與擴充說明
