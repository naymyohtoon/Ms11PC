from collections import deque
import os
import re
import socket
import sys
import threading
import time
import tkinter as tk
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import openpyxl
from PIL import Image, ImageTk
import uvicorn
import vlc


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


app = FastAPI(title="MI7 Karaoke Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DRIVE = "J:\\"
MYANMAR_EXCEL = os.path.join(BASE_DRIVE, "q2.xlsx")
DISCO_EXCEL = os.path.join(BASE_DRIVE, "disco.xlsx")

MYANMAR_FOLDERS = ["Myanmar_5", "MI5_New_Song"]
DISCO_FOLDERS = ["DiscoVideo"]
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".dat", ".vob", ".avi", ".mpg", ".mpeg")

MYANMAR_DIGITS = {
    "0": "၀", "1": "၁", "2": "၂", "3": "၃", "4": "၄",
    "5": "၅", "6": "၆", "7": "၇", "8": "၈", "9": "၉",
}


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname)[2]:
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    return ip
        except Exception:
            pass
    return "127.0.0.1"


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
myanmar_video_index: Dict[str, str] = {}
disco_video_index: Dict[str, str] = {}
def scan_videos():
    global myanmar_video_index, disco_video_index
    m_index = {}
    d_index = {}

    for folder in MYANMAR_FOLDERS:
        folder_path = os.path.join(BASE_DRIVE, folder)
        if not os.path.exists(folder_path):
            continue
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(VIDEO_EXTENSIONS):
                    name_no_ext = os.path.splitext(file)[0].strip()
                    full_path = os.path.join(root, file)
                    match = re.search(r"(\d+)", name_no_ext)
                    if match:
                        m_index[match.group(1)] = full_path
                    m_index[name_no_ext] = full_path

    for folder in DISCO_FOLDERS:
        folder_path = os.path.join(BASE_DRIVE, folder)
        if not os.path.exists(folder_path):
            continue
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(VIDEO_EXTENSIONS):
                    name_no_ext = os.path.splitext(file)[0].strip()
                    full_path = os.path.join(root, file)
                    match = re.search(r"(\d+)", name_no_ext)
                    if match:
                        d_index[match.group(1)] = full_path
                    d_index[name_no_ext] = full_path

    myanmar_video_index = m_index
    disco_video_index = d_index


