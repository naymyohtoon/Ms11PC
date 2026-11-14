import os, sys, re, socket, configparser
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import vlc, uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MM_TO_EN = str.maketrans("၀၁၂၃၄၅၆၇၈၉", "0123456789")

W54_MAP = {
    'u': 'က', 'c': 'ခ', '*': 'ဂ', 'C': 'ဃ', 'i': 'င',
    'p': 'စ', 'q': 'ဆ', 'Z': 'ဇ', 'ps': 'ဈ', 'n': 'ည', 'N': 'ည', 'Ò': 'ဉ', 'ò': 'ဉ',
    '#': 'ဋ', 'X': 'ဌ', '!': 'ဍ', '¡': 'ဎ', 'P': 'ဏ', 'ó': 'ဏ',
    'w': 'တ', 'x': 'ထ', '’': 'ဒ', '“': 'ဓ', 'e': 'န', 'E': 'န', 'ø': 'န', '3': 'ဒ',
    'y': 'ပ', 'ù': 'ပ', 'z': 'ဖ', 'A': 'ဗ', 'b': 'ဘ', 'r': 'မ', 'ý': 'မ',
    ',': 'ယ', '&': 'ရ', 'v': 'လ', '0': 'ဝ', 'o': 'သ', 'ð': 'သ',
    '[': 'ဟ', 'V': 'ဠ', 't': 'အ', 'O': 'ဩ', 'o&': 'သြ', 'aMomf': 'ဪ',
    '£': 'ဣ', '%': 'ဣ', '¤': 'ဤ', '{': 'ဧ', '}': 'ၒ', 'OD;': 'ဦး', 'OD': 'ဦ',
    'ü': 'ဘ', 'ö': 'ဒ', 'ú': 'ဖ', 'û': 'ဗ', 'þ': 'ယ', 'ÿ': 'ရ',
    '"': 'ဒ', "'": 'ဒ', '|': 'ု', '<': '၎င်း', '>': '။', '?': '၊', 'í': '၌', 'ì': '၍',
    'm': 'ာ', 'g': 'ါ', 'd': 'ိ', 'D': 'ီ', 'k': 'ု', 'K': 'ူ', 'l': 'ူ', 'L': 'ြူ',
    'J': 'ဲ', 'H': 'ံ', 'h': '့', 'Y': '့', 'U': '့', 'f': '်', ';': 'း', ':': 'ာ်',
    '/': 'ျ', 's': 'ျ', 'j': 'ြ', 'B': 'ြ', 'M': 'ြ', '~': 'ြ', '\\': 'ြ',
    'S': 'ှ', 'T': 'ှ', '^': 'ှ', '`': 'ှ', '4': 'ှ', '7': 'ှ',
    'W': 'ွ', 'G': 'ွ', 'Q': 'ြွ', 'R': 'ျွ', '_': 'ွ', '2': 'ွ', '6': 'ွ',
    'uúm': 'က္ကာ', 'uú': 'က္က', 'c©': 'က္ခ', 'u©': 'က္ခ', '*¾': 'ဂ္ဂ', 'C¾': 'ဂ္ဃ',
    'pö': 'စ္စ', 'qä': 'စ္ဆ', 'ZÆ': 'ဇ္ဇ', 'ZÑ': 'ဇ္ဈ', 'n©': 'ဉ္စ', 'nÖ': 'ဉ္ဆ',
    '#Ö': 'ဋ္ဋ', '$': 'ဋ္ဌ', '@': 'ဍ္ဍ', '¡Ö': 'ဍ္ဎ', 'PÖ': 'ဏ္ဍ', 'PØ': 'ဏ္ဌ',
    'wå': 'တ္တ', 'Wå': 'တ္တ', 'å': '္တ', 'w¦': 'တ္ထ', 'x¦': 'တ္ထ',
    '’´': 'ဒ္ဒ', '“´': 'ဒ္ဓ', 'eÅ': 'န္တ', 'e¨': 'န္ထ', 'e´': 'န္ဒ',
    'yÜ': 'ပ္ပ', 'zÜ': 'ပ္ဖ', 'AÁ': 'ဗ္ဗ', 'bÁ': 'ဗ္ဘ',
    'rÜ': 'မ္ပ', 'rÁ': 'မ္ဗ', 'rÇ': 'မ္ဘ', 'r®': 'မ္မ',
    'vØ': 'လ္လ', 'ß': 'ဿ',
    '½': 'ွှ', '¾': 'ွှ', '¿': 'ြွ', 'À': 'ြွ', 'Á': 'ျွ', 'Â': 'ျွ',
    'Ã': 'ျှ', 'Ä': 'ျှ', 'Å': 'ြှ', 'Æ': 'ြှ', 'Ç': 'ှု', 'È': 'ှူ', 'É': 'ွှ',
    '=': 'ည', '+': 'ဏ', '-': 'ဗ'
}

