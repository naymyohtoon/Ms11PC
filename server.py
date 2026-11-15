from collections import deque
import os
import re
import socket
import subprocess
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


def open_firewall_port():
    """Windows Firewall တွင် Port 8000 ကို အလိုအလျောက် ဖွင့်ပေးခြင်း"""
    try:
        subprocess.run(
            'netsh advfirewall firewall add rule name="NMH Karaoke Server" dir=in action=allow protocol=TCP localport=8000',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


app = FastAPI(title="NMH Karaoke Server")

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
        ip = s.getsockname()
        s.close()
        return ip
    except Exception:
        try:
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname):
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
                    name_no_ext = os.path.splitext(file).strip()
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
                    name_no_ext = os.path.splitext(file).strip()
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
            code = normalize_code(row)
            raw_title = row
            if not code or not raw_title:
                continue

            title = str(raw_title).strip()
            artist = str(row).strip() if len(row) > 2 and row else "အမည်မသိ"
            coartist = str(row).strip() if len(row) > 3 and row else ""
            if coartist:
                artist = f"{artist} + {coartist}"
            album = str(row).strip() if len(row) > 4 and row else ""

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
            code = normalize_code(row)
            raw_title = row
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
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    q_clean = q.strip().lower()
    matched = []
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
        matched.append(s)
    return matched[offset : offset + limit]


