# MatchLens Live v0.8 — Broadcast UX update

This is a drop-in replacement for your **existing frontend**. Backend remains unchanged.

Changes:
- Compact scoreboard, tighter hero and KPI cards to bring analysis above the fold.
- Every visible shot is clickable and keyboard-selectable. Opens the existing event evidence drawer showing player, timestamp, xG proxy, shot outcome, and event ID.
- New prominent rule-based intelligence spotlight, derived exclusively from the last available five-minute momentum window at the current playback timestamp. No AI or Foundry required.
- Source data remains synthetic; no hardcoded tactical claims.

## Install (PowerShell)

From `C:\Users\USER\matchlens-live`:

```powershell
Expand-Archive -Path "$env:USERPROFILE\Downloads\matchlens_broadcast_v08.zip" -DestinationPath "." -Force
cd frontend
npm install
npm run dev
```

Run FastAPI separately: `cd backend; uvicorn app.main:app --reload`.

This archive has a top-level `frontend/` folder and overwrites matching frontend files. Back up your current changes before extracting if you have edited them.
