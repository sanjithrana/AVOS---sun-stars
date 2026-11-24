---
name: avos-autoclip
description: How the Auto Clip tab works: turning a long video into captioned vertical shorts, connecting YouTube, and the Autopilot setting that posts and tracks them with no person involved.
---

# Auto Clip

Tab: **Auto Clip** in the desktop app. Backend: `animation_studio/studio/autoclip/` (API under `/api/autoclip`, reached as `/studio-api/autoclip`).

## Flow
1. **Get** the video: an upload, or a link (needs `yt-dlp`).
2. **Find the moments**: loudness per second, snapped to sentence edges when a transcript exists (an uploaded `.srt`, or `faster-whisper`).
3. **Cut** 9:16 clips (720p or 1080p; blurred fill, zoomed in or fill screen) with burned-in captions (Bounce, Hype, Clean, none).
4. **Post** to YouTube Shorts through the official Data API; **track** views, likes and, for Partner Programme channels, estimated earnings.

## Connect YouTube (once)
Create your own Google Cloud OAuth client (Web application), enable YouTube Data API v3 and YouTube Analytics API, add the redirect URI shown on the page, paste the client ID and secret, press Connect. Publish the consent screen ("In production") so the login does not expire. Tokens stay on the studio and are never sent to the page.

## Autopilot (Settings card, all OFF by default)
- Master switch, pause switch, "Fully automatic (no review)" (otherwise you approve each clip).
- Posts per day (1-20), minutes between posts (10+), posting hours, visibility (private by default), channel.
- Watch list: public channel IDs; new uploads (never the back catalogue) are downloaded and cut automatically.
- Required before ANY post: the box "I own this content or have permission to clip and post it".
- A dead login pauses autopilot and shows a notice. A clip that fails 3 times is left alone. A clip is marked "posting" before upload, so a crash cannot post twice.

## Limits
YouTube often refuses downloads from servers ("confirm you're not a bot"); Auto Clip does not work around that. Upload the file instead. Install the optional tools with `docker compose exec animation-studio pip install yt-dlp faster-whisper` (lost when the image is rebuilt). Upload quota is set by Google (100 calls a day at last check). Earnings need the YouTube Partner Programme.
