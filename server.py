#!/usr/bin/env python3
"""
Painting Robot — Web Control Server
Modology Studios

Usage on Pi:
    python3 server.py                        # auto-finds /dev/ttyACM0
    python3 server.py --port /dev/ttyUSB0    # explicit port
    python3 server.py --host 0.0.0.0         # accessible on LAN

Then open http://raspberrypi.local:5000 (or the Pi's IP) in any browser.
"""

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional

import serial
import serial.tools.list_ports
from flask import Flask, jsonify, render_template, request, Response, stream_with_context
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ── Notifications (Discord) ───────────────────────────────────────────────────

import discord_notify as _discord


# ── Multi-pass job state ──────────────────────────────────────────────────────

_job_lock = threading.Lock()
_job_passes: list[dict] = []   # [{"name": str, "gcode": str, "color": str}, ...]
_job_current: int = -1         # index of active pass, -1 = no job loaded
_job_status: str = "idle"      # idle | ready | running | awaiting_swap | done


def _job_title() -> str:
    if not _job_passes:
        return ""
    p = _job_passes[_job_current] if 0 <= _job_current < len(_job_passes) else {}
    return p.get("name", f"Pass {_job_current + 1}")


# ── Serial state ──────────────────────────────────────────────────────────────

_serial_lock = threading.Lock()
_serial: Optional[serial.Serial] = None
_connected_port = ""

# ── SSE fan-out ───────────────────────────────────────────────────────────────

_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


def push_event(event: str, data: str):
    msg = f"event: {event}\ndata: {data}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


# ── GRBL streaming ────────────────────────────────────────────────────────────

_stream_thread: Optional[threading.Thread] = None
_stream_stop = threading.Event()


def grbl_stream(lines: list[str]):
    global _serial
    total = sum(1 for l in lines if l.strip() and not l.strip().startswith(";"))
    sent = 0
    push_event("progress", f"0/{total}")

    for raw in lines:
        if _stream_stop.is_set():
            push_event("status", "stopped")
            return

        line = raw.strip()
        if not line or line.startswith(";"):
            continue

        with _serial_lock:
            if _serial is None or not _serial.is_open:
                push_event("error", "Serial disconnected during stream")
                return
            _serial.write((line + "\n").encode())
            _serial.flush()

        # wait for ok or error
        got_ok = False
        deadline = time.time() + 30
        while time.time() < deadline:
            if _stream_stop.is_set():
                push_event("status", "stopped")
                return
            with _serial_lock:
                if _serial and _serial.in_waiting:
                    resp = _serial.readline().decode(errors="replace").strip()
                else:
                    resp = None
            if resp is None:
                time.sleep(0.005)
                continue
            if resp.startswith("ok"):
                got_ok = True
                break
            if resp.startswith("error"):
                push_event("error", f"GRBL error on line {sent+1}: {resp}")
                return
            # status reports or other — ignore, keep waiting

        if not got_ok:
            push_event("error", f"Timeout waiting for GRBL ack on line {sent+1}")
            return

        sent += 1
        push_event("progress", f"{sent}/{total}")

    push_event("status", "done")
    push_event("progress", f"{total}/{total}")

    with _job_lock:
        global _job_current, _job_status
        if _job_current >= 0 and _job_passes:
            next_idx = _job_current + 1
            if next_idx < len(_job_passes):
                next_pass = _job_passes[next_idx]
                _job_status = "awaiting_swap"
                push_event("job", json.dumps({
                    "status": "awaiting_swap",
                    "completed": _job_current + 1,
                    "total": len(_job_passes),
                    "next_name": next_pass["name"],
                    "next_color": next_pass.get("color", ""),
                }))
                _discord.send_pass_complete(
                    pass_num=_job_current + 1,
                    total=len(_job_passes),
                    next_color=next_pass.get("color", next_pass["name"]),
                    next_name=next_pass["name"],
                )
            else:
                _job_status = "done"
                push_event("job", json.dumps({"status": "done", "total": len(_job_passes)}))
                _discord.send_job_done(len(_job_passes))
        else:
            _discord.send_simple("Painting robot: pass complete.")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ports")
