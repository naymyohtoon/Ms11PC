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

WIN_CONSONANTS = {
    'u': 'က', 'c': 'ခ', '*': 'ဂ', 'C': 'ဃ', 'i': 'င',
    'p': 'စ', 'q': 'ဆ', 'Z': 'ဇ', 'ps': 'ဈ', 'n': 'ဉ', 'N': 'ည',
    '#': 'ဋ', 'X': 'ဌ', '!': 'ဍ', '¡': 'ဎ', 'P': 'ဏ',
    'w': 'တ', 'x': 'ထ', '’': 'ဒ', '“': 'ဓ', 'e': 'န',
    'y': 'ပ', 'z': 'ဖ', 'A': 'ဗ', 'b': 'ဘ', 'r': 'မ',
    ',': 'ယ', '&': 'ရ', 'v': 'လ', '0': 'ဝ', 'o': 'သ',
    '[': 'ဟ', 'V': 'ဠ', 't': 'အ', 'O': 'ဩ', 'a': 'ေ', 'o&': 'သြ'
}

def win_to_unicode(text):
    if not isinstance(text, str):
        return ""
    s = text.strip()
    if not s or s == "0":
        return ""

    replacements = [
        ('o&', 'သြ'), ('ps', 'ဈ'), ('OD;', 'ဦး'), ('OD', 'ဦ'), ('£', 'ဣ'), ('¤', 'ဤ'),
        ('O', 'ဩ'), ('aMomf', 'ဪ'), ('/', 'ျ'), ('j', 'ျ'), ('G', 'ြ'), ('B', 'ြ'),
        ('M', 'ြ'), ('N', 'ြ'), ('S', 'ှ'), ('T', 'ှ'), ('W', 'ွ'), ('Q', 'ွ'),
        ('d', 'ိ'), ('D', 'ီ'), ('k', 'ု'), ('K', 'ူ'), ('l', 'ူ'), ('J', 'ဲ'),
        ('H', 'ံ'), ('h', '့'), ('f', '်'), (';', 'း'), ('m', 'ာ'), ('g', 'ါ'),
        (':', 'င်္'), ('F', '်'), ('½', 'ွှ'), ('¾', 'ွှ'), ('¿', 'ြွ'), ('À', 'ြွ'),
        ('Á', 'ျွ'), ('Â', 'ျွ'), ('Ã', 'ျှ'), ('Ä', 'ျှ'), ('Å', 'ြှ'), ('Æ', 'ြှ'),
        ('Ç', 'ှု'), ('È', 'ှူ'), ('É', 'ွှ'), ('Ê', '်'), ('Ë', 'ျ'), ('Ì', 'ြ'),
        ('Í', 'ွ'), ('Î', 'ှ'), ('Ï', 'ာ'), ('Ð', 'ါ'), ('Ñ', 'ီ'), ('Ò', 'ိ'),
        ('Ó', 'ု'), ('Ô', 'ူ'), ('Õ', 'ဲ'), ('Ö', 'ံ'), ('×', '့'), ('Ø', 'း'),
        ('Ù', '္'), ('Ú', '်'), ('Û', 'ျ'), ('Ü', 'ြ'), ('Ý', 'ွ'), ('Þ', 'ှ'),
        ('ß', 'ဿ'), ('à', 'ာ'), ('á', 'ါ'), ('â', 'ိ'), ('ã', 'ီ'), ('ä', 'ု'),
        ('å', 'ူ'), ('æ', 'ေ'), ('ç', 'ဲ'), ('è', 'ံ'), ('é', '့'), ('ê', 'း'),
        ('ë', '်'), ('ì', 'ျ'), ('í', 'ြ'), ('î', 'ွ'), ('ï', 'ှ'), ('ð', 'သ'),
        ('ñ', 'ည'), ('ò', 'ဉ'), ('ó', 'ဏ'), ('ô', 'တ'), ('õ', 'ထ'), ('ö', 'ဒ'),
        ('÷', 'ဓ'), ('ø', 'န'), ('ù', 'ပ'), ('ú', 'ဖ'), ('û', 'ဗ'), ('ü', 'ဘ'),
        ('ý', 'မ'), ('þ', 'ယ'), ('ÿ', 'ရ'), ('"', 'ဒ'), ("'", 'ဒ'), ('|', 'ရ'),
        ('~', 'ြ'), ('\\', 'ြ'), ('{', 'ဧ'), ('}', 'ၒ'), ('^', 'ှ'), ('_', 'ွ'),
        (chr(96), 'ှ'), ('$', 'ဋ္ဌ'), ('%', 'ဣ'), ('@', 'ဍ္ဍ'), ('<', '၎င်း'), ('>', '။'),
        ('?', '၊'), ('=', 'ည'), ('+', 'ဏ'), ('-', 'ဗ')
    ]

    s = re.sub(r'a([jBGMN]?[uc*CipqZnN#X!¡Pwx’“eyzAbr,&v0o\[Vt])', r'\1ေ', s)
    s = re.sub(r'([jBGMN])([uc*CipqZnN#X!¡Pwx’“eyzAbr,&v0o\[Vt])', r'\2ြ', s)

    out = []
    i = 0
    while i < len(s):
        if i + 1 < len(s) and s[i:i+2] in WIN_CONSONANTS:
            out.append(WIN_CONSONANTS[s[i:i+2]])
            i += 2
        elif s[i] in WIN_CONSONANTS:
            out.append(WIN_CONSONANTS[s[i]])
            i += 1
        else:
            out.append(s[i])
            i += 1
    res = "".join(out)

    for old, new in replacements:
        res = res.replace(old, new)

    return res

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

