import os
import subprocess
import json
import re
import urllib.request
import urllib.parse
import webbrowser
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
YT_DATA_FILE = DATA_DIR / "youtube_videos.json"

DEFAULT_CURATED_VIDEOS = [
    {
        "id": "JOhVvj_Zuzk",
        "url": "https://www.youtube.com/watch?v=JOhVvj_Zuzk",
        "title": "2 Broke Girls - Bloopers and Gag Reel Season 5",
        "channel": "Bloopers Network",
        "category": "Specials",
        "description": "Hilarious outtakes, flubbed lines, and behind-the-scenes moments from Season 5.",
        "thumbnail": "https://i.ytimg.com/vi/JOhVvj_Zuzk/hqdefault.jpg",
        "duration": "8:12",
        "added_at": 1729770000
    },
    {
        "id": "hm0lHv9HIYA",
        "url": "https://www.youtube.com/watch?v=hm0lHv9HIYA",
        "title": "'2 Broke Girls' and Their Pets! (Ellen Interview)",
        "channel": "TheEllenShow",
        "category": "Interviews",
        "description": "Kat Dennings and Beth Behrs discuss their real-life chemistry and pet stories.",
        "thumbnail": "https://i.ytimg.com/vi/hm0lHv9HIYA/hqdefault.jpg",
        "duration": "5:45",
        "added_at": 1729770100
    },
    {
        "id": "cvMV3jxtYBs",
        "url": "https://www.youtube.com/watch?v=cvMV3jxtYBs",
        "title": "Kat Dennings & Beth Behrs Play 'Heads Up!' on Ellen",
        "channel": "TheEllenShow",
        "category": "Interviews",
        "description": "The stars team up with Ellen in a high-energy, hilarious game of Heads Up!",
        "thumbnail": "https://i.ytimg.com/vi/cvMV3jxtYBs/hqdefault.jpg",
        "duration": "4:20",
        "added_at": 1729770200
    },
    {
        "id": "VxwZivhb-Rc",
        "url": "https://www.youtube.com/watch?v=VxwZivhb-Rc",
        "title": "2 Broke Girls - Bloopers and Gag Reel Season 4",
        "channel": "Bloopers Network",
        "category": "Specials",
        "description": "Classic diner mishaps, uncontrollable laughter, and unscripted moments.",
        "thumbnail": "https://i.ytimg.com/vi/VxwZivhb-Rc/hqdefault.jpg",
        "duration": "7:35",
        "added_at": 1729770300
    }
]

def find_system_browser() -> Optional[str]:
    candidates = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

class YouTubeManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_data_file()

    def _ensure_data_file(self):
        if not YT_DATA_FILE.exists():
            with open(YT_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CURATED_VIDEOS, f, indent=2)

    def extract_video_id(self, url: str) -> Optional[str]:
        if not url:
            return None
        patterns = [
            r'(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$'
        ]
        for pattern in patterns:
            match = re.search(pattern, url.strip())
            if match:
                return match.group(1)
        return None

    def get_all(self) -> List[Dict[str, Any]]:
        self._ensure_data_file()
        try:
            with open(YT_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_CURATED_VIDEOS

    def add_video(self, url: str, title: Optional[str] = None, category: Optional[str] = "Favorites", description: Optional[str] = None) -> Dict[str, Any]:
        video_id = self.extract_video_id(url)
        if not video_id:
            return {"success": False, "error": "Invalid YouTube URL or Video ID"}

        videos = self.get_all()
        for v in videos:
            if v["id"] == video_id:
                return {"success": False, "error": "Video is already in your Sanctuary"}

        clean_title = title.strip() if title and title.strip() else f"YouTube Video ({video_id})"
        clean_category = category.strip() if category and category.strip() else "Favorites"
        clean_desc = description.strip() if description and description.strip() else ""

        entry = {
            "id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": clean_title,
            "channel": "YouTube",
            "category": clean_category,
            "description": clean_desc,
            "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "duration": "HD Video",
            "added_at": int(os.path.getmtime(YT_DATA_FILE)) if YT_DATA_FILE.exists() else 0
        }

        videos.insert(0, entry)
        with open(YT_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(videos, f, indent=2)

        return {"success": True, "video": entry}

    def delete_video(self, video_id: str) -> bool:
        videos = self.get_all()
        orig_len = len(videos)
        videos = [v for v in videos if v["id"] != video_id]
        if len(videos) < orig_len:
            with open(YT_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(videos, f, indent=2)
            return True
        return False

    def open_feed(self, mode: str = "home", url: Optional[str] = None) -> Dict[str, Any]:
        if url and url.strip():
            target_url = url.strip()
            if not target_url.startswith("http://") and not target_url.startswith("https://"):
                vid_id = self.extract_video_id(target_url)
                if vid_id:
                    target_url = f"https://www.youtube.com/watch?v={vid_id}"
                else:
                    encoded = urllib.parse.quote_plus(target_url)
                    target_url = f"https://www.youtube.com/results?search_query={encoded}"
        else:
            if mode in ("signin", "login"):
                target_url = "https://www.youtube.com/signin"
            elif mode == "account":
                target_url = "https://www.youtube.com/account"
            elif mode == "switch":
                target_url = "https://accounts.google.com/AccountChooser?service=youtube"
            elif mode == "library":
                target_url = "https://www.youtube.com/feed/library"
            elif mode == "liked":
                target_url = "https://www.youtube.com/playlist?list=LL"
            elif mode == "subscriptions":
                target_url = "https://www.youtube.com/feed/subscriptions"
            elif mode == "history":
                target_url = "https://www.youtube.com/feed/history"
            elif mode == "tv":
                target_url = "https://www.youtube.com/tv"
            else:
                target_url = "https://www.youtube.com"

        print(f"[YOUTUBE] Opening feed in Brave: {target_url}")

        brave_exe = find_system_browser()
        if brave_exe and os.path.exists(brave_exe):
            try:
                # Launch Brave in standalone app mode with native Brave Shields
                DETACHED = 0x00000008 | 0x00000200
                cmd = [brave_exe, f"--app={target_url}"]
                subprocess.Popen(cmd, creationflags=DETACHED)
                print(f"[BRAVE] Successfully launched Brave app window: {cmd}")
                return {"success": True, "url": target_url, "mode": mode, "method": "brave_app"}
            except Exception as e:
                print(f"[BRAVE ERROR] Failed to launch in app mode: {e}")
                try:
                    subprocess.Popen([brave_exe, target_url])
                    return {"success": True, "url": target_url, "mode": mode, "method": "brave_browser"}
                except Exception as ex:
                    print(f"[BRAVE ERROR] Normal launch failed: {ex}")

        # 1. Fallback to default system browser via webbrowser module
        try:
            webbrowser.open(target_url)
            print("[YOUTUBE] Launched via webbrowser.open")
            return {"success": True, "url": target_url, "mode": mode, "method": "webbrowser"}
        except Exception as e:
            print(f"[YOUTUBE ERROR] webbrowser.open failed: {e}")

        # 2. Try os.startfile
        try:
            os.startfile(target_url)
            print("[YOUTUBE] Launched via os.startfile")
            return {"success": True, "url": target_url, "mode": mode, "method": "startfile"}
        except Exception as e:
            print(f"[YOUTUBE ERROR] os.startfile failed: {e}")

        return {"success": True, "url": target_url, "mode": mode, "method": "ready"}

youtube_manager = YouTubeManager()