def win_to_unicode(text):
    if not isinstance(text, str): return ""
    s = text.strip()
    if not s or s == "0": return ""

    pre = [
        ('o&', 'သြ'), ('OD;', 'ဦး'), ('OD', 'ဦ'), ('£', 'ဣ'), ('¤', 'ဤ'), ('aMomf', 'ဪ'),
        ('arwåm', 'မေတ္တာ'), ('wå', 'တ္တ'), ('Wå', 'တ္တ'), ('NyD', 'ပြီ'), ('MuD;', 'ကြီး'), ('MuD', 'ကြီ'),
        ('ES', 'နှ'), ('ET', 'နှ'), ('eS', 'နှ'), ('eT', 'နှ'),
        ('rS', 'မှ'), ('rT', 'မှ'), ('vS', 'လှ'), ('vT', 'လှ'),
        ('0S', 'ဝှ'), ('0T', 'ဝှ'), ('oS', 'သှ'), ('oT', 'သှ'),
        (',S', 'ယှ'), (',T', 'ယှ'), ('&S', 'ရှ'), ('&T', 'ရှ'),
        ('aY', 'ရွှေ'), ('a&T', 'ရွှေ'), ('a&S', 'ရွှေ'), ('a&$', 'ရွှေ')
    ]
    for old, new in pre:
        s = s.replace(old, new)

    cons = r'[uc*CipqZnN#X!¡Pwx’“eEyzAbr,&v0o\[Vt3]'
    s = re.sub(rf'({cons})F', r'င်္\1', s)
    s = re.sub(rf'a([jBMQL]?{cons})', r'\1ေ', s)
    s = re.sub(rf'([jBM])({cons})', r'\2ြ', s)
    s = re.sub(rf'Q({cons})', r'\1ြွ', s)
    s = re.sub(rf'L({cons})', r'\1ြူ', s)

    out, i = [], 0
    while i < len(s):
        if i + 3 <= len(s) and s[i:i+3] in W54_MAP:
            out.append(W54_MAP[s[i:i+3]]); i += 3
        elif i + 2 <= len(s) and s[i:i+2] in W54_MAP:
            out.append(W54_MAP[s[i:i+2]]); i += 2
        elif s[i] in W54_MAP:
            out.append(W54_MAP[s[i]]); i += 1
        else:
            out.append(s[i]); i += 1
    res = "".join(out)

    fixes = [
        ('ေြ', 'ြေ'), ('ေျ', 'ျေ'), ('ေွ', 'ွေ'), ('ေှ', 'ှေ'),
        ('ော', 'ော'), ('ေါ', 'ေါ'), ('ေါ်', 'ေါ်'), ('ေော်', 'ော်'),
        ('ုိ', 'ို'), ('ူိ', 'ို'), ('ံု', 'ုံ'), ('ံူ', 'ုံ'),
        ('့်', '့်'), ('့း', 'း'), ('့့', '့')
    ]
    for old, new in fixes:
        res = res.replace(old, new)
    return res