@app.get("/browse/artists")
def browse_artists(
    q: str = Query(""),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
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
    return artists[offset : offset + limit]


@app.get("/browse/albums")
def browse_albums(
    q: str = Query(""),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
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
    return albums[offset : offset + limit]


@app.get("/browse/filter")
def browse_filter(
    artist: str = Query(""),
    album: str = Query(""),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    results = []
    for s in songs_db:
        if s["category"] != "MYANMAR":
            continue
        if artist and s["artist"] == artist:
            results.append(s)
        elif album and s["album"] == album:
            results.append(s)
    return results[offset : offset + limit]


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
class NMHDesktopUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("NMH Karaoke System")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="#23272B")
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))

        self.screen_mode = "HOME"
        self.current_cat = "MYANMAR"
        self.displayed_items = []
        self.num_input = ""
        self.build_ui()
        self.refresh_loop()

    def build_ui(self):
        top_frame = tk.Frame(self.root, bg="#181A1D", height=80)
        top_frame.pack(fill=tk.X, padx=10, pady=8)
        top_frame.pack_propagate(False)

        try:
            logo_path = resource_path("image_afebac29.jpg")
            orig = Image.open(logo_path)
            ratio = 68 / orig.height
            new_w = int(orig.width * ratio)
            img = orig.resize((new_w, 68), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(img)
            tk.Label(top_frame, image=self.logo_photo, bg="#181A1D").pack(side=tk.LEFT, padx=10)
        except Exception:
            tk.Label(
                top_frame, text="NMH KARAOKE SYSTEM", font=("Pyidaungsu", 18, "bold"),
                fg="#00E5FF", bg="#181A1D"
            ).pack(side=tk.LEFT, padx=15)

        self.lbl_playing = tk.Label(
            top_frame, text="သီချင်း မဖွင့်ရသေးပါ (Song Playing...)", font=("Pyidaungsu", 13, "bold"),
            fg="#64FFDA", bg="#263238", anchor="w", padx=12
        )
        self.lbl_playing.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        ip_text = f"IP: {get_local_ip()}"
        self.lbl_ip = tk.Label(
            top_frame, text=ip_text, font=("Consolas", 14, "bold"),
            fg="#FFFFFF", bg="#00695C", padx=16, pady=8
        )
        self.lbl_ip.pack(side=tk.RIGHT, padx=10)

        body = tk.Frame(self.root, bg="#23272B")
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        left_panel = tk.Frame(body, bg="#1C1F22", width=380, highlightbackground="#00BFA5", highlightthickness=1)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)

        self.q_header = tk.Label(
            left_panel, text="ရွေးထားသောသီချင်းများ (0)", font=("Pyidaungsu", 13, "bold"),
            fg="white", bg="#00695C", pady=8
        )
        self.q_header.pack(fill=tk.X)

        self.queue_listbox = tk.Listbox(
            left_panel, bg="#1C1F22", fg="white", font=("Pyidaungsu", 12),
            selectbackground="#00897B", borderwidth=0, highlightthickness=0
        )
        self.queue_listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        q_btn_row = tk.Frame(left_panel, bg="#1C1F22")
        q_btn_row.pack(fill=tk.X, padx=6, pady=6)
        tk.Button(q_btn_row, text="↑ ဦးစားပေး", font=("Pyidaungsu", 11, "bold"), bg="#2E7D32", fg="white", command=self.ui_priority).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(q_btn_row, text="× ဖျက်မည်", font=("Pyidaungsu", 11, "bold"), bg="#C62828", fg="white", command=self.ui_remove).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.right_panel = tk.Frame(body, bg="#2B2E33")
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        bottom_bar = tk.Frame(self.root, bg="#141618", height=54)
        bottom_bar.pack(fill=tk.X, padx=10, pady=(4, 8))

        controls = [
            ("Play/Pause", "#FF4081", lambda: control_player("play_pause")),
            ("Stop", "#FF5252", lambda: control_player("stop")),
            ("Repeat", "#E040FB", lambda: control_player("repeat")),
            ("<<<<", "#40C4FF", lambda: control_player("rewind")),
            (">>>>", "#40C4FF", lambda: control_player("forward")),
            ("Re-Start", "#F50057", lambda: control_player("restart")),
            ("Next", "#F50057", lambda: control_player("next")),
            ("HOME", "#69F0AE", self.show_home_view),
            ("Vocal", "#FFD740", lambda: control_player("vocal_toggle")),
            ("Vol-", "#18FFFF", lambda: control_player("volume", max(0, player.audio_get_volume() - 10))),
            ("Vol+", "#18FFFF", lambda: control_player("volume", min(100, player.audio_get_volume() + 10))),
            ("Mute", "#90A4AE", lambda: control_player("volume", 0 if player.audio_get_volume() > 0 else 80)),
        ]
        for text, col, cmd in controls:
            tk.Button(
                bottom_bar, text=text, font=("Pyidaungsu", 10, "bold"),
                bg="#263238", fg=col, padx=6, pady=6, command=cmd
            ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2, pady=6)

        self.show_home_view()

    def clear_right_panel(self):
        for w in self.right_panel.winfo_children():
            w.destroy()

    def show_home_view(self):
        self.screen_mode = "HOME"
        self.clear_right_panel()

        top_cards = tk.Frame(self.right_panel, bg="#2B2E33")
        top_cards.pack(fill=tk.BOTH, expand=True, padx=12, pady=(14, 0))

        mm_box = tk.Frame(top_cards, bg="#00796B", highlightbackground="#64FFDA", highlightthickness=2)
        mm_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        tk.Label(mm_box, text="မြန်မာသီချင်းများ\n(မြန်မာ)", font=("Pyidaungsu", 20, "bold"), fg="white", bg="#00796B").pack(expand=True)

        disco_btn = tk.Button(
            top_cards, text="💿\nDisco Song", font=("Pyidaungsu", 18, "bold"),
            bg="#4527A0", fg="#FFD740", activebackground="#5E35B1",
            command=lambda: self.show_list_view("DISCO", "Disco Songs")
        )
        disco_btn.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        tree_canvas = tk.Canvas(self.right_panel, height=45, bg="#2B2E33", highlightthickness=0)
        tree_canvas.pack(fill=tk.X, padx=12)
        tree_canvas.bind("<Configure>", self.draw_tree_lines)

        sub_cards = tk.Frame(self.right_panel, bg="#2B2E33")
        sub_cards.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 14))

        sub_items = [
            ("အဆိုတော်\nနာမည်နှင့်ရှာပါ", "#AD1457", lambda: self.show_list_view("ARTISTS", "အဆိုတော် စာရင်း")),
            ("တေးစီးရီး\nနာမည်နှင့်ရှာပါ", "#EF6C00", lambda: self.show_list_view("ALBUMS", "တေးစီးရီး စာရင်း")),
            ("သီချင်းနာမည်\nနှင့်ရှာပါ", "#1565C0", lambda: self.show_list_view("MYANMAR", "သီချင်းအမည် စာရင်း")),
            ("သီချင်းနံပါတ်\nနှင့်ရှာပါ", "#00838F", self.show_numpad_view),
        ]
        for label, bg_col, cmd in sub_items:
            tk.Button(
                sub_cards, text=label, font=("Pyidaungsu", 13, "bold"),
                bg=bg_col, fg="white", command=cmd
            ).pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
    def draw_tree_lines(self, event):
        c = event.widget
        c.delete("all")
        w, h = event.width, event.height
        root_x = w * 0.25
        mid_y = h * 0.45
        c.create_line(root_x, 0, root_x, mid_y, fill="#64FFDA", width=2)
        targets = [w * 0.125, w * 0.375, w * 0.625, w * 0.875]
        c.create_line(targets[0], mid_y, targets[3], mid_y, fill="#64FFDA", width=2)
        for tx in targets:
            c.create_line(tx, mid_y, tx, h, fill="#64FFDA", width=2)

    def show_numpad_view(self):
        self.screen_mode = "NUMPAD"
        self.num_input = ""
        self.clear_right_panel()

        wrap = tk.Frame(self.right_panel, bg="#2B2E33")
        wrap.pack(expand=True)

        left_col = tk.Frame(wrap, bg="#2B2E33")
        left_col.pack(side=tk.LEFT, padx=20)

        self.lbl_num = tk.Label(
            left_col, text="သီချင်းနံပါတ် ရိုက်ထည့်ပါ", font=("Pyidaungsu", 18, "bold"),
            fg="#FFD740", bg="#141618", width=20, pady=16
        )
        self.lbl_num.pack(pady=10)

        btn_row = tk.Frame(left_col, bg="#2B2E33")
        btn_row.pack(pady=8)
        tk.Button(btn_row, text="← နောက်သို့", font=("Pyidaungsu", 12, "bold"), bg="#546E7A", fg="white", padx=12, pady=8, command=self.show_home_view).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="ဖျက်မည်", font=("Pyidaungsu", 12, "bold"), bg="#C62828", fg="white", padx=12, pady=8, command=self.num_backspace).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="ထည့်မည်", font=("Pyidaungsu", 12, "bold"), bg="#2E7D32", fg="white", padx=14, pady=8, command=self.num_submit).pack(side=tk.LEFT, padx=4)

        pad_frame = tk.Frame(wrap, bg="#2B2E33")
        pad_frame.pack(side=tk.RIGHT, padx=20)
        keys = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["C", "0", "OK"]]
        for r, row_keys in enumerate(keys):
            for c, k in enumerate(row_keys):
                tk.Button(
                    pad_frame, text=k, font=("Consolas", 16, "bold"), bg="#37474F", fg="white",
                    width=6, height=2, command=lambda val=k: self.on_num_key(val)
                ).grid(row=r, column=c, padx=4, pady=4)

    def on_num_key(self, k: str):
        if k == "C":
            self.num_input = ""
        elif k == "OK":
            self.num_submit()
            return
        else:
            self.num_input += k
        self.lbl_num.config(text=self.num_input if self.num_input else "သီချင်းနံပါတ် ရိုက်ထည့်ပါ")

    def num_backspace(self):
        self.num_input = self.num_input[:-1]
        self.lbl_num.config(text=self.num_input if self.num_input else "သီချင်းနံပါတ် ရိုက်ထည့်ပါ")

    def num_submit(self):
        if self.num_input:
            try:
                add_to_queue(self.num_input)
            except Exception:
                pass
            self.num_input = ""
            self.lbl_num.config(text="သီချင်းနံပါတ် ရိုက်ထည့်ပါ")

    def show_list_view(self, mode: str, title: str, filter_val: str = ""):
        self.screen_mode = mode
        self.filter_val = filter_val
        self.clear_right_panel()

        top = tk.Frame(self.right_panel, bg="#181A1D", pady=6)
        top.pack(fill=tk.X)

        tk.Button(top, text="← HOME", font=("Pyidaungsu", 11, "bold"), bg="#00796B", fg="white", padx=10, command=self.show_home_view).pack(side=tk.LEFT, padx=8)
        tk.Label(top, text=title, font=("Pyidaungsu", 14, "bold"), fg="#FFD740", bg="#181A1D").pack(side=tk.LEFT, padx=10)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.populate_list())
        tk.Entry(top, textvariable=self.search_var, font=("Pyidaungsu", 13), bg="#37474F", fg="white", insertbackground="white", width=26).pack(side=tk.RIGHT, padx=10)
        tk.Label(top, text="ရှာရန်:", font=("Pyidaungsu", 12), fg="#B0BEC5", bg="#181A1D").pack(side=tk.RIGHT)

        self.listbox = tk.Listbox(self.right_panel, bg="#1E2226", fg="white", font=("Pyidaungsu", 12), selectbackground="#00796B")
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.listbox.bind("<Double-Button-1>", self.on_list_double_click)
        self.populate_list()

        def populate_list(self):
        q = self.search_var.get().strip().lower()
        self.listbox.delete(0, tk.END)
        self.displayed_items = []

        if self.screen_mode == "ARTISTS":
            for art in browse_artists(q=q, offset=0, limit=5000):
                self.displayed_items.append(("ARTIST", art))
                self.listbox.insert(tk.END, f" 🎤  {art}")
        elif self.screen_mode == "ALBUMS":
            for alb in browse_albums(q=q, offset=0, limit=5000):
                self.displayed_items.append(("ALBUM", alb))
                self.listbox.insert(tk.END, f" 💿  {alb}")
        elif self.screen_mode == "FILTER_ARTIST":
            for s in browse_filter(artist=self.filter_val, offset=0, limit=5000):
                self.displayed_items.append(("SONG", s))
                self.listbox.insert(tk.END, f" [{s['code']}]  {s['title']} - {s['artist']}")
        elif self.screen_mode == "FILTER_ALBUM":
            for s in browse_filter(album=self.filter_val, offset=0, limit=5000):
                self.displayed_items.append(("SONG", s))
                self.listbox.insert(tk.END, f" [{s['code']}]  {s['title']} - {s['artist']}")
        else:
            cat = "DISCO" if self.screen_mode == "DISCO" else "MYANMAR"
            for s in search_songs(q=q, category=cat, offset=0, limit=50000):
                self.displayed_items.append(("SONG", s))
                mark = "✔" if s["has_file"] else "✖"
                art = f" - {s['artist']}" if s["artist"] else ""
                self.listbox.insert(tk.END, f" {mark} [{s['code']}]  {s['title']}{art}")

    def on_list_double_click(self, event):
        sel = self.listbox.curselection()
        if not sel:
            return
        kind, data = self.displayed_items[sel[0]]
        if kind == "ARTIST":
            self.show_list_view("FILTER_ARTIST", data, filter_val=data)
        elif kind == "ALBUM":
            self.show_list_view("FILTER_ALBUM", data, filter_val=data)
        elif kind == "SONG":
            try:
                add_to_queue(data["id"])
            except Exception:
                pass

    def ui_priority(self):
        sel = self.queue_listbox.curselection()
        if sel:
            priority_queue(sel[0])

    def ui_remove(self):
        sel = self.queue_listbox.curselection()
        if sel:
            remove_from_queue(sel[0])

    def refresh_loop(self):
        if current_song:
            art = f" - {current_song['artist']}" if current_song.get("artist") else ""
            self.lbl_playing.config(text=f"Playing: [{current_song['code']}] {current_song['title']}{art}")
        else:
            self.lbl_playing.config(text="သီချင်း မဖွင့်ရသေးပါ (Song Playing...)")

        q_list = list(song_queue)
        self.q_header.config(text=f"ရွေးထားသောသီချင်းများ ({len(q_list)})")
        if self.queue_listbox.size() != len(q_list):
            self.queue_listbox.delete(0, tk.END)
            for idx, item in enumerate(q_list):
                self.queue_listbox.insert(tk.END, f" {idx + 1}. [{item['code']}] {item['title']}")

        self.root.after(1000, self.refresh_loop)


def run_api_server():
    open_firewall_port()
    scan_videos()
    load_databases()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    threading.Thread(target=run_api_server, daemon=True).start()
    root = tk.Tk()
    ui = NMHDesktopUI(root)
    root.mainloop()
