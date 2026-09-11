import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory


def load_local_env() -> None:
    """Load .env only for local development; hosting environment values take priority."""
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()
app = Flask(__name__, static_folder="public")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

SMARTFLO_URL = "https://api-smartflo.tatateleservices.com/v1/click_to_call"
PHONE_PATTERN = re.compile(r"^[6-9]\d{9}$")
REQUESTS = defaultdict(deque)
RATE_LIMIT = 3
RATE_WINDOW_SECONDS = 600


def normalise_indian_mobile(value: object) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("0091"):
        digits = digits[4:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return f"91{digits}" if PHONE_PATTERN.fullmatch(digits) else None


def under_rate_limit(ip: str) -> bool:
    now = time.monotonic()
    entries = REQUESTS[ip]
    while entries and now - entries[0] > RATE_WINDOW_SECONDS:
        entries.popleft()
    if len(entries) >= RATE_LIMIT:
        return False
    entries.append(now)
    return True


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/app.js")
def javascript():
    return send_from_directory(app.static_folder, "app.js")


@app.get("/styles.css")
def stylesheet():
    return send_from_directory(app.static_folder, "styles.css")


@app.post("/api/request-callback")
def request_callback():
    payload = request.get_json(silent=True) or {}
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()

    if payload.get("website"):
        return jsonify(ok=True, message="Thank you. We will call you shortly.")
    if not under_rate_limit(ip):
        return jsonify(ok=False, message="Please wait a few minutes before requesting another callback."), 429

    name = str(payload.get("name", "")).strip()
    phone = normalise_indian_mobile(payload.get("phone"))
    if not name or len(name) > 80:
        return jsonify(ok=False, message="Please enter your name."), 400
    if phone is None:
        return jsonify(ok=False, message="Enter a valid 10-digit Indian mobile number."), 400

    token = os.getenv("SMARTFLO_API_TOKEN")
    agent_number = os.getenv("SMARTFLO_AGENT_NUMBER")
    caller_id = os.getenv("SMARTFLO_CALLER_ID")
    if not token or not agent_number:
        app.logger.error("Smartflo is not configured: missing token or agent number")
        return jsonify(ok=False, message="Callback service is temporarily unavailable. Please try again soon."), 503

    smartflo_body = {
        "agent_number": agent_number,
        "destination_number": phone,
        "async": 1,
        "call_timeout": int(os.getenv("SMARTFLO_CALL_TIMEOUT", "300")),
        "custom_identifier": {"lead_name": re.sub(r"[^A-Za-z0-9 ]", "", name)[:60]},
    }
    if caller_id:
        smartflo_body["caller_id"] = caller_id

    api_request = urllib.request.Request(
        SMARTFLO_URL,
        data=json.dumps(smartflo_body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(api_request, timeout=15) as response:
            response_data = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        app.logger.warning("Smartflo rejected callback request (%s): %s", error.code, error.read().decode("utf-8", "replace")[:500])
        return jsonify(
            ok=False,
            message=f"Smartflo could not accept the callback request (HTTP {error.code}). Check the Smartflo token, agent number, and caller ID.",
        ), 502
    except urllib.error.URLError as error:
        app.logger.exception("Smartflo callback request failed: %s", error)
        return jsonify(ok=False, message="We could not start the callback. Please try again."), 502
    except TimeoutError:
        app.logger.exception("Smartflo callback request timed out")
        return jsonify(ok=False, message="Smartflo did not respond before the request timed out."), 504
    except json.JSONDecodeError:
        app.logger.exception("Smartflo returned an invalid response")
        return jsonify(ok=False, message="Smartflo returned an invalid API response."), 502

    ref_id = response_data.get("ref_id") or response_data.get("data", {}).get("ref_id")
    app.logger.info("Smartflo callback accepted for lead %s; ref_id=%s", name, ref_id)
    return jsonify(ok=True, message="Thank you. A sales specialist will call you shortly.", ref_id=ref_id)


@app.get("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
