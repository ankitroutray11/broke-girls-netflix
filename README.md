# 🎬 PlayerSlayer's Sanctuary

A prestige media sanctuary designed for **2 Broke Girls** (The Final Season - Season 6) and **The YouTube Sanctuary**, featuring **VLC hardware acceleration, automatic subtitles, resume tracking, and an uncluttered luxury streaming interface**.

---

## 🏛️ Architecture: Completely Separated Luxury Views

### 1. 🎬 2 Broke Girls Sanctuary
- **Cinematic Interface**: Obsidian and velvet theme with gold and crimson royal accents, hero billboard banner with next-up badge, season switcher tabs, episode cards, and comprehensive detail modals.
- **Final Season (Season 6)**: All 20 episodes sorted, tagged (`S6:E1-E2` through `S6:E22`), and organized with full metadata.
- **Episode Summaries & Details**: Complete title, airdate, runtime, and full synopsis for every single episode, accompanied by high-resolution preview stills.
- **VLC Codec Engine**:
  - Automatically launches **VLC Media Player** in fullscreen with hardware acceleration for x265/HEVC 1080p video and multi-channel audio.
  - Bidirectional communication via VLC's local HTTP API on port 8089.
- **Guaranteed Automatic Subtitles**:
  - Automatically detects, binds, and forces subtitles on via `--sub-file` and `--sub-track=0`.
  - All 20 episodes have verified English subtitles (`.srt`).
- **Smart Resume Capability**:
  - Progress is polled live from VLC and saved to `data/watch_progress.json`.
  - Progress bars appear across episode thumbnails and in the **"Continue Watching"** row.
  - One-click **Resume** automatically rewinds 3 seconds for viewing context.
  - Episodes are marked as completed when $\ge 92\%$ watched.
- **Dual Playback Modes**:
  - **VLC Native (Recommended)**: Full hardware decoding, audio passthrough, and native shortcuts.
  - **In-Browser Theater**: Web-based HTML5 player with range requests and auto-loaded WebVTT subtitles.

### 2. 🔴 The YouTube Sanctuary
- **Uncluttered Luxury Experience**: Minimalist design focused on pure aesthetics, speed, and comfort.
- **Instant Search & Stream**: Paste any YouTube link or enter a search query to immediately play inside the built-in Sanctuary Theater or stream in VLC.
- **Prestige Portals**:
  - **Personal Recommendations**: One-click portal to your personalized algorithm feed.
  - **Subscriptions Stream**: Chronological releases from channels you follow.
  - **Watch History & Queue**: Instantly resume saved and past videos.
  - **Big Screen TV Mode**: 10-foot smart-TV leanback experience for couch viewing.
- **Curated Sanctuary Featured Library**: Curated specials, cast interviews, and bloopers with 1-click playback.

---

## 🚀 How to Launch

### Option 1: Desktop Shortcut
Double-click **PlayerSlayer's Sanctuary** shortcut on your Desktop or run `Start-PlayerSlayers-Sanctuary.bat`.

### Option 2: Command Line
```powershell
python run_app.py
```
Server runs on `http://127.0.0.1:7890`.
