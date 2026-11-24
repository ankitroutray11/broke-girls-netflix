import os
import re
import json
import html
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
THUMBNAILS_DIR = STATIC_DIR / "thumbnails"
ASSETS_DIR = STATIC_DIR / "assets"

DOWNLOADS_DIR = Path.home() / "Downloads"
S6_DIR = DOWNLOADS_DIR / "2.Broke.Girls.S06.1080p.WEBRip.x265-RARBG"

EPISODES_FILE = DATA_DIR / "episodes.json"
PROGRESS_FILE = DATA_DIR / "watch_progress.json"

def clean_html(raw_html: str) -> str:
    if not raw_html:
        return "No summary available."
    clean = re.sub(r"<.*?>", "", raw_html)
    return html.unescape(clean).strip()

def download_file(url: str, dest: Path) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 1000:
            return True
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as e:
        print(f"Failed to download {url} -> {dest}: {e}")
        return False

def find_subtitles(video_file: Path) -> str:
    # 1. Check sidecar srt
    sidecar = video_file.with_suffix(".srt")
    if sidecar.exists():
        return str(sidecar)
    
    # 2. Check Subs subfolder
    subs_dir = video_file.parent / "Subs" / video_file.stem
    if subs_dir.exists():
        srts = list(subs_dir.glob("*.srt"))
        if srts:
            return str(srts[0])
            
    return ""

def scan_and_generate_metadata():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching 2 Broke Girls metadata from TVMaze...")
    tvmaze_url = "https://api.tvmaze.com/singlesearch/shows?q=2+broke+girls&embed=episodes"
    req = urllib.request.Request(tvmaze_url, headers={"User-Agent": "Mozilla/5.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        show_data = json.loads(resp.read().decode("utf-8"))

    show_info = {
        "app_name": "PlayerSlayer's Sanctuary",
        "title": "2 Broke Girls",
        "tagline": "PlayerSlayer's Sanctuary • Two girls. One diner. Huge dreams.",
        "description": clean_html(show_data.get("summary", "")),
        "genres": show_data.get("genres", ["Comedy"]),
        "rating": show_data.get("rating", {}).get("average", 7.0),
        "premiered": show_data.get("premiered", "2011-09-19"),
        "status": show_data.get("status", "Ended"),
        "network": show_data.get("network", {}).get("name", "CBS"),
        "backdrop": "/static/assets/backdrop.jpg",
        "poster": "/static/assets/poster.jpg",
        "logo_text": "PLAYERSLAYER'S SANCTUARY"
    }

    # Map TVMaze episodes by (season, episode)
    tvmaze_eps = {}
    for ep in show_data.get("_embedded", {}).get("episodes", []):
        tvmaze_eps[(ep.get("season"), ep.get("number"))] = ep

    # Scan video files (Final Season: Season 6)
    scanned_episodes = []

    for folder, season_num in [(S6_DIR, 6)]:
        if not folder.exists():
            print(f"Warning: Directory not found: {folder}")
            continue

        for file_path in sorted(folder.glob("*.mp4")):
            fname = file_path.name
            match = re.search(r"S(\d+)E(\d+)(?:E(\d+))?", fname, re.IGNORECASE)
            if not match:
                continue

            s_num = int(match.group(1))
            e_num1 = int(match.group(2))
            e_num2 = int(match.group(3)) if match.group(3) else None

            ep1_data = tvmaze_eps.get((s_num, e_num1), {})
            
            if e_num2:
                # Double episode
                ep2_data = tvmaze_eps.get((s_num, e_num2), {})
                title = f"{ep1_data.get('name', f'Episode {e_num1}')} & {ep2_data.get('name', f'Episode {e_num2}')}"
                ep_id = f"s{s_num:02d}e{e_num1:02d}e{e_num2:02d}"
                summary = clean_html(ep1_data.get("summary", "")) + " " + clean_html(ep2_data.get("summary", ""))
                runtime = (ep1_data.get("runtime") or 22) + (ep2_data.get("runtime") or 22)
                ep_label = f"S{s_num}:E{e_num1}-E{e_num2}"
                airdate = ep1_data.get("airdate", "")
            else:
                title = ep1_data.get("name", f"Episode {e_num1}")
                ep_id = f"s{s_num:02d}e{e_num1:02d}"
                summary = clean_html(ep1_data.get("summary", ""))
                runtime = ep1_data.get("runtime") or 22
                ep_label = f"S{s_num}:E{e_num1}"
                airdate = ep1_data.get("airdate", "")

            thumb_dest = THUMBNAILS_DIR / f"{ep_id}.jpg"
            thumb_path = f"/static/thumbnails/{ep_id}.jpg" if thumb_dest.exists() else "/static/assets/backdrop.jpg"
            file_size_mb = round(file_path.stat().st_size / (1024 * 1024), 1)

            # Locate subtitle
            sub_path = find_subtitles(file_path)

            scanned_episodes.append({
                "id": ep_id,
                "season": s_num,
                "episode": e_num1,
                "episode_end": e_num2,
                "episode_label": ep_label,
                "title": title,
                "summary": summary if summary else "No summary available for this episode.",
                "runtime": f"{runtime}m",
                "runtime_minutes": runtime,
                "airdate": airdate,
                "thumbnail": thumb_path,
                "filename": fname,
                "filepath": str(file_path),
                "filesize_mb": file_size_mb,
                "codec": "HEVC / x265",
                "resolution": "1080p FHD",
                "audio": "AAC 5.1 / Stereo",
                "has_subtitles": bool(sub_path),
                "subtitle_path": sub_path,
                "subtitle_name": Path(sub_path).name if sub_path else "None"
            })

    # Sort episodes by season, episode
    scanned_episodes.sort(key=lambda x: (x["season"], x["episode"]))

    output = {
        "app_name": "PlayerSlayer's Sanctuary",
        "show": show_info,
        "episodes": scanned_episodes,
        "total_episodes": len(scanned_episodes),
        "seasons": [6]
    }

    with open(EPISODES_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    sub_count = sum(1 for e in scanned_episodes if e["has_subtitles"])
    print(f"Updated metadata! Total episodes: {len(scanned_episodes)}, with subtitles: {sub_count}")
    return output

if __name__ == "__main__":
    scan_and_generate_metadata()
