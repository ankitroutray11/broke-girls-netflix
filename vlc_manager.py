import os
import subprocess
import threading
import time
import json
import base64
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROGRESS_FILE = DATA_DIR / "watch_progress.json"

DEFAULT_VLC_PATHS = [
    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
]

_last_snap_times = {}

def capture_episode_screenshot(episode_id: str, timestamp: int):
    try:
        import cv2
        episodes_file = Path(__file__).resolve().parent / "data" / "episodes.json"
        if not episodes_file.exists():
            return
        with open(episodes_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        ep = next((e for e in data.get("episodes", []) if e["id"] == episode_id), None)
        if not ep or not os.path.exists(ep.get("filepath", "")):
            return

        cap = cv2.VideoCapture(ep["filepath"])
        cap.set(cv2.CAP_PROP_POS_MSEC, max(1, int(timestamp)) * 1000)
        ret, frame = cap.read()
        if ret:
            thumb = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
            thumb_dir = Path(__file__).resolve().parent / "static" / "thumbnails"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            dest = thumb_dir / f"{episode_id}.jpg"
            dest_prog = thumb_dir / f"{episode_id}_progress.jpg"
            cv2.imwrite(str(dest), thumb, [cv2.IMWRITE_JPEG_QUALITY, 90])
            cv2.imwrite(str(dest_prog), thumb, [cv2.IMWRITE_JPEG_QUALITY, 90])
        cap.release()
    except Exception as e:
        print(f"[THUMB CAPTURE ERROR] {episode_id} at {timestamp}s: {e}")

class VLCManager:
    def __init__(self, port: int = 8089, password: str = "antigravity"):
        self.port = port
        self.password = password
        self.vlc_path = self._find_vlc()
        self.process: Optional[subprocess.Popen] = None
        self.current_episode: Optional[Dict[str, Any]] = None
        self.playback_state: Dict[str, Any] = {
            "status": "stopped",
            "time": 0,
            "length": 0,
            "position": 0.0,
            "volume": 256,
            "episode_id": None,
            "title": None,
            "is_active": False
        }
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()
        self._lock = threading.Lock()

    def _find_vlc(self) -> str:
        for p in DEFAULT_VLC_PATHS:
            if os.path.exists(p):
                return p
        import shutil
        which_vlc = shutil.which("vlc")
        if which_vlc:
            return which_vlc
        return r"C:\Program Files\VideoLAN\VLC\vlc.exe"

    def get_all_progress(self) -> Dict[str, Any]:
        with self._lock:
            if not PROGRESS_FILE.exists():
                return {}
            try:
                with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}

    def get_progress(self, episode_id: str) -> Optional[Dict[str, Any]]:
        all_prog = self.get_all_progress()
        return all_prog.get(episode_id)

    def save_progress(self, episode_id: str, current_time: int, duration: int, completed: bool = False):
        if not episode_id:
            return
        with self._lock:
            all_prog = {}
            if PROGRESS_FILE.exists():
                try:
                    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                        all_prog = json.load(f)
                except Exception:
                    all_prog = {}

            pct = round((current_time / duration) * 100, 1) if duration > 0 else 0
            if pct >= 92:
                completed = True

            all_prog[episode_id] = {
                "current_time": int(current_time),
                "duration": int(duration),
                "progress_pct": pct,
                "completed": completed,
                "updated_at": time.time()
            }

            try:
                PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_prog, f, indent=2)
            except Exception as e:
                print(f"Error saving progress for {episode_id}: {e}")

        # Update thumbnail with real video screenshot at playback position
        if episode_id.startswith("s") and current_time >= 10:
            last_time = _last_snap_times.get(episode_id, 0)
            if abs(current_time - last_time) >= 10 or completed:
                _last_snap_times[episode_id] = current_time
                threading.Thread(target=capture_episode_screenshot, args=(episode_id, current_time), daemon=True).start()

    def reset_progress(self, episode_id: str):
        with self._lock:
            if not PROGRESS_FILE.exists():
                return
            try:
                with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                    all_prog = json.load(f)
                if episode_id in all_prog:
                    del all_prog[episode_id]
                    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                        json.dump(all_prog, f, indent=2)
            except Exception as e:
                print(f"Error resetting progress: {e}")

    def play_episode(self, episode_data: Dict[str, Any], resume: bool = True) -> Dict[str, Any]:
        episode_id = episode_data["id"]
        filepath = episode_data["filepath"]

        if not os.path.exists(filepath):
            return {"success": False, "error": f"File does not exist: {filepath}"}

        # Calculate start time
        start_time = 0
        if resume:
            prog = self.get_progress(episode_id)
            if prog and not prog.get("completed", False):
                # Don't resume if in the first 10 seconds or completed
                start_time = max(0, prog.get("current_time", 0) - 3) # Rewind 3 seconds for context

        # Stop existing instance if any
        self.stop()

        cmd = [
            self.vlc_path,
            filepath,
            f"--start-time={int(start_time)}",
            "--extraintf=http",
            f"--http-password={self.password}",
            f"--http-port={self.port}",
            "--no-video-title-show",
            "--fullscreen"
        ]

        # Automatic Subtitle Integration
        sub_path = episode_data.get("subtitle_path")
        if sub_path and os.path.exists(sub_path):
            cmd.append(f"--sub-file={sub_path}")
            cmd.append("--sub-track=0")
            print(f"Attached subtitle to VLC: {sub_path}")

        print(f"Launching VLC: {filepath} at {start_time}s")
        try:
            self.process = subprocess.Popen(cmd)
            self.current_episode = episode_data
            self.playback_state = {
                "status": "playing",
                "time": start_time,
                "length": episode_data.get("runtime_minutes", 22) * 60,
                "position": 0.0,
                "volume": 256,
                "episode_id": episode_id,
                "title": episode_data.get("title", ""),
                "is_active": True
            }

            # Start monitoring thread
            self._stop_monitor.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_playback, daemon=True)
            self._monitor_thread.start()

            return {
                "success": True,
                "resumed_from": start_time,
                "episode_id": episode_id,
                "title": episode_data.get("title", "")
            }
        except Exception as e:
            print(f"Failed to launch VLC: {e}")
            return {"success": False, "error": str(e)}

    def play_youtube(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        url = video_data.get("url") or f"https://www.youtube.com/watch?v={video_data['id']}"
        title = video_data.get("title", "YouTube Video")

        self.stop()

        cmd = [
            self.vlc_path,
            url,
            "--extraintf=http",
            f"--http-password={self.password}",
            f"--http-port={self.port}",
            "--no-video-title-show",
            "--fullscreen"
        ]

        print(f"Launching VLC for YouTube stream: {url}")
        try:
            self.process = subprocess.Popen(cmd)
            self.current_episode = video_data
            self.playback_state = {
                "status": "playing",
                "time": 0,
                "length": 0,
                "position": 0.0,
                "volume": 256,
                "episode_id": f"yt_{video_data['id']}",
                "title": title,
                "is_active": True
            }

            self._stop_monitor.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_playback, daemon=True)
            self._monitor_thread.start()

            return {
                "success": True,
                "title": title,
                "url": url
            }
        except Exception as e:
            print(f"Failed to launch VLC for YouTube: {e}")
            return {"success": False, "error": str(e)}

    def _send_vlc_command(self, query: str) -> Optional[Dict[str, Any]]:
        auth = base64.b64encode(f":{self.password}".encode("utf-8")).decode("ascii")
        url = f"http://127.0.0.1:{self.port}/requests/status.json?{query}"
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def _monitor_playback(self):
        ep_id = self.current_episode["id"] if self.current_episode else None
        last_save_time = 0

        # Wait initial 2 seconds for VLC HTTP server to start
        time.sleep(2)

        while not self._stop_monitor.is_set():
            if self.process and self.process.poll() is not None:
                # VLC process has exited
                print(f"VLC process ended for episode {ep_id}")
                break

            status = self._send_vlc_command("")
            if status:
                current_time = status.get("time", 0)
                length = status.get("length", 0)
                state = status.get("state", "stopped")
                pos = status.get("position", 0.0)
                vol = status.get("volume", 256)

                self.playback_state.update({
                    "status": state,
                    "time": current_time,
                    "length": length,
                    "position": pos,
                    "volume": vol,
                    "is_active": True
                })

                # Save progress periodically every 3 seconds or on state change
                now = time.time()
                if current_time > 0 and length > 0 and (now - last_save_time >= 3):
                    self.save_progress(ep_id, current_time, length)
                    last_save_time = now

                if state == "stopped" and current_time == 0 and length > 0 and pos >= 0.95:
                    # Episode completed
                    self.save_progress(ep_id, length, length, completed=True)
                    break
            else:
                # HTTP not responding or VLC stopped
                if self.process and self.process.poll() is not None:
                    break

            time.sleep(1.5)

        # Final progress save
        if ep_id and self.playback_state["time"] > 0 and self.playback_state["length"] > 0:
            self.save_progress(ep_id, self.playback_state["time"], self.playback_state["length"])

        self.playback_state["is_active"] = False
        self.playback_state["status"] = "stopped"
        self.current_episode = None

    def pause_toggle(self) -> Dict[str, Any]:
        res = self._send_vlc_command("command=pl_pause")
        return {"success": res is not None}

    def toggle_fullscreen(self) -> Dict[str, Any]:
        res = self._send_vlc_command("command=fullscreen")
        return {"success": res is not None}

    def seek(self, seconds: int) -> Dict[str, Any]:
        res = self._send_vlc_command(f"command=seek&val={seconds}")
        return {"success": res is not None}

    def stop(self) -> Dict[str, Any]:
        self._stop_monitor.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1)

        # Try sending stop command
        try:
            self._send_vlc_command("command=pl_stop")
        except Exception:
            pass

        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

        self.process = None
        self.playback_state["is_active"] = False
        self.playback_state["status"] = "stopped"
        return {"success": True}

    def get_status(self) -> Dict[str, Any]:
        return dict(self.playback_state)

vlc_manager = VLCManager()
