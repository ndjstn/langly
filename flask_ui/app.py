"""Enhanced Flask UI for Langly harness."""
from __future__ import annotations

import os
import uuid
from urllib.parse import urlparse

import httpx
from flask import Flask, jsonify, render_template, request


APP = Flask(__name__)
HARNESS_URL = os.getenv("LANGLY_HARNESS_URL", "http://localhost:8000/api/v2/harness/run")
API_BASE = os.getenv("LANGLY_API_BASE", "http://localhost:8000")
UPLOAD_DIR = os.getenv("LANGLY_UPLOAD_DIR", "uploads")

THEMES = [
    {"value": "catppuccin", "label": "Catppuccin"},
    {"value": "tokyonight", "label": "Tokyo Night"},
    {"value": "kanagawa", "label": "Kanagawa"},
    {"value": "rose-pine", "label": "Rose Pine"},
    {"value": "nightfox", "label": "Nightfox"},
    {"value": "onedark", "label": "OneDark"},
    {"value": "gruvbox-material", "label": "Gruvbox Material"},
    {"value": "github", "label": "GitHub"},
    {"value": "everforest", "label": "Everforest"},
    {"value": "vscode", "label": "VSCode"},
    {"value": "cyberdream", "label": "Cyberdream"},
    {"value": "onedarkpro", "label": "OneDark Pro"},
    {"value": "material", "label": "Material"},
    {"value": "dracula", "label": "Dracula"},
    {"value": "nord", "label": "Nord"},
    {"value": "oxocarbon", "label": "Oxocarbon"},
    {"value": "solarized-osaka", "label": "Solarized Osaka"},
    {"value": "sonokai", "label": "Sonokai"},
    {"value": "nordic", "label": "Nordic"},
    {"value": "moonfly", "label": "Moonfly"},
]


def _harness_ws_url(harness_url: str) -> str:
    parsed = urlparse(harness_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/v2/ws/deltas"


@APP.get("/")
def index():
    return render_template(
        "index.html",
        harness_ws=_harness_ws_url(HARNESS_URL),
        themes=THEMES,
        default_theme=os.getenv("LANGLY_UI_THEME", "catppuccin"),
    )


@APP.post("/run")
def run_harness():
    payload = request.get_json(force=True) or {}
    payload.setdefault("request_id", str(uuid.uuid4()))
    try:
        resp = httpx.post(HARNESS_URL, json=payload, timeout=600)
        resp.raise_for_status()
        return jsonify(resp.json())
    except httpx.HTTPError as exc:
        return jsonify({"error": str(exc)}), 500


@APP.get("/files/tree")
def files_tree():
    path = request.args.get("path", ".")
    try:
        resp = httpx.get(
            f"{API_BASE}/api/v2/files/tree",
            params={"path": path},
            timeout=15,
        )
        resp.raise_for_status()
        return jsonify(resp.json())
    except httpx.HTTPError as exc:
        return jsonify({"error": str(exc)}), 500


@APP.get("/files/read")
def files_read():
    path = request.args.get("path", ".")
    try:
        resp = httpx.get(
            f"{API_BASE}/api/v2/files/read",
            params={"path": path},
            timeout=15,
        )
        resp.raise_for_status()
        return jsonify(resp.json())
    except httpx.HTTPError as exc:
        return jsonify({"error": str(exc)}), 500


@APP.post("/upload")
def upload():
    if "file" not in request.files:
        return jsonify({"error": "missing file"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "empty filename"}), 400
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    ext = os.path.splitext(safe_name)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.abspath(os.path.join(UPLOAD_DIR, filename))
    file.save(dest)
    return jsonify({"path": dest})


@APP.get("/health")
def health():
    return {"status": "ok", "harness_url": HARNESS_URL}


@APP.get("/favicon.ico")
def favicon():
    return ("", 204)


def create_app() -> Flask:
    return APP
