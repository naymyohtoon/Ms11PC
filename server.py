from collections import deque
import os
import re
import threading
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import openpyxl
import uvicorn
import vlc

app = FastAPI(title="MI7 Karaoke Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DRIVE = "J:\\"
EXCEL_PATH = os.path.join(BASE_DRIVE, "q2.xlsx")
TARGET_FOLDERS = [
    "Myanmar_5",
    "Shann_5",
    "Rakhine_7",
    "Kachin 5",
    "Paoh_7",
    "English_5",
    "Chinese_5",
    "India_7",
    "DiscoVideo",
    "MI5_New_Song",
]
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".dat", ".vob", ".avi", ".mpg", ".mpeg")

MYANMAR_DIGITS = {
    "0": "၀", "1": "၁", "2": "၂", "3": "၃", "4": "၄",
    "5": "၅", "6": "၆", "7": "၇", "8": "၈", "9": "၉",
}


def normalize_code(raw_code) -> str:
    if raw_code is None:
        return ""
    s = str(raw_code).strip()
    rev_digits = {v: k for k, v in MYANMAR_DIGITS.items()}
    eng_s = "".join(rev_digits.get(ch, ch) for ch in s)
    if eng_s.endswith(".0"):
        eng_s = eng_s[:-2]
    return eng_s


songs_db: List[Dict] = []
video_index: Dict[str, str] = {}


def scan_videos():
    global video_index
    temp_index = {}
    print("Scanning video folders in J:\\ ...")
    for folder in TARGET_FOLDERS:
        folder_path = os.path.join(BASE_DRIVE, folder)
        if not os.path.exists(folder_path):
            continue
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(VIDEO_EXTENSIONS):
                    name_without_ext = os.path.splitext(file)[0].strip()
                    code_match = re.match(r"^(\d+)", name_without_ext)
                    full_path = os.path.join(root, file)
                    if code_match:
                        code_key = code_match.group(1)
                        temp_index[code_key] = full_path
                    temp_index[name_without_ext] = full_path
    video_index = temp_index
    print(f"Total indexed video files: {len(video_index)}")


def load_excel_db():
    global songs_db
    if not os.path.exists(EXCEL_PATH):
        print(f"Excel file not found: {EXCEL_PATH}")
        return

    print("Loading Unicode Excel database...")
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    ws = wb.active
    temp_songs = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or len(row) < 2:
            continue
        raw_code = row[0] if len(row) > 0 else None
        raw_title = row[1] if len(row) > 1 else None
        raw_artist = row[2] if len(row) > 2 else None
        raw_coartist = row[3] if len(row) > 3 else None
        raw_album = row[4] if len(row) > 4 else None

        code = normalize_code(raw_code)
        if not code or not raw_title:
            continue

        title = str(raw_title).strip()
        artist = str(raw_artist).strip() if raw_artist else "အမည်မသိ"
        coartist = str(raw_coartist).strip() if raw_coartist else ""
        if coartist:
            artist = f"{artist} + {coartist}"
        album = str(raw_album).strip() if raw_album else ""

        file_path = video_index.get(code, "")
        category = "MYANMAR"
        if file_path:
            upper_path = file_path.upper()
            if "CHINESE" in upper_path:
                category = "CHINA"
            elif "ENGLISH" in upper_path:
                category = "ENGLISH"
            elif any(x in upper_path for x in ["SHANN", "RAKHINE", "KACHIN", "PAOH"]):
                category = "ETHNIC"
            elif "INDIA" in upper_path:
                category = "INTERNATIONAL"
            elif "DISCO" in upper_path:
                category = "DISCO"

        temp_songs.append({
            "id": code,
            "code": code,
            "title": title,
            "artist": artist,
            "album": album,
            "category": category,
            "has_file": bool(file_path),
            "path": file_path,
        })

    wb.close()
    songs_db = temp_songs
    print(f"Loaded {len(songs_db)} songs from J:\\q2.xlsx.")

vlc_instance = vlc.Instance("--no-video-title-show", "--fullscreen")
player = vlc_instance.media_player_new()
player.set_fullscreen(True)

song_queue = deque()
current_song: Optional[Dict] = None
is_repeat = False
vocal_off = False


def play_media_file(song_item: Dict):
    global current_song, vocal_off
    path = song_item.get("path") or video_index.get(song_item["id"])
    if not path or not os.path.exists(path):
        print(f"Video file not found for code: {song_item['id']}")
        return False

    current_song = song_item
    media = vlc_instance.media_new(path)
    player.set_media(media)
    player.play()
    time.sleep(0.3)
    player.set_fullscreen(True)
    vocal_off = False
    return True


def queue_watcher():
    global current_song
    while True:
        time.sleep(1.0)
        state = player.get_state()
        if state == vlc.State.Ended:
            if is_repeat and current_song:
                play_media_file(current_song)
            elif len(song_queue) > 0:
                next_song = song_queue.popleft()
                play_media_file(next_song)
            else:
                current_song = None


threading.Thread(target=queue_watcher, daemon=True).start()


