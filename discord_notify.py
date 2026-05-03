#!/usr/bin/env python3
"""
Discord notification + interaction handler for the painting robot.

Sends pass-complete messages with action buttons.
Listens for button clicks via Discord interactions webhook.

Usage (standalone test):
    python3 discord_notify.py

In server.py, import and call send_pass_complete() / send_job_done().
"""

import json
import threading
import urllib.request
import urllib.error
from typing import Optional

DISCORD_API = "https://discord.com/api/v10"
HEADERS_BASE = {
    "Content-Type": "application/json",
    "User-Agent": "DiscordBot (https://modologystudios.com, 1.0)",
}

_token = ""
_channel_id = ""
_on_next_pass = None   # callback() → advance to next pass
_on_stop_job  = None   # callback() → stop job


def configure(token: str, channel_id: str, on_next_pass=None, on_stop_job=None):
    global _token, _channel_id, _on_next_pass, _on_stop_job
    _token = token
    _channel_id = channel_id
    _on_next_pass = on_next_pass
    _on_stop_job = on_stop_job


def _headers():
    return {**HEADERS_BASE, "Authorization": f"Bot {_token}"}


def _post(path: str, payload: dict) -> Optional[dict]:
    req = urllib.request.Request(
        f"{DISCORD_API}{path}",
        data=json.dumps(payload).encode(),
        headers=_headers(),
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req, timeout=8)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"[discord] HTTP {e.code}: {e.read().decode()}")
    except Exception as e:
        print(f"[discord] error: {e}")
    return None


def send_pass_complete(pass_num: int, total: int, next_color: str, next_name: str) -> Optional[str]:
    """Send a pass-complete message with Ready / Stop buttons. Returns message ID."""
    payload = {
        "content": (
            f"**Pass {pass_num}/{total} complete** — swap pen\n"
            f"Load: **{next_color}** ({next_name})\n"
            f"Tap **Ready** when the pen is swapped. Machine will re-home and start automatically."
        ),
        "components": [{
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 3,          # green
                    "label": "Ready — start next pass",
                    "custom_id": "robot_next_pass",
                    "emoji": {"name": "✅"},
                },
                {
                    "type": 2,
                    "style": 4,          # red
                    "label": "Stop job",
                    "custom_id": "robot_stop_job",
                    "emoji": {"name": "🛑"},
                },
            ],
        }],
    }
    result = _post(f"/channels/{_channel_id}/messages", payload)
    return result.get("id") if result else None


def send_job_done(total: int) -> None:
    """Send a job-complete notification."""
    payload = {
        "content": (
            f"**Painting complete** — all {total} pass{'es' if total != 1 else ''} finished.\n"
            f"Your painting is ready. 🎨"
        ),
    }
    _post(f"/channels/{_channel_id}/messages", payload)


def send_simple(message: str) -> None:
    """Send a plain text message."""
    _post(f"/channels/{_channel_id}/messages", {"content": message})


def handle_interaction(interaction: dict) -> dict:
    """
    Handle a Discord interaction (button click).
    Call this from your interactions endpoint.
    Returns the response payload to send back to Discord.
    """
    custom_id = (
        interaction.get("data", {}).get("custom_id", "")
    )
    if custom_id == "robot_next_pass":
        if _on_next_pass:
            threading.Thread(target=_on_next_pass, daemon=True).start()
        return {
            "type": 4,
            "data": {"content": "Starting next pass — re-homing now.", "flags": 64},
        }
    elif custom_id == "robot_stop_job":
        if _on_stop_job:
            threading.Thread(target=_on_stop_job, daemon=True).start()
        return {
            "type": 4,
            "data": {"content": "Job stopped.", "flags": 64},
        }
    return {"type": 1}  # pong


if __name__ == "__main__":
    import os
    tok = os.environ.get("DISCORD_BOT_TOKEN", "")
    ch  = os.environ.get("DISCORD_CHANNEL", "")
    configure(tok, ch)
    send_simple("Painting robot online — Discord notifications active.")
    print("Test message sent.")