def ports():
    found = [p.device for p in serial.tools.list_ports.comports()]
    return jsonify(ports=found)


@app.route("/connect", methods=["POST"])
def connect():
    global _serial, _connected_port
    data = request.get_json(force=True)
    port = data.get("port", "").strip()
    baud = int(data.get("baud", 115200))

    if not port:
        return jsonify(ok=False, error="No port specified"), 400

    with _serial_lock:
        if _serial and _serial.is_open:
            _serial.close()

    try:
        new_ser = serial.Serial(port, baud, timeout=2)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400

    time.sleep(2)       # wait for GRBL boot — outside lock so other requests don't block
    new_ser.flushInput()

    with _serial_lock:
        _serial = new_ser
        _connected_port = port

    push_event("status", "connected")
    return jsonify(ok=True, port=port)


@app.route("/disconnect", methods=["POST"])
def disconnect():
    global _serial, _connected_port
    with _serial_lock:
        if _serial and _serial.is_open:
            _serial.close()
        _serial = None
        _connected_port = ""
    push_event("status", "disconnected")
    return jsonify(ok=True)


@app.route("/status")
def status():
    with _serial_lock:
        connected = _serial is not None and _serial.is_open
    streaming = _stream_thread is not None and _stream_thread.is_alive()
    return jsonify(connected=connected, port=_connected_port, streaming=streaming)


@app.route("/generate", methods=["POST"])
def generate():
    if "image" not in request.files:
        return jsonify(ok=False, error="No image uploaded"), 400

    f = request.files["image"]
    if not f.filename:
        return jsonify(ok=False, error="Uploaded file has no name"), 400

    img_path = UPLOAD_DIR / secure_filename(f.filename)
    f.save(img_path)

    mode         = request.form.get("mode", "edges")
    canvas_w     = request.form.get("canvas_w", "1220")
    canvas_h     = request.form.get("canvas_h", "1524")
    feed_draw    = request.form.get("feed_draw", "3000")
    feed_travel  = request.form.get("feed_travel", "8000")
    backlash     = request.form.get("backlash", "0.4")
    canny_low    = request.form.get("canny_low", "50")
    canny_high   = request.form.get("canny_high", "150")
    blur         = request.form.get("blur", "3")
    dot_spacing  = request.form.get("dot_spacing", "4.0")
    dot_radius   = request.form.get("dot_radius", "1.2")
    line_spacing = request.form.get("line_spacing", "1.5")
    threshold    = request.form.get("threshold", "128")
    invert       = request.form.get("invert", "false").lower() == "true"

    out_path = UPLOAD_DIR / (img_path.stem + f"_{mode}.gcode")

    cmd = [
        sys.executable,
        str(Path(__file__).parent / "toolpath.py"),
        mode, str(img_path),
        "-o", str(out_path),
        "--canvas-w",    canvas_w,
        "--canvas-h",    canvas_h,
        "--feed-draw",   feed_draw,
        "--feed-travel", feed_travel,
        "--backlash",    backlash,
        "--canny-low",   canny_low,
        "--canny-high",  canny_high,
        "--blur",        blur,
        "--dot-spacing", dot_spacing,
        "--dot-radius",  dot_radius,
        "--line-spacing", line_spacing,
        "--threshold",   threshold,
    ]
    if invert:
        cmd.append("--invert")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return jsonify(ok=False, error="Toolpath generation timed out"), 500

    if result.returncode != 0:
        return jsonify(ok=False, error=result.stderr.strip() or "toolpath.py failed"), 500

    if not out_path.exists():
        return jsonify(ok=False, error="toolpath.py exited successfully but wrote no .gcode file"), 500

    lines = out_path.read_text().splitlines()
    gcode_lines = [l for l in lines if l.strip() and not l.strip().startswith(";")]

    return jsonify(
        ok=True,
        gcode_path=str(out_path),
        line_count=len(gcode_lines),
        stdout=result.stdout.strip(),
    )


