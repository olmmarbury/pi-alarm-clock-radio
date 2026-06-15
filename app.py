from flask import Flask, redirect, request
import subprocess
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
import urllib.parse
AUDIO_EXTENSIONS = (".mp3", ".flac", ".wav", ".m4a", ".ogg")
MUSIC_DIR = "/home/matt/music"

app = Flask(__name__)

CONFIG_FILE = "/home/matt/pi-radio/config.json"

STREAMS = {
    "kutx": "https://streams.kut.org/4428_56?aw_0_1st.playerid=kutx-free",
    "kexp": "https://kexp.streamguys1.com/kexp160.aac",
    "GDRadio.net": "https://ssl.rockhost.com/proxy/gdradiov2?mp=/stream",
    "BBC World Service": "https://streams.kut.org/4427/playlist.m3u8",
    "KUT": "https://streams.kut.org/4426_56?aw_0_1st.playerid=kut-free",
}

DEFAULT_CONFIG = {
    "alarm_enabled": False,
    "weekday_time": "07:00",
    "weekend_time": "08:00",
    "station": "kutx",
    "alarm_source": "station",
    "alarm_file": "",
    "last_alarm_date": ""
}

def get_volume():
    try:
        result = subprocess.check_output(
            "/usr/bin/wpctl get-volume @DEFAULT_AUDIO_SINK@",
            shell=True,
            text=True
        ).strip()

        # Example output:
        # Volume: 0.44

        volume = float(result.split()[1])
        return int(volume * 100)

    except Exception:
        return "Unknown"

def run(cmd):
    subprocess.run(cmd, shell=True)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    # Add any new missing config keys without destroying existing settings
    changed = False
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value
            changed = True

    if changed:
        save_config(config)

    return config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def play_station(station):
    url = STREAMS.get(station)
    if url:
        run("/usr/bin/pkill -f vlc")
        run(f"/usr/bin/cvlc --no-video '{url}' >> /tmp/pi-radio.log 2>&1 &")

def play_alarm(config):
    run("/usr/bin/pkill -f vlc")

    if config.get("alarm_source") == "file" and config.get("alarm_file"):
        music_path = Path(MUSIC_DIR).resolve()
        full_path = (music_path / config["alarm_file"]).resolve()

        if str(full_path).startswith(str(music_path)) and full_path.exists():
            run(f'/usr/bin/cvlc --no-video "{full_path}" >> /tmp/pi-radio.log 2>&1 &')
            return

    play_station(config.get("station", "kutx"))

def alarm_loop():
    while True:
        config = load_config()
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        if config["alarm_enabled"] and config["last_alarm_date"] != today:
            is_weekend = now.weekday() >= 5
            alarm_time = config["weekend_time"] if is_weekend else config["weekday_time"]

            if now.strftime("%H:%M") == alarm_time:
                play_alarm(config)
                config["last_alarm_date"] = today
                save_config(config)

        time.sleep(30)

def get_music_files():
    music_path = Path(MUSIC_DIR)
    if not music_path.exists():
        return []

    files = []
    for path in music_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
            rel = path.relative_to(music_path)
            files.append(str(rel))

    return sorted(files)