def load_databases():
    global songs_db
    temp_songs = []

    if os.path.exists(MYANMAR_EXCEL):
        wb = openpyxl.load_workbook(MYANMAR_EXCEL, read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 2:
                continue
            code = normalize_code(row[0])
            raw_title = row[1]
            if not code or not raw_title:
                continue

            title = str(raw_title).strip()
            artist = str(row[2]).strip() if len(row) > 2 and row[2] else "အမည်မသိ"
            coartist = str(row[3]).strip() if len(row) > 3 and row[3] else ""
            if coartist:
                artist = f"{artist} + {coartist}"
            album = str(row[4]).strip() if len(row) > 4 and row[4] else ""

            file_path = myanmar_video_index.get(code, "")
            temp_songs.append({
                "id": code,
                "code": code,
                "title": title,
                "artist": artist,
                "album": album,
                "category": "MYANMAR",
                "has_file": bool(file_path),
                "path": file_path,
            })
        wb.close()

    if os.path.exists(DISCO_EXCEL):
        wb = openpyxl.load_workbook(DISCO_EXCEL, read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 2:
                continue
            code = normalize_code(row[0])
            raw_title = row[1]
            if not code or not raw_title:
                continue

            file_path = disco_video_index.get(code, "")
            temp_songs.append({
                "id": f"D{code}",
                "code": code,
                "title": str(raw_title).strip(),
                "artist": "",
                "album": "",
                "category": "DISCO",
                "has_file": bool(file_path),
                "path": file_path,
            })
        wb.close()
    else:
        sorted_keys = sorted([k for k in disco_video_index.keys() if k.isdigit()], key=lambda x: int(x))
        for code in sorted_keys:
            temp_songs.append({
                "id": f"D{code}",
                "code": code,
                "title": f"Disco Nonstop {code}",
                "artist": "",
                "album": "",
                "category": "DISCO",
                "has_file": True,
                "path": disco_video_index[code],
            })

    songs_db = temp_songs


vlc_instance = vlc.Instance("--no-video-title-show", "--fullscreen")
player = vlc_instance.media_player_new()
player.set_fullscreen(True)

song_queue = deque()
current_song: Optional[Dict] = None
is_repeat = False
vocal_off = False


def play_media_file(song_item: Dict):
    global current_song, vocal_off
    path = song_item.get("path")
    if not path or not os.path.exists(path):
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
@app.get("/status")
def get_status():
    return {
        "connected": True,
        "server_ip": get_local_ip(),
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
    category: str = Query("MYANMAR"),
    limit: int = Query(150, ge=1, le=500),
):
    q_clean = q.strip().lower()
    results = []
    for s in songs_db:
        if s["category"] != category:
            continue
        if q_clean:
            if (
                q_clean not in s["code"].lower()
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
        if s["category"] != "MYANMAR":
            continue
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
        if s["category"] != "MYANMAR":
            continue
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
        if s["category"] != "MYANMAR":
            continue
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
    if song_id.startswith("D"):
        code = normalize_code(song_id[1:])
        found = next((s for s in songs_db if s["category"] == "DISCO" and s["code"] == code), None)
        if not found and code in disco_video_index:
            found = {
                "id": f"D{code}",
                "code": code,
                "title": f"Disco Nonstop {code}",
                "artist": "",
                "album": "",
                "has_file": True,
                "path": disco_video_index[code],
            }
    else:
        code = normalize_code(song_id)
        found = next((s for s in songs_db if s["category"] == "MYANMAR" and s["code"] == code), None)
        if not found and code in myanmar_video_index:
            found = {
                "id": code,
                "code": code,
                "title": f"Myanmar Song {code}",
                "artist": "",
                "album": "",
                "has_file": True,
                "path": myanmar_video_index[code],
            }

    if not found or not found.get("has_file"):
        raise HTTPException(status_code=404, detail="Video file not found")

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
        valid_tracks = [t for t in tracks if t != -1] if tracks else []
        if len(valid_tracks) >= 2:
            curr_track = player.audio_get_track()
            next_track = valid_tracks if curr_track == valid_tracks else valid_tracks
            player.audio_set_track(next_track)
            vocal_off = next_track == valid_tracks
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
class MI7DesktopUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Microstack V7.1.5 - MI7 Karaoke System")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="#1E2226")
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))

        self.current_cat = "MYANMAR"
        self.displayed_songs = []
        self.build_ui()
        self.refresh_loop()

    def build_ui(self):
        # Top Bar (Logo တစ်ဝက်ကျယ် + Now Playing + App IP Address)
        top_frame = tk.Frame(self.root, bg="#121518", height=75)
        top_frame.pack(fill=tk.X, padx=10, pady=8)
        top_frame.pack_propagate(False)

        try:
            logo_path = resource_path("image_afebac29.jpg")
            img = Image.open(logo_path).resize((420, 62), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(img)
            tk.Label(top_frame, image=self.logo_photo, bg="#121518").pack(side=tk.LEFT, padx=8)
        except Exception:
            tk.Label(
                top_frame, text="MICROSTACK V7.1.5 (MI7)", font=("Pyidaungsu", 18, "bold"),
                fg="#00E5FF", bg="#121518"
            ).pack(side=tk.LEFT, padx=15)

        self.lbl_playing = tk.Label(
            top_frame, text="သီချင်း မဖွင့်ရသေးပါ (Ready)", font=("Pyidaungsu", 13, "bold"),
            fg="#64FFDA", bg="#263238", anchor="w", padx=12
        )
        self.lbl_playing.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        ip_text = f"App IP Address: {get_local_ip()}"
        self.lbl_ip = tk.Label(
            top_frame, text=ip_text, font=("Consolas", 13, "bold"),
            fg="#FFFFFF", bg="#00695C", padx=14, pady=8
        )
        self.lbl_ip.pack(side=tk.RIGHT, padx=10)

        # Main Body
        body_frame = tk.Frame(self.root, bg="#1E2226")
        body_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # ဘယ်ဘက်ခြမ်း: ရွေးထားသောသီချင်းများ (Queue)
        left_frame = tk.Frame(body_frame, bg="#262B30", width=380, bd=1, relief=tk.SOLID)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)

        tk.Label(
            left_frame, text="ရွေးထားသောသီချင်းများ (Queue)", font=("Pyidaungsu", 13, "bold"),
            fg="#FFD740", bg="#004D40", pady=8
        ).pack(fill=tk.X)

        self.queue_listbox = tk.Listbox(
            left_frame, bg="#262B30", fg="#FFFFFF", font=("Pyidaungsu", 12),
            selectbackground="#00796B", borderwidth=0, highlightthickness=0
        )
        self.queue_listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ညာဘက်ခြမ်း: ရှာဖွေရေးနှင့် သီချင်းစာရင်း
        right_frame = tk.Frame(body_frame, bg="#262B30", bd=1, relief=tk.SOLID)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        filter_bar = tk.Frame(right_frame, bg="#1B2024", pady=8)
        filter_bar.pack(fill=tk.X)

        tk.Button(
            filter_bar, text="မြန်မာသီချင်းများ", font=("Pyidaungsu", 12, "bold"),
            bg="#00897B", fg="white", padx=14, pady=4,
            command=lambda: self.switch_cat("MYANMAR")
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            filter_bar, text="Disco Song", font=("Pyidaungsu", 12, "bold"),
            bg="#5E35B1", fg="white", padx=14, pady=4,
            command=lambda: self.switch_cat("DISCO")
        ).pack(side=tk.LEFT, padx=4)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.update_song_list())
        search_entry = tk.Entry(
            filter_bar, textvariable=self.search_var, font=("Pyidaungsu", 13),
            bg="#37474F", fg="white", insertbackground="white", width=28
        )
        search_entry.pack(side=tk.RIGHT, padx=12)
        tk.Label(filter_bar, text="ရှာရန်:", font=("Pyidaungsu", 12), fg="#B0BEC5", bg="#1B2024").pack(side=tk.RIGHT)

        self.song_listbox = tk.Listbox(
            right_frame, bg="#262B30", fg="#ECEFF1", font=("Pyidaungsu", 12),
            selectbackground="#00695C", borderwidth=0, highlightthickness=0
        )
        self.song_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.song_listbox.bind("<Double-Button-1>", self.on_song_double_click)

        # Bottom Control Bar
        bottom_bar = tk.Frame(self.root, bg="#121518", height=52)
        bottom_bar.pack(fill=tk.X, padx=10, pady=(4, 8))

        controls = [
            ("Play/Pause", lambda: control_player("play_pause")),
            ("Stop", lambda: control_player("stop")),
            ("Re-Start", lambda: control_player("restart")),
            ("Next", lambda: control_player("next")),
            ("Vocal/Music", lambda: control_player("vocal_toggle")),
        ]
        for text, cmd in controls:
            tk.Button(
                bottom_bar, text=text, font=("Pyidaungsu", 11, "bold"),
                bg="#37474F", fg="white", padx=14, pady=6, command=cmd
            ).pack(side=tk.LEFT, padx=8, pady=6)

        tk.Label(
            bottom_bar, text="Double-click နှိပ်၍ သီချင်းရွေးနိုင်ပါသည် | ESC နှိပ်၍ Fullscreen ပိတ်နိုင်သည်",
            font=("Pyidaungsu", 10), fg="#90A4AE", bg="#121518"
        ).pack(side=tk.RIGHT, padx=12)

    def switch_cat(self, cat: str):
        self.current_cat = cat
        self.update_song_list()

    def update_song_list(self):
        q = self.search_var.get().strip().lower()
        self.song_listbox.delete(0, tk.END)
        self.displayed_songs = []
        count = 0
        for s in songs_db:
            if s["category"] != self.current_cat:
                continue
            if q and (q not in s["code"].lower() and q not in s["title"].lower() and q not in s["artist"].lower()):
                continue
            self.displayed_songs.append(s)
            artist_part = f" - {s['artist']}" if s["artist"] else ""
            status_mark = "✔" if s["has_file"] else "✖"
            self.song_listbox.insert(tk.END, f" [{s['code']}]  {s['title']}{artist_part}   ({status_mark})")
            count += 1
            if count >= 200:
                break

    def on_song_double_click(self, event):
        sel = self.song_listbox.curselection()
        if not sel:
            return
        song = self.displayed_songs[sel[0]]
        try:
            add_to_queue(song["id"])
        except Exception:
            pass

    def refresh_loop(self):
        if current_song:
            art = f" - {current_song['artist']}" if current_song.get("artist") else ""
            self.lbl_playing.config(text=f"Playing: [{current_song['code']}] {current_song['title']}{art}")
        else:
            self.lbl_playing.config(text="သီချင်း မဖွင့်ရသေးပါ (Ready)")

        self.queue_listbox.delete(0, tk.END)
        for idx, item in enumerate(list(song_queue)):
            self.queue_listbox.insert(tk.END, f" {idx + 1}. [{item['code']}] {item['title']}")

        if not hasattr(self, "_initial_loaded") and len(songs_db) > 0:
            self._initial_loaded = True
            self.update_song_list()

        self.root.after(1000, self.refresh_loop)


def run_api_server():
    scan_videos()
    load_databases()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    threading.Thread(target=run_api_server, daemon=True).start()
    root = tk.Tk()
    ui = MI7DesktopUI(root)
    root.mainloop()