base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
config = configparser.ConfigParser()
config_path = os.path.join(base_dir, "config.txt")
if not os.path.exists(config_path): config_path = "config.txt"
config.read(config_path, encoding="utf-8")
EXCEL_PATH = config.get("PATHS", "EXCEL_PATH", fallback="J:/q2.xlsx").strip('"').strip("'")
VIDEO_ROOT = config.get("PATHS", "VIDEO_ROOT", fallback="J:/").strip('"').strip("'")

print(f"Scanning video files in {VIDEO_ROOT}...")
video_file_map = {}
video_cat_map = {}

def detect_category(folder_path):
    p = folder_path.lower()
    if "shann" in p or "shan" in p: return "SHAN"
    if "rakhine" in p: return "RAKHINE"
    if "kachin" in p: return "KACHIN"
    if "paoh" in p: return "PAOH"
    if "english" in p: return "ENGLISH"
    if "chinese" in p or "china" in p: return "CHINA"
    if "india" in p: return "INTERNATIONAL"
    if "disco" in p: return "DISCO"
    return "MYANMAR"

if os.path.exists(VIDEO_ROOT):
    for root, dirs, files in os.walk(VIDEO_ROOT):
        if "bkgvideo" in root.lower() or "discomp3" in root.lower():
            continue
        cat = detect_category(root)
        for f in files:
            if f.lower().endswith(('.mp4', '.mpg', '.mpeg', '.dat', '.mkv', '.avi', '.vob')):
                m = re.match(r"^[aA]?0*(\d+)\.", f)
                if m:
                    cid = m.group(1)
                    video_file_map[cid] = os.path.join(root, f)
                    video_cat_map[cid] = cat
print(f"Found {len(video_file_map)} video files on disk!")

songs_db, artists_set, albums_set = [], set(), set()
if os.path.exists(EXCEL_PATH):
    df_q = pd.read_excel(EXCEL_PATH, sheet_name="q", header=None)
    for idx, row in df_q.iterrows():
        raw_code = row.iloc if len(row) > 1 else None
        raw_title = row.iloc if len(row) > 2 else None
        raw_artist = row.iloc if len(row) > 4 else None
        raw_album = row.iloc if len(row) > 8 else (row.iloc if len(row) > 7 else None)
        if pd.notna(raw_code) and pd.notna(raw_title):
            try: code_str = str(int(float(raw_code)))
            except Exception: code_str = re.sub(r"[^0-9]", "", str(raw_code).translate(MM_TO_EN))
            title_uni = win_to_unicode(str(raw_title))
            artist_uni = win_to_unicode(str(raw_artist)) if pd.notna(raw_artist) else "အဆိုတော်အမည်မသိ"
            album_uni = win_to_unicode(str(raw_album)) if pd.notna(raw_album) else "တေးစီးရီးအမည်မသိ"
            if code_str and title_uni:
                cat_name = video_cat_map.get(code_str, "MYANMAR")
                songs_db.append({
                    "id": code_str,
                    "title": title_uni,
                    "artist": artist_uni,
                    "album": album_uni,
                    "category": cat_name,
                    "has_file": code_str in video_file_map
                })
                if cat_name == "MYANMAR":
                    if artist_uni != "အဆိုတော်အမည်မသိ": artists_set.add(artist_uni)
                    if album_uni != "တေးစီးရီးအမည်မသိ": albums_set.add(album_uni)

artists_db, albums_db = sorted(list(artists_set)), sorted(list(albums_set))
print(f"Loaded {len(songs_db)} songs, {len(artists_db)} artists, {len(albums_db)} albums!")

vlc_instance = vlc.Instance()
player = vlc_instance.media_player_new()
player.set_fullscreen(True)
queue_list, current_song, vocal_off, repeat_mode = [], None, False, False