print("Reading Excel:", EXCEL_PATH)
songs_db = []
artists_db = []
albums_db = []

if os.path.exists(EXCEL_PATH):
    df_q = pd.read_excel(EXCEL_PATH, sheet_name="q", header=None)
    df_r = pd.read_excel(EXCEL_PATH, sheet_name="r", header=None)
    df_s = pd.read_excel(EXCEL_PATH, sheet_name="s", header=None)

    for idx, row in df_q.iterrows():
        raw_code = row.iloc[1] if len(row) > 1 else None
        raw_title = row.iloc[2] if len(row) > 2 else None
        raw_artist = row.iloc[4] if len(row) > 4 else None
        raw_album = row.iloc[8] if len(row) > 8 else (row.iloc[7] if len(row) > 7 else None)

        if pd.notna(raw_code) and pd.notna(raw_title):
            try:
                code_str = str(int(float(raw_code)))
            except Exception:
                code_str = re.sub(r"[^0-9]", "", str(raw_code))

            title_uni = win_to_unicode(str(raw_title))
            artist_uni = win_to_unicode(str(raw_artist)) if pd.notna(raw_artist) else "အဆိုတော်အမည်မသိ"
            album_uni = win_to_unicode(str(raw_album)) if pd.notna(raw_album) else "Album အမည်မသိ"

            if code_str and title_uni:
                songs_db.append({
                    "id": code_str,
                    "filename": f"a{code_str}.mpg",
                    "title": title_uni,
                    "artist": artist_uni,
                    "album": album_uni
                })

    for idx, row in df_r.iterrows():
        val = row.iloc[2] if (len(row) > 2 and pd.notna(row.iloc[2]) and not isinstance(row.iloc[2], (int, float))) else (row.iloc[1] if len(row) > 1 else None)
        if pd.notna(val):
            name_uni = win_to_unicode(str(val))
            if name_uni and not name_uni.isdigit():
                artists_db.append(name_uni)

    for idx, row in df_s.iterrows():
        val = row.iloc[2] if (len(row) > 2 and pd.notna(row.iloc[2]) and not isinstance(row.iloc[2], (int, float))) else (row.iloc[1] if len(row) > 1 else None)
        if pd.notna(val):
            name_uni = win_to_unicode(str(val))
            if name_uni and not name_uni.isdigit():
                albums_db.append(name_uni)

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
        ip = next(iter(s.getsockname()))
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    print("=" * 50)
    print(f"Phone App IP Address: {get_local_ip()}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
