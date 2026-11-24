import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
EPISODES_FILE = DATA_DIR / "episodes.json"
SERVER_LOG = BASE_DIR / "server.log"

# Safe stream fallbacks for pythonw / no-console execution
if sys.stdout is None or not hasattr(sys.stdout, "write"):
    try:
        sys.stdout = open(SERVER_LOG, "a", encoding="utf-8", buffering=1)
    except Exception:
        pass
if sys.stderr is None or not hasattr(sys.stderr, "write"):
    try:
        sys.stderr = open(SERVER_LOG, "a", encoding="utf-8", buffering=1)
    except Exception:
        pass

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from vlc_manager import vlc_manager
from youtube_manager import youtube_manager

app = FastAPI(title="2 Broke Girls Netflix Experience")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Native window holder for desktop fullscreen toggle
window_holder = {}

def set_main_window(window):
    window_holder["window"] = window

@app.post("/api/app/fullscreen")
def toggle_app_fullscreen():
    win = window_holder.get("window")
    if win:
        try:
            form = getattr(win, "native", None)
            if form:
                form.toggle_fullscreen()
                is_fs = getattr(form, "is_fullscreen", False)
            else:
                win.toggle_fullscreen()
                is_fs = True
            return {"handled": True, "is_fullscreen": is_fs}
        except Exception as e:
            return {"handled": True, "error": str(e), "is_fullscreen": False}
    return {"handled": False, "is_fullscreen": False}

@app.post("/api/app/fullscreen/set")
def set_app_fullscreen(enable: bool = True):
    win = window_holder.get("window")
    if win:
        try:
            form = getattr(win, "native", None)
            curr = getattr(form, "is_fullscreen", False) if form else False
            if bool(enable) != curr:
                if form:
                    form.toggle_fullscreen()
                    is_fs = getattr(form, "is_fullscreen", False)
                else:
                    win.toggle_fullscreen()
                    is_fs = bool(enable)
            else:
                is_fs = curr
            return {"handled": True, "is_fullscreen": is_fs}
        except Exception as e:
            return {"handled": True, "error": str(e), "is_fullscreen": False}
    return {"handled": False, "is_fullscreen": False}

@app.post("/api/app/focus")
def focus_app_window():
    try:
        import ctypes
        hwnd = ctypes.windll.user32.FindWindowW(None, "PlayerSlayer's Sanctuary")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return {"handled": True}
    except Exception:
        pass
    win = window_holder.get("window")
    if win:
        try:
            win.restore()
            win.focus()
            return {"handled": True}
        except Exception:
            pass
    return {"handled": False}

