from flask import Flask, redirect, request
import subprocess
import json
import os
import threading
import time
from datetime import datetime

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
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def play_station(station):
    url = STREAMS.get(station)
    if url:
        run("/usr/bin/pkill -f vlc")
        run(f"/usr/bin/cvlc --no-video '{url}' >> /tmp/pi-radio.log 2>&1 &")

def alarm_loop():
    while True:
        config = load_config()
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        if config["alarm_enabled"] and config["last_alarm_date"] != today:
            is_weekend = now.weekday() >= 5
            alarm_time = config["weekend_time"] if is_weekend else config["weekday_time"]

            if now.strftime("%H:%M") == alarm_time:
                play_station(config["station"])
                config["last_alarm_date"] = today
                save_config(config)

        time.sleep(30)

@app.route("/")
def index():
    config = load_config()
    
    volume = get_volume()    

    alarm_status = "Enabled" if config["alarm_enabled"] else "Disabled"

    stream_buttons = ""
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
        <p>Alarm Station: <b>{config["station"].upper()}</b></p>
        <p>Volume: <b>{volume}%</b></p>
      </div>

      <h2>Streams</h2>
      {stream_buttons}

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
    config["alarm_enabled"] = True
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

if __name__ == "__main__":
    threading.Thread(target=alarm_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