@app.route("/send", methods=["POST"])
def send():
    global _stream_thread
    data = request.get_json(force=True)
    gcode_path = data.get("gcode_path", "")

    if not gcode_path or not Path(gcode_path).exists():
        return jsonify(ok=False, error="G-code file not found"), 400

    with _serial_lock:
        if _serial is None or not _serial.is_open:
            return jsonify(ok=False, error="Not connected"), 400

    if _stream_thread and _stream_thread.is_alive():
        return jsonify(ok=False, error="Already streaming"), 400

    lines = Path(gcode_path).read_text().splitlines()
    _stream_stop.clear()
    _stream_thread = threading.Thread(target=grbl_stream, args=(lines,), daemon=True)
    _stream_thread.start()
    return jsonify(ok=True)


@app.route("/stop", methods=["POST"])
def stop():
    _stream_stop.set()
    with _serial_lock:
        if _serial and _serial.is_open:
            _serial.write(b"!")   # GRBL feed hold
            _serial.flush()
    return jsonify(ok=True)


@app.route("/home", methods=["POST"])
def home():
    with _serial_lock:
        if _serial is None or not _serial.is_open:
            return jsonify(ok=False, error="Not connected"), 400
        _serial.write(b"$H\n")
        _serial.flush()
    push_event("status", "homing")
    return jsonify(ok=True)


@app.route("/jog", methods=["POST"])
def jog():
    data = request.get_json(force=True)
    axis = data.get("axis", "X").upper()
    dist = float(data.get("dist", 10))
    feed = int(data.get("feed", 3000))

    cmd = f"$J=G91 G21 {axis}{dist:.1f} F{feed}\n"
    with _serial_lock:
        if _serial is None or not _serial.is_open:
            return jsonify(ok=False, error="Not connected"), 400
        _serial.write(cmd.encode())
        _serial.flush()
    return jsonify(ok=True)


@app.route("/cmd", methods=["POST"])
def cmd():
    data = request.get_json(force=True)
    raw = data.get("cmd", "").strip()
    if not raw:
        return jsonify(ok=False, error="Empty command"), 400

    with _serial_lock:
        if _serial is None or not _serial.is_open:
            return jsonify(ok=False, error="Not connected"), 400
        _serial.write((raw + "\n").encode())
        _serial.flush()
        time.sleep(0.1)
        resp = ""
        while _serial.in_waiting:
            resp += _serial.readline().decode(errors="replace")

    return jsonify(ok=True, response=resp.strip())


@app.route("/events")
def events():
    q: queue.Queue = queue.Queue(maxsize=200)
    with _sse_lock:
        _sse_clients.append(q)

    @stream_with_context
    def generate():
        yield "data: connected\n\n"
        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield msg
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Multi-pass job routes ─────────────────────────────────────────────────────

@app.route("/job/load", methods=["POST"])
def job_load():
    """Load a multi-pass job.

    POST body (JSON):
      {"passes": [{"name": "Background hatch", "gcode": "uploads/bg.gcode", "color": "Raw Sienna"}, ...]}

    Or load from a .json file:
      {"file": "uploads/my_painting.json"}
    """
    global _job_passes, _job_current, _job_status
    data = request.get_json(force=True)

    if "file" in data:
        p = Path(data["file"])
        if not p.exists():
            return jsonify(ok=False, error=f"Job file not found: {p}"), 400
        try:
            data = json.loads(p.read_text())
        except Exception as e:
            return jsonify(ok=False, error=f"Invalid JSON: {e}"), 400

    passes = data.get("passes", [])
    if not passes:
        return jsonify(ok=False, error="Job must have at least one pass"), 400

    for i, p in enumerate(passes):
        if "gcode" not in p:
            return jsonify(ok=False, error=f"Pass {i} missing 'gcode' field"), 400
        if not Path(p["gcode"]).exists():
            return jsonify(ok=False, error=f"G-code not found: {p['gcode']}"), 400

    with _job_lock:
        _job_passes = passes
        _job_current = 0
        _job_status = "ready"

    push_event("job", json.dumps({
        "status": "ready",
        "total": len(passes),
        "current": 0,
        "name": passes[0]["name"],
        "color": passes[0].get("color", ""),
    }))
    return jsonify(ok=True, total=len(passes), first=passes[0]["name"])