def format_time(seconds: int) -> str:
    if seconds <= 0:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def get_episodes_data() -> Dict[str, Any]:
    if not EPISODES_FILE.exists():
        raise HTTPException(status_code=500, detail="Episode catalog not generated yet.")
    with open(EPISODES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/catalog")
def get_catalog():
    data = get_episodes_data()
    all_progress = vlc_manager.get_all_progress()

    enriched_episodes = []
    continue_watching = []

    for ep in data["episodes"]:
        ep_copy = dict(ep)
        ep_id = ep["id"]
        prog = all_progress.get(ep_id, {})

        current_time = prog.get("current_time", 0)
        duration = prog.get("duration", ep.get("runtime_minutes", 22) * 60)
        pct = prog.get("progress_pct", 0)
        completed = prog.get("completed", False)
        updated_at = prog.get("updated_at", 0)

        # Dynamic video screenshot with cache key
        cache_ts = int(updated_at) if updated_at else 1
        ep_copy["thumbnail"] = f"/static/thumbnails/{ep_id}.jpg?v={cache_ts}"

        remaining_sec = max(0, duration - current_time)
        remaining_min = max(1, round(remaining_sec / 60))

        ep_copy["progress"] = {
            "current_time": current_time,
            "duration": duration,
            "progress_pct": pct,
            "completed": completed,
            "formatted_current_time": format_time(current_time),
            "formatted_duration": format_time(duration),
            "formatted_remaining": f"{remaining_min}m left",
            "updated_at": updated_at
        }
        enriched_episodes.append(ep_copy)

        # Build continue watching list: started, not finished (> 15s and < 90%)
        if current_time >= 15 and not completed and pct < 90:
            continue_watching.append(ep_copy)

    # Sort continue watching by most recently updated
    continue_watching.sort(key=lambda x: x["progress"]["updated_at"], reverse=True)

    # Determine "Next Up" recommendation
    next_up = None
    if continue_watching:
        next_up = continue_watching[0]
    else:
        # Find first unwatched episode
        for ep in enriched_episodes:
            if not ep["progress"]["completed"]:
                next_up = ep
                break
        if not next_up and enriched_episodes:
            next_up = enriched_episodes[0]

    return {
        "show": data["show"],
        "seasons": data["seasons"],
        "total_episodes": len(enriched_episodes),
        "episodes": enriched_episodes,
        "continue_watching": continue_watching,
        "next_up": next_up
    }

@app.get("/api/backdrops")
def get_backdrops():
    backdrops_dir = STATIC_DIR / "backdrops"
    if not backdrops_dir.exists():
        return {"backdrops": ["/static/assets/backdrop.jpg"]}
    files = sorted([f"/static/backdrops/{p.name}" for p in backdrops_dir.glob("*.jpg")])
    if not files:
        files = ["/static/assets/backdrop.jpg"]
    return {"backdrops": files, "total": len(files)}

class OpenYouTubeRequest(BaseModel):
    mode: Optional[str] = "home"
    url: Optional[str] = None

class AddYouTubeRequest(BaseModel):
    url: str
    title: Optional[str] = None
    category: Optional[str] = "Favorites"
    description: Optional[str] = None

class PlayYouTubeRequest(BaseModel):
    video_id: str

@app.get("/api/youtube")
def get_youtube_catalog():
    videos = youtube_manager.get_all()
    categories = list(dict.fromkeys([v.get("category", "Favorites") for v in videos]))
    return {
        "videos": videos,
        "total": len(videos),
        "categories": categories
    }

@app.post("/api/youtube/add")
def add_youtube_video(req: AddYouTubeRequest):
    res = youtube_manager.add_video(req.url, title=req.title, category=req.category, description=req.description)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to add video"))
    return res

@app.delete("/api/youtube/{video_id}")
def delete_youtube_video(video_id: str):
    success = youtube_manager.delete_video(video_id)
    if not success:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"success": True}

@app.post("/api/youtube/play-vlc")
def play_youtube_vlc(req: PlayYouTubeRequest):
    videos = youtube_manager.get_all()
    target_vid = next((v for v in videos if v["id"] == req.video_id), None)
    if not target_vid:
        target_vid = {"id": req.video_id, "title": "YouTube Video", "url": f"https://www.youtube.com/watch?v={req.video_id}"}
    res = vlc_manager.play_youtube(target_vid)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Failed to launch VLC"))
    return res

@app.post("/api/youtube/open-window")
def open_youtube_endpoint(req: OpenYouTubeRequest):
    target_url = req.url or "https://www.youtube.com"
    if req.mode in ("signin", "login"):
        target_url = "https://www.youtube.com/signin"
    elif req.mode == "account":
        target_url = "https://www.youtube.com/account"
    elif req.mode == "switch":
        target_url = "https://accounts.google.com/AccountChooser?service=youtube"
    elif req.mode == "subscriptions":
        target_url = "https://www.youtube.com/feed/subscriptions"
    elif req.mode == "history":
        target_url = "https://www.youtube.com/feed/history"
    elif req.mode == "library":
        target_url = "https://www.youtube.com/feed/library"
    elif req.mode == "tv":
        target_url = "https://www.youtube.com/tv"

    win = window_holder.get("window")
    if win:
        try:
            print(f"[SERVER] Navigating in-app Sanctuary window to: {target_url}")
            win.load_url(target_url)
            return {"handled": True, "success": True, "method": "in_app_window", "url": target_url}
        except Exception as e:
            print(f"[SERVER ERROR] win.load_url failed: {e}")

    return {"handled": True, "success": True, "url": target_url}

class PlayRequest(BaseModel):
    episode_id: str
    resume: bool = True

@app.post("/api/play")
def play_episode_vlc(req: PlayRequest):
    data = get_episodes_data()
    target_ep = next((e for e in data["episodes"] if e["id"] == req.episode_id), None)
    if not target_ep:
        raise HTTPException(status_code=404, detail="Episode not found.")

    res = vlc_manager.play_episode(target_ep, resume=req.resume)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Failed to launch VLC"))
    return res

@app.get("/api/vlc/status")
def get_vlc_status():
    return vlc_manager.get_status()

