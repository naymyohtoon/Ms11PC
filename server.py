import os
import sys
import re
import socket
import configparser
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import vlc
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

config = configparser.ConfigParser()
config_path = os.path.join(base_dir, "config.txt")
if not os.path.exists(config_path):
    config_path = "config.txt"

config.read(config_path, encoding="utf-8")
EXCEL_PATH = config.get("PATHS", "EXCEL_PATH", fallback=r"J:\q2.xlsx").strip('"').strip("'")
VIDEO_FOLDER = config.get("PATHS", "VIDEO_FOLDER", fallback=r"J:\Myanmar_5").strip('"').strip("'")

MM_TO_EN_DIGITS = str.maketrans("၀၁၂၃၄၅၆၇၈၉", "0123456789")

def parse_song_entry(text):
    if pd.isna(text):
        return None, ""
    text = str(text).strip()
    match = re.match(r"^([၀-၉0-9]+)\s*(.*)$", text)
    if match:
        code_en = match.group(1).translate(MM_TO_EN_DIGITS)
        title = match.group(2).strip()
        return code_en, title
    return None, text

print("Reading Excel:", EXCEL_PATH)
songs_db = []
artists_db = []
albums_db = []

if os.path.exists(EXCEL_PATH):
    df_q = pd.read_excel(EXCEL_PATH, sheet_name="q", header=None)
    df_r = pd.read_excel(EXCEL_PATH, sheet_name="r", header=None)
    df_s = pd.read_excel(EXCEL_PATH, sheet_name="s", header=None)

    print("Sample rows from sheet q:")
    for i in range(min(3, len(df_q))):
        print(f"Row {i}: {list(df_q.iloc[i].dropna().values)}")

    for idx, row in df_q.iterrows():
        raw_song = row[1] if len(row) > 1 else None
        artist = str(row[4]).strip() if len(row) > 4 and pd.notna(row[4]) else "Unknown Artist"
        album = str(row[8]).strip() if len(row) > 8 and pd.notna(row[8]) else "Unknown Album"
        code, title = parse_song_entry(raw_song)
        if code and title:
            songs_db.append({
                "id": code,
                "filename": f"a{code}.mpg",
                "title": title,
                "artist": artist,
                "album": album
            })

    for idx, row in df_r.iterrows():
        if len(row) > 1 and pd.notna(row[1]):
            _, name = parse_song_entry(row[1])
            if name and name != "0":
                artists_db.append(name)

    for idx, row in df_s.iterrows():
        if len(row) > 1 and pd.notna(row[1]):
            _, name = parse_song_entry(row[1])
            if name and name != "0":
                albums_db.append(name)

    print(f"Loaded {len(songs_db)} songs, {len(artists_db)} artists, {len(albums_db)} albums!")
else:
    print("WARNING: Excel file not found! Please check config.txt")

vlc_instance = vlc.Instance()
player = vlc_instance.media_player_new()
player.set_fullscreen(True)

queue_list = []
current_song = None
vocal_off = False

def play_next_in_queue():
    global current_song
    if len(queue_list) > 0:
        current_song = queue_list.pop(0)
        file_path = os.path.join(VIDEO_FOLDER, current_song["filename"])
        if os.path.exists(file_path):
            media = vlc_instance.media_new(file_path)
            player.set_media(media)
            player.play()
        else:
            print(f"File not found: {file_path}")
            play_next_in_queue()
    else:
        current_song = None
        player.stop()

@app.get("/status")
def get_status():
    state = str(player.get_state())
    if "Ended" in state and len(queue_list) > 0:
        play_next_in_queue()
    return {
        "is_playing": player.is_playing() == 1,
        "current_song": current_song,
        "time_ms": player.get_time(),
        "length_ms": player.get_length(),
        "volume": player.audio_get_volume(),
        "vocal_off": vocal_off,
        "queue_count": len(queue_list)
    }

@app.get("/search")
def search_songs(q: str = ""):
    if not q:
        return songs_db[:50]
    q_lower = q.lower()
    results = [
        s for s in songs_db
        if q_lower in s["title"].lower() or q_lower in s["artist"].lower() or q_lower in s["id"]
    ]
    return results[:100]

@app.get("/browse/artists")
def get_artists():
    return artists_db

@app.get("/browse/albums")
def get_albums():
    return albums_db

@app.get("/browse/filter")
def filter_songs(artist: str = None, album: str = None):
    if artist:
        return [s for s in songs_db if artist in s["artist"]]
    if album:
        return [s for s in songs_db if album in s["album"]]
    return songs_db[:50]

@app.get("/queue")
def get_queue():
    return queue_list

@app.post("/queue/add/{song_id}")
def add_to_queue(song_id: str):
    song = next((s for s in songs_db if s["id"] == song_id), None)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    queue_list.append(song)
    if player.is_playing() == 0 and current_song is None:
        play_next_in_queue()
    return {"status": "added", "queue": queue_list}

@app.post("/queue/priority/{index}")
def move_to_top(index: int):
    if 0 <= index < len(queue_list):
        song = queue_list.pop(index)
        queue_list.insert(0, song)
    return {"queue": queue_list}

@app.delete("/queue/remove/{index}")
def remove_from_queue(index: int):
    if 0 <= index < len(queue_list):
        queue_list.pop(index)
    return {"queue": queue_list}

@app.post("/control/{action}")
def control_player(action: str, value: int = 0):
    global vocal_off
    if action == "play_pause":
        if player.is_playing():
            player.pause()
        else:
            player.play()
    elif action == "stop":
        player.stop()
    elif action == "next":
        play_next_in_queue()
    elif action == "restart":
        player.set_time(0)
    elif action == "volume":
        player.audio_set_volume(value)
    elif action == "seek":
        player.set_time(value)
    elif action == "vocal_toggle":
        vocal_off = not vocal_off
        if vocal_off:
            player.audio_set_channel(4)
        else:
            player.audio_set_channel(1)
    return {"status": "ok", "vocal_off": vocal_off}

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    print("=" * 50)
    print(f"Phone App IP Address: {get_local_ip()}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)