@app.on_event("startup")
def startup_event():
    scan_videos()
    load_excel_db()


@app.get("/status")
def get_status():
    return {
        "connected": True,
        "current_song": current_song,
        "queue_count": len(song_queue),
        "is_playing": player.is_playing() == 1,
        "repeat": is_repeat,
        "vocal_off": vocal_off,
        "volume": player.audio_get_volume(),
    }


@app.get("/search")
def search_songs(
    q: str = Query(""),
    category: str = Query("ALL"),
    limit: int = Query(100, ge=1, le=300),
):
    q_clean = q.strip().lower()
    results = []

    for s in songs_db:
        if category != "ALL" and s["category"] != category:
            continue
        if q_clean:
            if (
                q_clean not in s["id"].lower()
                and q_clean not in s["title"].lower()
                and q_clean not in s["artist"].lower()
                and q_clean not in s["album"].lower()
            ):
                continue
        results.append(s)
        if len(results) >= limit:
            break

    return results


@app.get("/browse/artists")
def browse_artists(q: str = Query("")):
    q_clean = q.strip().lower()
    seen = set()
    artists = []
    for s in songs_db:
        art = s["artist"]
        if not art or art == "အမည်မသိ" or art in seen:
            continue
        if q_clean and q_clean not in art.lower():
            continue
        seen.add(art)
        artists.append(art)
        if len(artists) >= 150:
            break
    return artists


@app.get("/browse/albums")
def browse_albums(q: str = Query("")):
    q_clean = q.strip().lower()
    seen = set()
    albums = []
    for s in songs_db:
        alb = s["album"]
        if not alb or alb in seen:
            continue
        if q_clean and q_clean not in alb.lower():
            continue
        seen.add(alb)
        albums.append(alb)
        if len(albums) >= 150:
            break
    return albums


@app.get("/browse/filter")
def browse_filter(artist: str = Query(""), album: str = Query("")):
    results = []
    for s in songs_db:
        if artist and s["artist"] == artist:
            results.append(s)
        elif album and s["album"] == album:
            results.append(s)
        if len(results) >= 200:
            break
    return results


@app.get("/queue")
def get_queue():
    return list(song_queue)


@app.post("/queue/add/{song_id}")
def add_to_queue(song_id: str):
    code = normalize_code(song_id)
    found = next((s for s in songs_db if s["id"] == code), None)
    if not found:
        path = video_index.get(code)
        if not path:
            raise HTTPException(status_code=404, detail="Video file not found")
        found = {
            "id": code,
            "code": code,
            "title": f"Song {code}",
            "artist": "",
            "album": "",
            "has_file": True,
            "path": path,
        }
    elif not found.get("has_file"):
        raise HTTPException(status_code=404, detail="Video file missing in drive")

    if not current_song and player.is_playing() == 0:
        play_media_file(found)
        return {"message": "Playing now", "queue_count": len(song_queue)}

    song_queue.append(found)
    return {"message": "Added to queue", "queue_count": len(song_queue)}


@app.post("/queue/priority/{index}")
def priority_queue(index: int):
    q_list = list(song_queue)
    if 0 <= index < len(q_list):
        item = q_list.pop(index)
        q_list.insert(0, item)
        song_queue.clear()
        song_queue.extend(q_list)
    return {"queue_count": len(song_queue)}


@app.delete("/queue/remove/{index}")
def remove_from_queue(index: int):
    q_list = list(song_queue)
    if 0 <= index < len(q_list):
        q_list.pop(index)
        song_queue.clear()
        song_queue.extend(q_list)
    return {"queue_count": len(song_queue)}


@app.post("/control/{action}")
def control_player(action: str, value: int = Query(0)):
    global is_repeat, vocal_off, current_song

    if action == "play_pause":
        player.pause()
    elif action == "stop":
        player.stop()
        current_song = None
    elif action == "repeat":
        is_repeat = not is_repeat
    elif action == "rewind":
        curr = player.get_time()
        player.set_time(max(0, curr - 10000))
    elif action == "forward":
        curr = player.get_time()
        player.set_time(curr + 10000)
    elif action == "restart":
        player.set_time(0)
    elif action == "next":
        if len(song_queue) > 0:
            next_song = song_queue.popleft()
            play_media_file(next_song)
        else:
            player.stop()
            current_song = None
    elif action == "vocal_toggle":
        tracks = player.audio_get_track_description()
        valid_tracks = [t[0] for t in tracks if t[0] != -1] if tracks else []
        if len(valid_tracks) >= 2:
            curr_track = player.audio_get_track()
            next_track = valid_tracks[1] if curr_track == valid_tracks[0] else valid_tracks[0]
            player.audio_set_track(next_track)
            vocal_off = next_track == valid_tracks[1]
        else:
            if not vocal_off:
                player.audio_set_channel(4)
                vocal_off = True
            else:
                player.audio_set_channel(1)
                vocal_off = False
    elif action == "volume":
        player.audio_set_volume(max(0, min(150, value)))

    return get_status()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