@app.route("/")
def index():
    config = load_config()
    
    volume = get_volume()    

    alarm_status = "Enabled" if config["alarm_enabled"] else "Disabled"

    stream_buttons = ""

    music_files = get_music_files()

    music_list = ""
    for file in music_files:
        encoded = urllib.parse.quote(file)
        music_list += f'''
        <li>
            {file}
            - <a href="/play-file?file={encoded}">Play</a>
            - <a href="/set-alarm-file?file={encoded}">Use for Alarm</a>
        </li>
        '''

    for name in STREAMS:
        stream_buttons += f'<a href="/play/{name}"><button>{name.upper()}</button></a>'

    return f"""
    <html>
    <head>
      <title>Bedroom Pi Radio</title>
      <style>
        body {{
          font-family: sans-serif;
          text-align: center;
          background: #111;
          color: white;
          padding-top: 30px;
        }}
        button {{
          font-size: 22px;
          padding: 18px 30px;
          margin: 8px;
          border-radius: 12px;
        }}
        input {{
          font-size: 22px;
          padding: 10px;
          margin: 8px;
        }}
        .status {{
          background: #222;
          display: inline-block;
          padding: 20px 35px;
          border-radius: 14px;
          margin-bottom: 20px;
        }}
      </style>
    </head>

    <body>
      <h1>Bedroom Pi Radio</h1>

      <!-- HTML CODE TO ADD TO THE TOP -->
      <div class="status">
        <h2>Status</h2>
        <p>Alarm: <b>{alarm_status}</b></p>
        <p>Weekday Alarm: <b>{config["weekday_time"]}</b></p>
        <p>Weekend Alarm: <b>{config["weekend_time"]}</b></p>
        <p>Alarm Source: <b>{config.get("alarm_source", "station")}</b></p>
        <p>Alarm Station: <b>{config["station"].upper()}</b></p>
        <p>Alarm File: <b>{config.get("alarm_file", "")}</b></p>
        <p>Volume: <b>{volume}%</b></p>
      </div>

      <h2>Streams</h2>
      {stream_buttons}
      
      <h2>Music Files</h2>
      <ul style="list-style: none; padding: 0;">
      {music_list}
      </ul>

      <p>
        <a href="/set-alarm-station"><button>Use Station for Alarm</button></a>
      </p>

      <h2>Volume</h2>
      <a href="/vol/down"><button>Vol -</button></a>
      <a href="/vol/up"><button>Vol +</button></a>
      <a href="/mute"><button>Mute</button></a>
      <a href="/stop"><button>Stop</button></a>

      <h2>Alarm</h2>
      <a href="/alarm/on"><button>Enable Alarm</button></a>
      <a href="/alarm/off"><button>Disable Alarm</button></a>

      <form action="/alarm/set" method="post">
        <p>Weekday Time</p>
        <input type="time" name="weekday_time" value="{config["weekday_time"]}">

        <p>Weekend Time</p>
        <input type="time" name="weekend_time" value="{config["weekend_time"]}">

        <p>
          <button type="submit">Save Alarm Times</button>
        </p>
      </form>
    </body>
    </html>
    """

@app.route("/play/<station>")
def play(station):
    play_station(station)
    return redirect("/")

@app.route("/stop")
def stop():
    run("/usr/bin/pkill -f vlc")
    return redirect("/")

@app.route("/vol/up")
def vol_up():
    run("/usr/bin/wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+")
    return redirect("/")

@app.route("/vol/down")
def vol_down():
    run("/usr/bin/wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-")
    return redirect("/")

@app.route("/mute")
def mute():
    run("/usr/bin/wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle")
    return redirect("/")

@app.route("/alarm/on")
def alarm_on():
    config = load_config()
    config["alarm_enabled"] = True
    save_config(config)
    return redirect("/")

@app.route("/alarm/off")
def alarm_off():
    config = load_config()
    config["alarm_enabled"] = False
    config["last_alarm_date"] = ""
    save_config(config)
    return redirect("/")

@app.route("/alarm/set", methods=["POST"])
def alarm_set():
    config = load_config()
    config["weekday_time"] = request.form["weekday_time"]
    config["weekend_time"] = request.form["weekend_time"]
    config["last_alarm_date"] = ""
    save_config(config)
    return redirect("/")

@app.route("/play-file")
def play_file():
    rel_file = request.args.get("file", "")

    music_path = Path(MUSIC_DIR).resolve()
    full_path = (music_path / rel_file).resolve()

    if not str(full_path).startswith(str(music_path)):
        return "Invalid file path", 400

    if not full_path.exists():
        return "File not found", 404

    run("/usr/bin/pkill -f vlc")
    run(f'/usr/bin/cvlc --no-video "{full_path}" >> /tmp/pi-radio.log 2>&1 &')

    return redirect("/")

@app.route("/set-alarm-file")
def set_alarm_file():
    rel_file = request.args.get("file", "")

    config = load_config()
    config["alarm_source"] = "file"
    config["alarm_file"] = rel_file
    config["last_alarm_date"] = ""
    save_config(config)

    return redirect("/")

@app.route("/set-alarm-station")
def set_alarm_station():
    config = load_config()
    config["alarm_source"] = "station"
    config["last_alarm_date"] = ""
    save_config(config)

    return redirect("/")

if __name__ == "__main__":
    threading.Thread(target=alarm_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
