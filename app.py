from flask import Flask, redirect, request
import subprocess
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
import urllib.parse
import socket
HOSTNAME = socket.gethostname()

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
    "AIR Raagam" : "https://air.pc.cdn.bitgravity.com/air/live/pbaudio044/chunklist.m3u8",
    "indianlinkradio" : "https://indianlink1.radioca.st/;",
    "Radio Caprice - indian folk" : "http://79.111.14.76:8000/indianfolk",
    "Beatles Radio": "http://www.beatlesradio.com:8000/stream/1/",
    "Beatles-A-Rama": "https://stream.radio.co/se13369565/listen",
    "Exclusively The Beatles": "https://streaming.exclusive.radio/er/beatles/icecast.audio",
    "The Beatles (Dedicated Beatles stream)": "https://sp0.wlservices.org:9996/stream",
    "Exclusively Led Zeppelin — full catalog": "https://streaming.exclusive.radio/er-app/ledzeppelin/icecast.audio",
    "Exclusively Led Zeppelin – Only Hits": "https://streaming.exclusive.radio/er-app/ledzeppelinhits/icecast.audio",
    "181.FM — The Eagle (Classic Rock)" : "https://listen.181fm.com/181-eagle_128k.mp3?utm_source=chatgpt.com",
    "BAGeL Radio" : "https://ais-sa3.cdnstream1.com/2606_128.mp3?utm_source=chatgpt.com",
    "SomaFM — Underground 80s" : "https://ice5.somafm.com/u80s-128-mp3?utm_source=chatgpt.com",
    "Punkrockers Radio" : "https://stream.punkrockers-radio.de:8443/prr.flac?utm_source=chatgpt.com",
    "WFMU" : "http://stream0.wfmu.org/freeform-128k.mp3?utm_source=chatgpt.com",
}

DEFAULT_CONFIG = {
    "alarm_enabled": False,
    "weekday_time": "07:00",
    "weekend_time": "08:00",
    "station": "kutx",
    "alarm_source": "station",
    "alarm_file": "",
    "last_alarm_date": "",
    "speaker_a_name": "Speaker A",
    "speaker_a_mac": "",
    "speaker_b_name": "Speaker B",
    "speaker_b_mac": "",
    "current_source": "",
    "current_title": ""
}

def get_volume():
    try:
        result = subprocess.check_output(
            "/usr/bin/wpctl get-volume @DEFAULT_AUDIO_SINK@",
            shell=True,
            text=True
        ).strip()

        volume = float(result.split()[1])
        return int(volume * 100)

    except Exception:
        return "Unknown"
    
def vlc_is_running():
    result = subprocess.run(
        ["/usr/bin/pgrep", "-f", "vlc"],
        capture_output=True
    )
    return result.returncode == 0

def run(cmd):
    subprocess.run(cmd, shell=True)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

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

        config = load_config()
        config["current_source"] = "stream"
        config["current_title"] = station
        save_config(config)

def play_alarm(config):
    run("/usr/bin/pkill -f vlc")

    if config.get("alarm_source") == "file" and config.get("alarm_file"):
        music_path = Path(MUSIC_DIR).resolve()
        full_path = (music_path / config["alarm_file"]).resolve()

        if str(full_path).startswith(str(music_path)) and full_path.exists():
            run(f'/usr/bin/cvlc --no-video "{full_path}" >> /tmp/pi-radio.log 2>&1 &')
            config["current_source"] = "file"
            config["current_title"] = config["alarm_file"]
            return

    station = config.get("station", "kutx")
    play_station(station)
    if station in STREAMS:
        config["current_source"] = "stream"
        config["current_title"] = station

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
                config = load_config()
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

def bluetooth_connect(mac_address):
    if not mac_address:
        return False

    result = subprocess.run(
        ["/usr/bin/bluetoothctl", "connect", mac_address],
        capture_output=True,
        text=True,
        timeout=20
    )

    output = result.stdout + result.stderr
    return result.returncode == 0 or "Connection successful" in output


def bluetooth_disconnect(mac_address):
    if not mac_address:
        return

    subprocess.run(
        ["/usr/bin/bluetoothctl", "disconnect", mac_address],
        capture_output=True,
        text=True,
        timeout=10
    )


def connect_speaker(speaker_key):
    config = load_config()

    selected_mac = config.get(f"{speaker_key}_mac", "")
    other_key = "speaker_b" if speaker_key == "speaker_a" else "speaker_a"
    other_mac = config.get(f"{other_key}_mac", "")

    # Disconnect the old possible master first
    bluetooth_disconnect(other_mac)

    time.sleep(1)

    return bluetooth_connect(selected_mac)