@app.route("/job/status")
def job_status():
    with _job_lock:
        p = _job_passes[_job_current] if 0 <= _job_current < len(_job_passes) else {}
        return jsonify(
            status=_job_status,
            current=_job_current,
            total=len(_job_passes),
            pass_name=p.get("name", ""),
            pass_color=p.get("color", ""),
        )


@app.route("/job/start", methods=["POST"])
def job_start():
    """Start the first pass of the loaded job."""
    global _stream_thread, _job_status
    with _job_lock:
        if _job_status != "ready":
            return jsonify(ok=False, error=f"Job not ready (status: {_job_status})"), 400
        gcode_path = _job_passes[_job_current]["gcode"]

    with _serial_lock:
        if _serial is None or not _serial.is_open:
            return jsonify(ok=False, error="Not connected"), 400

    if _stream_thread and _stream_thread.is_alive():
        return jsonify(ok=False, error="Already streaming"), 400

    lines = Path(gcode_path).read_text().splitlines()
    _stream_stop.clear()
    with _job_lock:
        _job_status = "running"
    _stream_thread = threading.Thread(target=grbl_stream, args=(lines,), daemon=True)
    _stream_thread.start()
    return jsonify(ok=True, pass_name=_job_passes[_job_current]["name"])


@app.route("/job/next", methods=["POST"])
def job_next():
    """Confirm pen swap and start the next pass."""
    global _stream_thread, _job_current, _job_status
    with _job_lock:
        if _job_status != "awaiting_swap":
            return jsonify(ok=False, error=f"Not waiting for swap (status: {_job_status})"), 400
        _job_current += 1
        gcode_path = _job_passes[_job_current]["gcode"]
        _job_status = "running"
        pass_name = _job_passes[_job_current]["name"]

    with _serial_lock:
        if _serial is None or not _serial.is_open:
            return jsonify(ok=False, error="Not connected"), 400

    if _stream_thread and _stream_thread.is_alive():
        return jsonify(ok=False, error="Already streaming"), 400

    # Home before next pass so registration is exact
    with _serial_lock:
        _serial.write(b"$H\n")
        _serial.flush()
    time.sleep(3)   # let homing cycle complete

    lines = Path(gcode_path).read_text().splitlines()
    _stream_stop.clear()
    _stream_thread = threading.Thread(target=grbl_stream, args=(lines,), daemon=True)
    _stream_thread.start()
    push_event("job", json.dumps({
        "status": "running",
        "current": _job_current,
        "total": len(_job_passes),
        "name": pass_name,
    }))
    return jsonify(ok=True, pass_name=pass_name)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Painting Robot Web Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default 0.0.0.0)")
    parser.add_argument("--port-http", type=int, default=5000, help="HTTP port (default 5000)")
    parser.add_argument("--port", default="", help="Auto-connect to this serial port on startup")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--discord-token", default=os.environ.get("DISCORD_BOT_TOKEN", ""),
                        help="Discord bot token (or set DISCORD_BOT_TOKEN env var)")
    parser.add_argument("--discord-channel", default="1500616786033381530",
                        help="Discord channel ID for notifications")
    args = parser.parse_args()

    def _next_pass_callback():
        with app.test_request_context():
            job_next()

    def _stop_job_callback():
        _stream_stop.set()

    _discord.configure(
        token=args.discord_token,
        channel_id=args.discord_channel,
        on_next_pass=_next_pass_callback,
        on_stop_job=_stop_job_callback,
    )
    print(f"Discord notifications → channel {args.discord_channel}")

    if args.port:
        try:
            new_ser = serial.Serial(args.port, args.baud, timeout=2)
            time.sleep(2)
            new_ser.flushInput()
            with _serial_lock:
                _serial = new_ser
                _connected_port = args.port
            print(f"Auto-connected to {args.port}")
        except Exception as e:
            print(f"Auto-connect to {args.port} failed: {e}")

    print(f"Painting Robot server at http://{args.host}:{args.port_http}")
    app.run(host=args.host, port=args.port_http, threaded=True)
