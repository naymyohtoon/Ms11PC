from collections import deque
import os
import re
import threading
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import openpyxl
from pydantic import BaseModel
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
]
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".dat", ".vob", ".avi", ".mpg", ".mpeg")

MYANMAR_DIGITS = {
    "0": "၀",
    "1": "၁",
    "2": "၂",
    "3": "၃",
    "4": "၄",
    "5": "၅",
    "6": "၆",
    "7": "၇",
    "8": "၈",
    "9": "၉",
}


def w54_to_unicode(text: str) -> str:
  if text is None:
    return ""
  text = str(text).strip()
  if not text:
    return ""

  multi_map = {
      "Q": "\u103B\u103E",
      "T": "\u103D\u103E",
      "F": "\u1004\u103A\u1039",
      "L": "\u103E\u102F",
      "I": "\u103E\u1030",
      "E": "\u1014\u1039\u1010",
      "Å": "\u1039\u1010",
      "W": "\u103C\u103D",
      "<": "\u103C",
      ">": "\u103C",
      "©": "\u1000\u1039\u1000",
      "®": "\u100F\u1039\u100D",
      "Æ": "\u1012\u1039\u1013",
      "Ç": "\u1015\u1039\u1015",
      "É": "\u1019\u1039\u1019",
      "Ê": "\u101C\u1039\u101C",
      "Ë": "\u101E\u1039\u101E",
  }

  text = re.sub(
      r"a([u-zA-Z0-9\'\"\#\!\[\]\*\,\&\\QTEW<>]{1,4})f", r"\u1031\1\u102B", text
  )

  for k, v in multi_map.items():
    text = text.replace(k, v)

  char_map = {
      "u": "က",
      "c": "ခ",
      "*": "ဂ",
      "C": "ဃ",
      "i": "င",
      "p": "စ",
      "q": "ဆ",
      "Z": "ဇ",
      "#": "ဋ",
      "X": "ဌ",
      "!": "ဍ",
      "\\": "ဎ",
      "P": "ဏ",
      "w": "တ",
      "x": "ထ",
      "'": "ဒ",
      '"': "ဓ",
      "e": "န",
      "y": "ပ",
      "z": "ဖ",
      "A": "ဗ",
      "b": "ဘ",
      "r": "မ",
      ",": "ယ",
      "&": "ရ",
      "v": "လ",
      "0": "ဝ",
      "o": "သ",
      "[": "ဟ",
      "V": "ဠ",
      "t": "အ",
      "n": "ည",
      "N": "ဉ",
      "a": "\u1031",
      "m": "\u102C",
      "g": "\u102B",
      "d": "\u102D",
      "D": "\u102E",
      "k": "\u102F",
      "K": "\u1030",
      "J": "\u1032",
      "H": "\u1036",
      "h": "\u1037",
      ";": "\u1038",
      "f": "\u103A",
      "s": "\u103B",
      "j": "\u103C",
      "M": "\u103C",
      "B": "\u103C",
      "G": "\u103D",
      "S": "\u103E",
      "1": "၁",
      "2": "၂",
      "3": "၃",
      "4": "၄",
      "5": "၅",
      "6": "၆",
      "7": "၇",
      "8": "၈",
      "9": "၉",
  }

  res = "".join(char_map.get(ch, ch) for ch in text)

  res = re.sub(
      r"(\u1031)?(\u1004\u103A\u1039)([\u1000-\u1021])", r"\2\3\1", res
  )
  res = re.sub(r"(\u103C)([\u1000-\u1021])", r"\2\1", res)
  res = re.sub(
      r"(\u1031)([\u1000-\u1021][\u103B-\u103E]*)", r"\2\1", res
  )
  res = res.replace("\u103E\u103D", "\u103D\u103E")
  res = re.sub(r"([\u102F\u1030])([\u103B-\u103E])", r"\2\1", res)
  res = res.replace("\u1036\u102D", "\u102D\u1036")
  res = res.replace("\u1037\u103A", "\u103A\u1037")
  res = res.replace("ဂမုှိင်္ရ", "ဂမုန်းရ")

  return res


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
  print("Scanning video folders...")
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

  print("Loading Excel database...")
  wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
  ws = wb.active
  temp_songs = []

  for row in ws.iter_rows(min_row=2, values_only=True):
    if not row or len(row) < 3:
      continue
    raw_code = row[1] if len(row) > 1 else None
    raw_title = row[2] if len(row) > 2 else None
    raw_artist = row[4] if len(row) > 4 else None
    raw_album = row[8] if len(row) > 8 else None

    code = normalize_code(raw_code)
    if not code or not raw_title:
      continue

    title = w54_to_unicode(raw_title)
    artist = w54_to_unicode(raw_artist) if raw_artist else "အမည်မသိ"
    album = w54_to_unicode(raw_album) if raw_album else ""

    file_path = video_index.get(code, "")
    category = "MYANMAR"
    if file_path:
      upper_path = file_path.upper()
      if "CHINESE" in upper_path:
        category = "CHINA"
      elif "ENGLISH" in upper_path:
        category = "ENGLISH"
      elif any(
          x in upper_path for x in ["SHANN", "RAKHINE", "KACHIN", "PAOH"]
      ):
        category = "ETHNIC"
      elif "INDIA" in upper_path:
        category = "INTERNATIONAL"
      elif "DISCO" in upper_path:
        category = "DISCO"

    temp_songs.append({
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
  print(f"Loaded {len(songs_db)} songs from Excel.")


vlc_instance = vlc.Instance("--no-video-title-show", "--fullscreen")
player = vlc_instance.media_player_new()
player.set_fullscreen(True)

song_queue = deque()
current_song: Optional[Dict] = None
is_repeat = False
vocal_mode = 0


def play_media_file(song_item: Dict):
  global current_song, vocal_mode
  path = song_item.get("path") or video_index.get(song_item["code"])
  if not path or not os.path.exists(path):
    print(f"Video file not found for code: {song_item['code']}")
    return False

  current_song = song_item
  media = vlc_instance.media_new(path)
  player.set_media(media)
  player.play()
  time.sleep(0.3)
  player.set_fullscreen(True)
  vocal_mode = 0
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


class SongRequest(BaseModel):
  code: str


@app.on_event("startup")
def startup_event():
  scan_videos()
  load_excel_db()


@app.get("/status")
def get_status():
  return {
      "connected": True,
      "current_song": current_song,
      "queue": list(song_queue),
      "queue_count": len(song_queue),
      "is_playing": player.is_playing() == 1,
      "is_repeat": is_repeat,
      "vocal_mode": vocal_mode,
      "volume": player.audio_get_volume(),
  }


@app.get("/songs")
def get_songs(
    q: str = Query(""),
    category: str = Query("ALL"),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
  q_clean = q.strip().lower()
  filtered = []

  for s in songs_db:
    if category != "ALL" and s["category"] != category:
      continue
    if q_clean:
      if (
          q_clean not in s["code"].lower()
          and q_clean not in s["title"].lower()
          and q_clean not in s["artist"].lower()
          and q_clean not in s["album"].lower()
      ):
        continue
    filtered.append({
        "code": s["code"],
        "title": s["title"],
        "artist": s["artist"],
        "album": s["album"],
        "category": s["category"],
    })

  return {
      "total": len(filtered),
      "items": filtered[offset : offset + limit],
  }


@app.get("/albums")
def get_albums(q: str = "", limit: int = 100):
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
    if len(albums) >= limit:
      break
  return {"albums": albums}


@app.post("/queue/add")
def add_to_queue(req: SongRequest):
  found = next((s for s in songs_db if s["code"] == req.code), None)
  if not found:
    path = video_index.get(req.code)
    if not path:
      raise HTTPException(status_code=404, detail="Song not found")
    found = {
        "code": req.code,
        "title": f"Song {req.code}",
        "artist": "",
        "album": "",
        "path": path,
    }

  if not current_song and player.is_playing() == 0:
    play_media_file(found)
    return {"message": "Playing now", "queue_count": len(song_queue)}

  song_queue.append(found)
  return {"message": "Added to queue", "queue_count": len(song_queue)}


@app.post("/queue/priority")
def priority_queue(req: SongRequest):
  existing = next((s for s in song_queue if s["code"] == req.code), None)
  if existing:
    song_queue.remove(existing)
    song_queue.appendleft(existing)
  else:
    found = next((s for s in songs_db if s["code"] == req.code), None)
    if found:
      song_queue.appendleft(found)
  return {"queue": list(song_queue), "queue_count": len(song_queue)}


@app.post("/queue/remove")
def remove_from_queue(req: SongRequest):
  existing = next((s for s in song_queue if s["code"] == req.code), None)
  if existing:
    song_queue.remove(existing)
  return {"queue": list(song_queue), "queue_count": len(song_queue)}


@app.post("/control/{action}")
def control_player(action: str):
  global is_repeat, vocal_mode, current_song

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
  elif action == "vocal":
    tracks = player.audio_get_track_description()
    valid_tracks = [t[0] for t in tracks if t[0] != -1] if tracks else []
    if len(valid_tracks) >= 2:
      curr_track = player.audio_get_track()
      next_track = (
          valid_tracks[1] if curr_track == valid_tracks[0] else valid_tracks[0]
      )
      player.audio_set_track(next_track)
      vocal_mode = 1 if next_track == valid_tracks[1] else 0
    else:
      if vocal_mode == 0:
        player.audio_set_channel(4)
        vocal_mode = 1
      else:
        player.audio_set_channel(1)
        vocal_mode = 0
  elif action == "vol_up":
    vol = player.audio_get_volume()
    player.audio_set_volume(min(150, vol + 10))
  elif action == "vol_down":
    vol = player.audio_get_volume()
    player.audio_set_volume(max(0, vol - 10))
  elif action == "mute":
    player.audio_toggle_mute()

  return get_status()


if __name__ == "__main__":
  uvicorn.run(app, host="0.0.0.0", port=8000)

