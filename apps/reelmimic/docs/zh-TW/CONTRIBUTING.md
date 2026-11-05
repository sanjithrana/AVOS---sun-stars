<p align="right"><a href="../../CONTRIBUTING.md">English</a> · <b>繁體中文</b></p>

# 參與開發

感謝你想一起改進 ReelMimic！

## 開發環境
依 [README](../../README.zh-TW.md) 安裝後：

```bash
cd app
npm run server   # 後端（改 server/ 後：bash app/restart.sh）
npm run web      # 前端熱更新 http://localhost:5173
npm run doctor   # 環境檢查
```

架構說明在 [ARCHITECTURE.md](ARCHITECTURE.md)，擴充方式在 [EXTENDING.md](EXTENDING.md)。

## 最常見的貢獻
- **新風格**：`.claude/skills/video-clone/styles/<name>.md`，附一段你用來測試的參考片描述（不要附上受版權保護的影片檔）。
- **「已知的坑」**：做片時踩到的問題與解法，補進對應風格檔或引擎的 SKILL.md。
- **新製作引擎**：一個 agent skill 資料夾；第三方 skill 請附上來源與授權，並更新 `THIRD_PARTY_NOTICES.md`。
- **流程與指令**：改 `app/server/prompts.ts` 或 `jobs.ts` 時，請說明用哪支片驗證、`timeline.py` 的前後時間比較。

## 提交前
- 在 `app/` 裡 `npm run check`（型別檢查、lint、測試）和 `npm run build` 都要過；每個 PR 的 CI 會跑同樣的檢查。
- app 是 TypeScript（strict）。server 的 `.ts` 由 Node 內建的型別剝除直接執行，不需要建置；只能用可剝除的語法（不要用 `enum`、`namespace`、建構子參數屬性）。
- 不要提交 `projects/`、金鑰（`~/.reelmimic/secrets.json`）、參考影片或任何你沒有授權的素材。
- 程式碼註解與文件用繁體中文或英文皆可，保持和周圍一致。