def play_next_in_queue():
    global current_song
    if queue_list:
        current_song = queue_list.pop(0)
        fp = video_file_map.get(current_song["id"])
        if fp and os.path.exists(fp):
            player.set_media(vlc_instance.media_new(fp))
            player.play()
        else: play_next_in_queue()
    else:
        current_song = None
        player.stop()

@app.get("/status")
def get_status():
    if "Ended" in str(player.get_state()):
        if repeat_mode and current_song:
            fp = video_file_map.get(current_song["id"])
            if fp: player.set_media(vlc_instance.media_new(fp)); player.play()
        elif queue_list: play_next_in_queue()
    return {"is_playing": player.is_playing() == 1, "current_song": current_song, "time_ms": player.get_time(), "length_ms": player.get_length(), "volume": player.audio_get_volume(), "vocal_off": vocal_off, "repeat": repeat_mode, "queue_count": len(queue_list)}

@app.get("/search")
def search_songs(q: str = "", category: str = ""):
    pool = songs_db
    if category:
        c_up = category.upper()
        if c_up == "ETHNIC":
            pool = [s for s in songs_db if s["category"] in ("SHAN", "RAKHINE", "KACHIN", "PAOH")]
        else:
            pool = [s for s in songs_db if s["category"] == c_up]
    if not q:
        return pool[:5000]
    q_clean = q.strip().translate(MM_TO_EN).lower()
    return [s for s in pool if q_clean in s["title"].lower() or q_clean in s["artist"].lower() or q_clean in s["id"]][:2000]

@app.get("/browse/artists")
def get_artists(q: str = ""):
    if not q: return artists_db
    return [a for a in artists_db if q.lower() in a.lower()]

@app.get("/browse/albums")
def get_albums(q: str = ""):
    if not q: return albums_db
    return [a for a in albums_db if q.lower() in a.lower()]

@app.get("/browse/filter")
def filter_songs(artist: str = None, album: str = None):
    if artist: return [s for s in songs_db if s["artist"] == artist]
    if album: return [s for s in songs_db if s["album"] == album]
    return songs_db[:5000]

@app.get("/queue")
def get_queue(): return queue_list

@app.post("/queue/add/{song_id}")
def add_to_queue(song_id: str):
    clean_id = song_id.strip().translate(MM_TO_EN)
    song = next((s for s in songs_db if s["id"] == clean_id), None)
    if not song or song["id"] not in video_file_map:
        raise HTTPException(status_code=404, detail="Not found")
    queue_list.append(song)
    if player.is_playing() == 0 and current_song is None: play_next_in_queue()
    return {"status": "added", "queue": queue_list}

@app.post("/queue/priority/{index}")
def move_to_top(index: int):
    if 0 <= index < len(queue_list): queue_list.insert(0, queue_list.pop(index))
    return {"queue": queue_list}

@app.delete("/queue/remove/{index}")
def remove_from_queue(index: int):
    if 0 <= index < len(queue_list): queue_list.pop(index)
    return {"queue": queue_list}

@app.post("/control/{action}")
def control_player(action: str, value: int = 0):
    global vocal_off, repeat_mode
    if action == "play_pause": player.pause() if player.is_playing() else player.play()
    elif action == "stop": player.stop()
    elif action == "next": play_next_in_queue()
    elif action == "restart": player.set_time(0)
    elif action == "repeat": repeat_mode = not repeat_mode
    elif action == "rewind": player.set_time(max(0, player.get_time() - 10000))
    elif action == "forward": player.set_time(player.get_time() + 10000)
    elif action == "volume": player.audio_set_volume(max(0, min(100, value)))
    elif action == "vocal_toggle": vocal_off = not vocal_off; player.audio_set_channel(4 if vocal_off else 1)
    return {"status": "ok", "vocal_off": vocal_off, "repeat": repeat_mode}

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80))
        ip = s.getsockname(); s.close(); return ip
    except Exception: return "127.0.0.1"

if __name__ == "__main__":
    print("=" * 50); print(f"Phone App IP Address: {get_local_ip()}"); print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)