class ControlRequest(BaseModel):
    action: str
    value: Optional[Any] = None

@app.post("/api/vlc/control")
def control_vlc(req: ControlRequest):
    act = req.action.lower()
    if act in ("pause", "toggle", "play"):
        return vlc_manager.pause_toggle()
    elif act == "stop":
        return vlc_manager.stop()
    elif act == "seek":
        sec = int(req.value or 0)
        return vlc_manager.seek(sec)
    elif act == "fullscreen":
        return vlc_manager.toggle_fullscreen()
    return {"success": False, "error": f"Unknown action: {act}"}

class ProgressUpdateRequest(BaseModel):
    episode_id: str
    current_time: int
    duration: int
    completed: Optional[bool] = False

@app.post("/api/progress/update")
def update_progress(req: ProgressUpdateRequest):
    vlc_manager.save_progress(req.episode_id, req.current_time, req.duration, req.completed or False)
    return {"success": True}

class WatchedRequest(BaseModel):
    episode_id: str
    watched: bool

@app.post("/api/progress/mark")
def mark_watched(req: WatchedRequest):
    data = get_episodes_data()
    target_ep = next((e for e in data["episodes"] if e["id"] == req.episode_id), None)
    if not target_ep:
        raise HTTPException(status_code=404, detail="Episode not found.")
    
    duration = target_ep.get("runtime_minutes", 22) * 60
    if req.watched:
        vlc_manager.save_progress(req.episode_id, duration, duration, completed=True)
    else:
        vlc_manager.reset_progress(req.episode_id)
    return {"success": True}

@app.post("/api/progress/reset")
def reset_progress(req: WatchedRequest):
    vlc_manager.reset_progress(req.episode_id)
    return {"success": True}

# Subtitles WebVTT endpoint for in-browser player
@app.get("/api/subtitles/{episode_id}")
def get_subtitles(episode_id: str):
    data = get_episodes_data()
    target_ep = next((e for e in data["episodes"] if e["id"] == episode_id), None)
    if not target_ep or not target_ep.get("subtitle_path"):
        raise HTTPException(status_code=404, detail="No subtitles for this episode.")
    
    sub_path = Path(target_ep["subtitle_path"])
    if not sub_path.exists():
        raise HTTPException(status_code=404, detail="Subtitle file not found.")

    try:
        content = sub_path.read_text(encoding="utf-8", errors="replace")
        # Convert SRT to WebVTT
        vtt_lines = ["WEBVTT", ""]
        for line in content.splitlines():
            # Replace 00:00:20,000 --> 00:00:24,000 with 00:00:20.000 --> 00:00:24.000
            if "-->" in line:
                line = line.replace(",", ".")
            vtt_lines.append(line)
        vtt_content = "\n".join(vtt_lines)
        return Response(content=vtt_content, media_type="text/vtt")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Video Streaming Endpoint (supporting Range requests for HTML5 video player fallback)
@app.get("/api/stream/{episode_id}")
async def stream_video(episode_id: str, request: Request):
    data = get_episodes_data()
    target_ep = next((e for e in data["episodes"] if e["id"] == episode_id), None)
    if not target_ep:
        raise HTTPException(status_code=404, detail="Episode not found.")

    path = Path(target_ep["filepath"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk.")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        # e.g., bytes=0-1048575
        bytes_prefix = "bytes="
        if not range_header.startswith(bytes_prefix):
            raise HTTPException(status_code=400, detail="Invalid range header")

        range_str = range_header[len(bytes_prefix):]
        parts = range_str.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1

        if start >= file_size or end >= file_size:
            raise HTTPException(status_code=416, detail="Requested range not satisfiable")

        chunk_size = (end - start) + 1

        def iterfile():
            with open(path, "rb") as f:
                f.seek(start)
                bytes_left = chunk_size
                buffer_size = 1024 * 1024 # 1MB buffer
                while bytes_left > 0:
                    read_bytes = min(bytes_left, buffer_size)
                    data = f.read(read_bytes)
                    if not data:
                        break
                    bytes_left -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(iterfile(), status_code=status.HTTP_206_PARTIAL_CONTENT, headers=headers)

    # Full file response
    return FileResponse(path, media_type="video/mp4", filename=path.name)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    response = FileResponse(STATIC_DIR / "index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=7890, reload=False, access_log=False)
