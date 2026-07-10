# pi-alarm-clock-radio

A simple Raspberry Pi Flask app for streaming internet radio, playing local audio files, and managing wake-up alarms through Bluetooth speakers.

## Features

- Web interface served on `http://<pi-ip>:8080`
- Play preset radio streams via VLC
- Browse and play local music files from `~/music`
- Set alarm times separately for weekdays and weekends
- Choose alarm source: internet radio station or local music file
- Connect to one of two Bluetooth speakers via `bluetoothctl`
- Control volume, mute, and stop playback

## Configuration

The app loads settings from `~/pi-radio/config.json` and creates it if missing.

Default config values:

- `alarm_enabled`: false
- `weekday_time`: `07:00`
- `weekend_time`: `08:00`
- `station`: `kutx`
- `alarm_source`: `station`
- `alarm_file`: `""`
- `last_alarm_date`: `""`
- `speaker_a_name` / `speaker_b_name`
- `speaker_a_mac` / `speaker_b_mac`

### Music directory

Local audio files are discovered under `~/music`.
Supported file extensions: `.mp3`, `.flac`, `.wav`, `.m4a`, `.ogg`.

## Running the app

1. Ensure dependencies are installed:
   - `flask`
   - `vlc`
   - `wpctl`
   - `bluetoothctl`

2. Start the app:

```bash
python3 ~/pi-alarm-clock-radio/app.py
```

3. Open the web UI:

```text
http://<pi-ip>:8080
```

## Web UI actions

- Play radio station buttons
- `Vol -`, `Vol +`, `Mute`, `Stop`
- Connect Bluetooth speaker A or B
- Enable/disable the alarm
- Set weekday/weekend alarm times
- Select `Use Station for Alarm` or choose a local file as the alarm source
- Music library list with `Play` and `Alarm` buttons for each file

## Alarm behavior

- Alarm only triggers once per day when enabled
- Uses weekday or weekend time based on the current day
- Resets `last_alarm_date` whenever alarm settings or source changes
- If `alarm_source` is `file`, the configured local file will play
- Otherwise the configured station is played

## Notes

- The app kills existing VLC instances before starting playback
- Bluetooth speaker connect/disconnect uses `bluetoothctl`
- Volume is read from `wpctl get-volume @DEFAULT_AUDIO_SINK@`