@app.route("/")
def index():
    config = load_config()
    volume = get_volume()

    if vlc_is_running():
        current_source = config.get("current_source", "")
        current_title = config.get("current_title", "")

        if current_source == "stream":
            now_playing = f"📻 {current_title}"
        elif current_source == "file":
            now_playing = f"🎵 {current_title}"
        else:
            now_playing = "Playing"
    else:
        now_playing = "Nothing Playing"

    speaker_a_name = config.get("speaker_a_name", "Speaker A")
    speaker_b_name = config.get("speaker_b_name", "Speaker B")

    alarm_status = "Enabled" if config["alarm_enabled"] else "Disabled"

    stream_buttons = ""
    for name in STREAMS:
        stream_buttons += f'<a href="/play/{urllib.parse.quote(name)}"><button>{name.upper()}</button></a>'

    music_files = get_music_files()

    music_list = ""
    for file in music_files:
        encoded = urllib.parse.quote(file)
        music_list += f'''
        <li class="music-item">
            <span class="music-name">🎵 {file}</span>
            <a href="/play-file?file={encoded}">
                <button class="small-button">Play</button>
            </a>
            <a href="/set-alarm-file?file={encoded}">
                <button class="small-button">Alarm</button>
            </a>
        </li>
        '''

    return f"""
    <html>
    <head>
      <title>{HOSTNAME.title()} Pi Radio</title>
      <style>
        body {{
          font-family: sans-serif;
          text-align: center;
          background: #111;
          color: white;
          padding-top: 30px;
        }}

        .now-playing {{
            font-size: 24px;
            background: #333;
            padding: 12px 18px;
            border-radius: 10px;
            margin-bottom: 18px;
        }}

        button {{
          font-size: 22px;
          padding: 18px 30px;
          margin: 8px;
          border-radius: 12px;
        }}

        .small-button {{
          font-size: 16px;
          padding: 8px 14px;
          margin: 4px;
          border-radius: 8px;
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

        details {{
          background: #181818;
          margin: 35px auto;
          padding: 20px;
          border-radius: 14px;
          max-width: 900px;
        }}

        summary {{
          cursor: pointer;
          font-size: 26px;
          font-weight: bold;
          margin-bottom: 15px;
        }}

        .music-list {{
          list-style: none;
          padding: 0;
          margin: 0;
        }}

        .music-item {{
          background: #222;
          margin: 10px auto;
          padding: 12px;
          border-radius: 10px;
          max-width: 800px;
        }}

        .music-name {{
          display: block;
          margin-bottom: 8px;
          word-break: break-word;
        }}
      </style>
    </head>

    <body>
      <h1>{HOSTNAME.title()} Pi Radio</h1>

        <div class="status">
        <h2>Status</h2>

        <p class="now-playing">
            Now Playing: <b>{now_playing}</b>
        </p>

        <p>Volume: <b>{volume}%</b></p>
        <p>Alarm: <b>{alarm_status}</b></p>
        <p>Weekday Alarm: <b>{config["weekday_time"]}</b></p>
        <p>Weekend Alarm: <b>{config["weekend_time"]}</b></p>
        <p>Alarm Source: <b>{config.get("alarm_source", "station")}</b></p>
        <p>Alarm Station: <b>{config["station"].upper()}</b></p>
        <p>Alarm File: <b>{config.get("alarm_file", "")}</b></p>
        </div>

        <h2>Streams</h2>
        {stream_buttons}

        <h2>Volume</h2>
        <a href="/vol/down"><button>Vol -</button></a>
        <a href="/vol/up"><button>Vol +</button></a>
        <a href="/mute"><button>Mute</button></a>
        <a href="/stop"><button>Stop</button></a>

        <h2>Bluetooth Speakers</h2>

        <a href="/bluetooth/connect/speaker_a">
            <button>Connect {speaker_a_name}</button>
        </a>

        <a href="/bluetooth/connect/speaker_b">
            <button>Connect {speaker_b_name}</button>
        </a>

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

        <p>
            <a href="/set-alarm-station">
            <button>Use Station for Alarm</button>
            </a>
        </p>

        <h2>System Controls</h2>

        <form action="/system/restart-radio" method="post"
            onsubmit="return confirm('Restart Pi Radio service?');">
            <button type="submit">🔄 Restart Pi Radio</button>
        </form>

        <form action="/system/reboot" method="post"
            onsubmit="return confirm('Reboot the entire Raspberry Pi?');">
            <button type="submit">⏻ Reboot Raspberry Pi</button>
        </form>

      <details>
        <summary>Music Library</summary>

        <ul class="music-list">
          {music_list}
        </ul>
      </details>

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

    config = load_config()
    config["current_source"] = ""
    config["current_title"] = ""
    save_config(config)

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
    config["last_alarm_date"] = ""
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

    if not full_path.is_relative_to(music_path):
        return "Invalid file path", 400

    if not full_path.exists():
        return "File not found", 404

    run("/usr/bin/pkill -f vlc")
    run(f'/usr/bin/cvlc --no-video "{full_path}" >> /tmp/pi-radio.log 2>&1 &')

    config = load_config()
    config["current_source"] = "file"
    config["current_title"] = rel_file
    save_config(config)

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

@app.route("/bluetooth/connect/<speaker_key>")
def connect_bluetooth_speaker(speaker_key):
    if speaker_key not in ("speaker_a", "speaker_b"):
        return "Invalid speaker", 400

    success = connect_speaker(speaker_key)

    if not success:
        return f"Unable to connect {speaker_key}", 500

    return redirect("/")

@app.route("/system/restart-radio", methods=["POST"])
def restart_radio():
    subprocess.Popen(
        ["/usr/bin/sudo", "-n", "/usr/bin/systemctl",
         "restart", "pi-radio.service"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    return "Pi Radio is restarting. Refresh the page in a few seconds."


@app.route("/system/reboot", methods=["POST"])
def reboot_pi():
    subprocess.Popen(
        ["/usr/bin/sudo", "-n", "/usr/bin/systemctl",
         "reboot"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    return "Raspberry Pi is rebooting. Reconnect in a minute or two."

if __name__ == "__main__":
    threading.Thread(target=alarm_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
    
