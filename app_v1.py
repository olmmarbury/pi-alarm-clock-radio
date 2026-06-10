from flask import Flask, redirect
import subprocess

app = Flask(__name__)

STREAMS = {
    "kutx": "https://streams.kut.org/4428_56?aw_0_1st.playerid=kutx-free",
    "kut": "https://kut.streamguys1.com/kut-free",
    "bbc6": "http://stream.live.vc.bbcmedia.co.uk/bbc_6music",
}

def run(cmd):
    subprocess.run(cmd, shell=True)

@app.route("/")
def index():
    buttons = ""
    for name in STREAMS:
        buttons += f'<a href="/play/{name}"><button>{name.upper()}</button></a>'

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
          padding-top: 40px;
        }}
        button {{
          font-size: 24px;
          padding: 20px 35px;
          margin: 10px;
          border-radius: 12px;
        }}
      </style>
    </head>
    <body>
      <h1>Bedroom Pi Radio</h1>

      <h2>Streams</h2>
      {buttons}

      <h2>Volume</h2>
      <a href="/vol/down"><button>Vol -</button></a>
      <a href="/vol/up"><button>Vol +</button></a>
      <a href="/stop"><button>Stop</button></a>
    </body>
    </html>
    """

@app.route("/play/<station>")
def play(station):
    url = STREAMS.get(station)
    if url:
        run("pkill vlc")
        run(f"cvlc --no-video --gain 1 '{url}' >/dev/null 2>&1 &")
    return redirect("/")

@app.route("/stop")
def stop():
    run("pkill vlc")
    return redirect("/")

@app.route("/vol/up")
def vol_up():
    run("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+")
    return redirect("/")

@app.route("/vol/down")
def vol_down():
    run("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-")
    return redirect("/")

app.run(host="0.0.0.0", port=8080)
