import os
import io
import csv
import json
import uuid
import time
import math
import base64
import sqlite3
import logging
from functools import lru_cache
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime, timezone

import gradio as gr
import requests
from PIL import Image, ImageDraw, ImageFile, UnidentifiedImageError
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM

# ============================================================
# Single-file Field Triage App
# - Multi-LLM support
# - Multi-camera connectivity
# - Geotag + overlay + SQLite + CSV + optional IPFS
# Honest positioning:
# - visual triage / candidate region detection
# - demo / pilot artifact
# - not confirmed botanical or forensic identification
# ============================================================

# ---------------------------
# Configuration
# ---------------------------
APP_TITLE = os.getenv("APP_TITLE", "Field Triage App")
TARGET_NAME = os.getenv("TARGET_NAME", "bud")
MODEL_ID = os.getenv("MODEL_ID", "google/siglip-base-patch16-224")
HF_LLM_MODEL_ID = os.getenv("HF_LLM_MODEL_ID", "distilgpt2")
DEVICE = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")

PORT = int(os.getenv("PORT", "7860"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

MAX_IMAGE_SIDE = int(os.getenv("MAX_IMAGE_SIDE", "1280"))
MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", "25000000"))
TILE_SIZE = int(os.getenv("TILE_SIZE", "224"))
TILE_STRIDE = int(os.getenv("TILE_STRIDE", "160"))
TOP_K_TILES = int(os.getenv("TOP_K_TILES", "8"))
MAX_TILES_TO_SCORE = int(os.getenv("MAX_TILES_TO_SCORE", "120"))

CLASSIFY_THRESHOLD_LIKELY = float(os.getenv("CLASSIFY_THRESHOLD_LIKELY", "0.72"))
CLASSIFY_THRESHOLD_REVIEW = float(os.getenv("CLASSIFY_THRESHOLD_REVIEW", "0.50"))
REGION_THRESHOLD = float(os.getenv("REGION_THRESHOLD", "0.65"))

HF_MAX_NEW_TOKENS = int(os.getenv("HF_MAX_NEW_TOKENS", "120"))
HF_TEMPERATURE = float(os.getenv("HF_TEMPERATURE", "0.6"))

DB_PATH = os.getenv("DB_PATH", "observations.db")
EXPORT_DIR = os.getenv("EXPORT_DIR", "exports")

PINATA_JWT = os.getenv("PINATA_JWT", "")
PINATA_UPLOAD_URL = os.getenv("PINATA_UPLOAD_URL", "https://uploads.pinata.cloud/v3/files")
PINATA_GATEWAY = os.getenv("PINATA_GATEWAY", "https://gateway.pinata.cloud/ipfs")
PINATA_TIMEOUT = int(os.getenv("PINATA_TIMEOUT", "90"))

# OpenAI-compatible
OPENAI_COMPAT_BASE_URL = os.getenv("OPENAI_COMPAT_BASE_URL", "https://api.groq.com/openai/v1")
OPENAI_COMPAT_API_KEY = os.getenv("OPENAI_COMPAT_API_KEY", "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")
OPENAI_COMPAT_MODEL = os.getenv("OPENAI_COMPAT_MODEL", "llama3-70b-8192")

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

os.makedirs(EXPORT_DIR, exist_ok=True)
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
ImageFile.LOAD_TRUNCATED_IMAGES = True

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("field_triage_app")

# ---------------------------
# Detection labels
# ---------------------------
POSITIVE_LABELS = [
    "a cannabis bud on the ground",
    "a marijuana bud on pavement",
    "a small nug of cannabis",
    "a dropped weed bud on sidewalk",
    "cannabis flower on the street",
]

NEGATIVE_LABELS = [
    "clean pavement",
    "clean sidewalk",
    "an empty street",
    "a clean floor",
    "ordinary debris",
]

ALL_LABELS = POSITIVE_LABELS + NEGATIVE_LABELS

# ---------------------------
# Validation
# ---------------------------
def validate_config() -> List[str]:
    issues = []
    if TILE_SIZE <= 0 or TILE_STRIDE <= 0:
        issues.append("TILE_SIZE and TILE_STRIDE must be positive.")
    if TOP_K_TILES <= 0:
        issues.append("TOP_K_TILES must be positive.")
    if MAX_IMAGE_SIDE < 224:
        issues.append("MAX_IMAGE_SIDE should be >= 224.")
    if MAX_TILES_TO_SCORE <= 0:
        issues.append("MAX_TILES_TO_SCORE must be positive.")
    return issues


# ---------------------------
# Database
# ---------------------------
OBSERVATION_COLUMNS = {
    "id": "TEXT PRIMARY KEY",
    "created_at": "TEXT NOT NULL",
    "filename": "TEXT",
    "source_type": "TEXT",
    "camera_url": "TEXT",
    "verdict": "TEXT",
    "overall_score": "REAL",
    "whole_image_score": "REAL",
    "best_tile_score": "REAL",
    "candidate_region_count": "INTEGER",
    "scene_description": "TEXT",
    "report_text": "TEXT",
    "llm_backend": "TEXT",
    "image_width": "INTEGER",
    "image_height": "INTEGER",
    "lat": "REAL",
    "lon": "REAL",
    "accuracy": "REAL",
    "location_source": "TEXT",
    "original_cid": "TEXT",
    "original_ipfs_url": "TEXT",
    "overlay_cid": "TEXT",
    "overlay_ipfs_url": "TEXT",
    "summary_json": "TEXT",
}

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            filename TEXT,
            source_type TEXT,
            camera_url TEXT,
            verdict TEXT,
            overall_score REAL,
            whole_image_score REAL,
            best_tile_score REAL,
            candidate_region_count INTEGER,
            scene_description TEXT,
            report_text TEXT,
            llm_backend TEXT,
            image_width INTEGER,
            image_height INTEGER,
            lat REAL,
            lon REAL,
            accuracy REAL,
            location_source TEXT,
            original_cid TEXT,
            original_ipfs_url TEXT,
            overlay_cid TEXT,
            overlay_ipfs_url TEXT,
            summary_json TEXT
        )
        """
    )

    cur.execute("PRAGMA table_info(observations)")
    existing = {row[1] for row in cur.fetchall()}
    for col, col_type in OBSERVATION_COLUMNS.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE observations ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()

def save_observation(record: Dict[str, Any]) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO observations (
            id, created_at, filename, source_type, camera_url,
            verdict, overall_score, whole_image_score, best_tile_score,
            candidate_region_count, scene_description, report_text, llm_backend,
            image_width, image_height, lat, lon, accuracy, location_source,
            original_cid, original_ipfs_url, overlay_cid, overlay_ipfs_url,
            summary_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["id"],
            record["created_at"],
            record.get("filename"),
            record.get("source_type"),
            record.get("camera_url"),
            record.get("verdict"),
            record.get("overall_score"),
            record.get("whole_image_score"),
            record.get("best_tile_score"),
            record.get("candidate_region_count"),
            record.get("scene_description"),
            record.get("report_text"),
            record.get("llm_backend"),
            record.get("image_width"),
            record.get("image_height"),
            record.get("lat"),
            record.get("lon"),
            record.get("accuracy"),
            record.get("location_source"),
            record.get("original_cid"),
            record.get("original_ipfs_url"),
            record.get("overlay_cid"),
            record.get("overlay_ipfs_url"),
            json.dumps(record.get("summary_json", {}), ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()

def list_recent_observations(limit: int = 25) -> List[List[Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT created_at, source_type, verdict, overall_score, candidate_region_count,
               lat, lon, accuracy, llm_backend, original_ipfs_url, overlay_ipfs_url
        FROM observations
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return [list(row) for row in rows]

def export_observations_csv() -> str:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM observations ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(EXPORT_DIR, f"observations_{ts}.csv")

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if rows:
            writer.writerow(rows[0].keys())
            for row in rows:
                writer.writerow(list(row))
        else:
            writer.writerow(list(OBSERVATION_COLUMNS.keys()))
    return path


# ---------------------------
# Utility
# ---------------------------
def parse_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None

def pil_to_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()

def validate_and_prepare_image(image: Image.Image) -> Image.Image:
    if image is None:
        raise ValueError("No image provided.")
    image = image.convert("RGB")
    w, h = image.size
    if w <= 0 or h <= 0:
        raise ValueError("Invalid image dimensions.")
    if w * h > MAX_IMAGE_PIXELS:
        raise ValueError("Image is too large.")
    return image

def resize_for_inference(image: Image.Image, max_side: int = MAX_IMAGE_SIDE) -> Image.Image:
    image = validate_and_prepare_image(image)
    w, h = image.size
    if max(w, h) <= max_side:
        return image
    scale = max_side / max(w, h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)


# ---------------------------
# Model loading
# ---------------------------
def _device_arg() -> int:
    return 0 if DEVICE.startswith("cuda") else -1

@lru_cache(maxsize=1)
def get_classifier():
    logger.info("Loading classifier: %s", MODEL_ID)
    return pipeline(
        task="zero-shot-image-classification",
        model=MODEL_ID,
        device=_device_arg(),
    )

@lru_cache(maxsize=1)
def get_hf_llm():
    logger.info("Loading HF LLM: %s", HF_LLM_MODEL_ID)
    tokenizer = AutoTokenizer.from_pretrained(HF_LLM_MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(HF_LLM_MODEL_ID)
    if DEVICE != "cpu":
        model.to(DEVICE)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer, model


# ---------------------------
# Image scoring
# ---------------------------
def classify_image_patch(image: Image.Image) -> Dict[str, Any]:
    classifier = get_classifier()
    results = classifier(image, candidate_labels=ALL_LABELS)
    label_scores = dict(zip(results["labels"], results["scores"]))

    positive = max((label_scores.get(lbl, 0.0) for lbl in POSITIVE_LABELS), default=0.0)
    negative = max((label_scores.get(lbl, 0.0) for lbl in NEGATIVE_LABELS), default=0.0)
    denom = positive + negative + 1e-9

    return {
        "target_score": float(positive / denom),
        "clean_score": float(negative / denom),
        "raw": [
            {"label": k, "score": float(v)}
            for k, v in sorted(label_scores.items(), key=lambda x: x[1], reverse=True)
        ],
    }

def sliding_windows(width: int, height: int, tile: int, stride: int) -> List[Tuple[int, int, int, int]]:
    xs = list(range(0, max(width - tile, 0) + 1, stride))
    ys = list(range(0, max(height - tile, 0) + 1, stride))
    if not xs:
        xs = [0]
    if not ys:
        ys = [0]
    if xs[-1] != max(width - tile, 0):
        xs.append(max(width - tile, 0))
    if ys[-1] != max(height - tile, 0):
        ys.append(max(height - tile, 0))

    boxes = []
    for y in ys:
        for x in xs:
            boxes.append((x, y, min(x + tile, width), min(y + tile, height)))
    return boxes

def tile_scan(image: Image.Image, tile_size: int = TILE_SIZE, stride: int = TILE_STRIDE) -> List[Dict[str, Any]]:
    width, height = image.size
    boxes = sliding_windows(width, height, tile_size, stride)
    if len(boxes) > MAX_TILES_TO_SCORE:
        step = max(1, math.ceil(len(boxes) / MAX_TILES_TO_SCORE))
        boxes = boxes[::step][:MAX_TILES_TO_SCORE]

    scored = []
    for box in boxes:
        patch = image.crop(box)
        res = classify_image_patch(patch)
        scored.append({
            "box": box,
            "target_score": res["target_score"],
            "clean_score": res["clean_score"],
            "top_labels": res["raw"][:3],
        })
    scored.sort(key=lambda x: x["target_score"], reverse=True)
    return scored

def draw_overlay(image: Image.Image, top_tiles: List[Dict[str, Any]]) -> Image.Image:
    out = image.copy()
    draw = ImageDraw.Draw(out, "RGBA")
    for idx, tile in enumerate(top_tiles, start=1):
        x1, y1, x2, y2 = tile["box"]
        score = float(tile["target_score"])
        alpha = int(60 + min(score, 1.0) * 120)
        draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0, 220), width=4)
        draw.rectangle([x1, y1, x2, y2], fill=(255, 0, 0, alpha))
        draw.text((x1 + 6, y1 + 6), f"#{idx} {score:.2f}", fill=(255, 255, 255, 255))
    return out

def summarize_tiles(top_tiles: List[Dict[str, Any]]) -> List[List[Any]]:
    rows = []
    for idx, tile in enumerate(top_tiles, start=1):
        rows.append([
            idx,
            round(tile["target_score"], 4),
            round(tile["clean_score"], 4),
            str(list(tile["box"])),
            str(tile["top_labels"]),
        ])
    return rows


# ---------------------------
# Camera connectivity
# ---------------------------
def fetch_image_from_camera_url(camera_url: str, timeout_sec: int = 15) -> Image.Image:
    if not camera_url.strip():
        raise ValueError("Camera URL is empty.")

    headers = {
        "User-Agent": "field-triage-app/1.0"
    }
    resp = requests.get(camera_url, headers=headers, timeout=timeout_sec)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "").lower()
    raw = resp.content

    if "image/" not in content_type and not raw:
        raise ValueError("Camera endpoint did not return image bytes.")

    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        return img
    except UnidentifiedImageError as e:
        raise ValueError(f"Camera URL did not return a decodable image: {e}")

def load_preferred_image(uploaded_image: Optional[Image.Image], camera_url: str, source_mode: str) -> Tuple[Image.Image, str, Optional[str]]:
    """
    Returns: image, source_type, camera_url_used
    """
    if source_mode == "Upload / Webcam":
        if uploaded_image is None:
            raise ValueError("No uploaded/webcam image provided.")
        return uploaded_image, "upload_or_webcam", None

    if source_mode == "Network Camera URL":
        img = fetch_image_from_camera_url(camera_url)
        return img, "network_camera_url", camera_url

    # fallback
    if uploaded_image is not None:
        return uploaded_image, "upload_or_webcam", None
    if camera_url.strip():
        img = fetch_image_from_camera_url(camera_url)
        return img, "network_camera_url", camera_url

    raise ValueError("No image source available.")


# ---------------------------
# LLM backends
# ---------------------------
def build_structured_prompt(
    verdict: str,
    overall_score: float,
    candidate_region_count: int,
    scene_desc: str,
    target_name: str,
) -> str:
    return (
        f"Scene: {scene_desc}\n"
        f"Target: {target_name}\n"
        f"Verdict: {verdict}\n"
        f"Confidence score: {overall_score:.2f}\n"
        f"Candidate regions: {candidate_region_count}\n"
        "Write a short, cautious municipal-style field observation note.\n"
        "Make clear that this is visual triage and not confirmed substance identification.\n"
        "Keep it under 120 words.\n"
    )

def generate_template_report(
    verdict: str,
    overall_score: float,
    candidate_region_count: int,
    scene_desc: str,
    target_name: str,
) -> str:
    return (
        "Field observation summary:\n"
        f"- Scene: {scene_desc or 'No scene caption available'}\n"
        f"- Target class: {target_name}\n"
        f"- Visual triage verdict: {verdict}\n"
        f"- Confidence score: {overall_score:.2f}\n"
        f"- Candidate regions: {candidate_region_count}\n"
        "- Note: this result reflects image-based similarity scoring and region triage only.\n"
        "- Recommendation: manual review is recommended before any operational or legal conclusion."
    )

def generate_hf_report(prompt: str) -> str:
    tokenizer, model = get_hf_llm()
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    if DEVICE != "cpu":
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=HF_MAX_NEW_TOKENS,
            temperature=HF_TEMPERATURE,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    out = generated[len(prompt):].strip()
    return out or "Manual review recommended."

def generate_ollama_report(prompt: str) -> str:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", "").strip() or "Manual review recommended."

def generate_openai_compat_report(prompt: str) -> str:
    if not OPENAI_COMPAT_API_KEY:
        raise ValueError("OPENAI_COMPAT_API_KEY is missing.")
    url = f"{OPENAI_COMPAT_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_COMPAT_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_COMPAT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You write short, cautious field-observation notes. Do not overclaim certainty."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 180,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()

def generate_report_with_backend(
    backend: str,
    verdict: str,
    overall_score: float,
    candidate_region_count: int,
    scene_desc: str,
    target_name: str,
) -> str:
    prompt = build_structured_prompt(
        verdict=verdict,
        overall_score=overall_score,
        candidate_region_count=candidate_region_count,
        scene_desc=scene_desc,
        target_name=target_name,
    )

    if backend == "template":
        return generate_template_report(verdict, overall_score, candidate_region_count, scene_desc, target_name)
    if backend == "hf_local":
        return generate_hf_report(prompt)
    if backend == "ollama":
        return generate_ollama_report(prompt)
    if backend == "openai_compat":
        return generate_openai_compat_report(prompt)

    return generate_template_report(verdict, overall_score, candidate_region_count, scene_desc, target_name)


# ---------------------------
# Scene description
# ---------------------------
def generate_scene_description_simple(image: Image.Image, top_labels: List[Dict[str, Any]]) -> str:
    parts = [x["label"] for x in top_labels[:3]]
    if not parts:
        return "Outdoor ground scene."
    return f"Ground-level scene; top visual matches: {', '.join(parts)}."


# ---------------------------
# IPFS / Pinata
# ---------------------------
def upload_to_pinata(image: Image.Image, name: str, keyvalues: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    if not PINATA_JWT:
        return {"error": "PINATA_JWT is missing"}

    image_bytes = pil_to_png_bytes(image)
    files = {"file": (name, image_bytes, "image/png")}
    data: Dict[str, Any] = {"network": "public"}

    if keyvalues:
        try:
            data["keyvalues"] = json.dumps(keyvalues)
        except Exception:
            data["keyvalues"] = "{}"

    headers = {"Authorization": f"Bearer {PINATA_JWT}"}

    try:
        response = requests.post(
            PINATA_UPLOAD_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=PINATA_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()

        cid = payload.get("cid") or payload.get("data", {}).get("cid") or payload.get("IpfsHash")
        ipfs_url = f"{PINATA_GATEWAY.rstrip('/')}/{cid}" if cid else ""
        return {
            "ok": True,
            "cid": cid,
            "ipfs_url": ipfs_url,
            "raw": payload,
        }
    except Exception as e:
        logger.exception("Pinata upload failed")
        return {"error": str(e)}


# ---------------------------
# Map
# ---------------------------
def build_map_html(lat: Optional[float], lon: Optional[float], accuracy: Optional[float], verdict: str, score: float) -> str:
    if lat is None or lon is None:
        return """
        <div style='padding:16px;border:1px solid #ddd;border-radius:12px;background:#fafafa;'>
            <b>Map unavailable.</b><br>
            Grant browser location permission and capture location before running analysis.
        </div>
        """

    acc_val = accuracy if accuracy is not None else 0
    map_id = f"map_{uuid.uuid4().hex}"
    return f"""
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <div id="{map_id}" style="height:360px;width:100%;border-radius:12px;overflow:hidden;"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
      (function() {{
        const container = document.getElementById('{map_id}');
        if (!container || container.dataset.ready === '1') return;
        container.dataset.ready = '1';
        const map = L.map('{map_id}').setView([{lat}, {lon}], 18);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
          maxZoom: 22,
          attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);

        const marker = L.marker([{lat}, {lon}]).addTo(map);
        marker.bindPopup(`<b>Observation</b><br>{verdict}<br>Score: {score:.4f}<br>Lat: {lat:.6f}<br>Lon: {lon:.6f}`);
        if ({acc_val} > 0) {{
          L.circle([{lat}, {lon}], {{ radius: {acc_val}, color: '#2563eb', fillOpacity: 0.12 }}).addTo(map);
        }}
      }})();
    </script>
    """


# ---------------------------
# Recycling / field guide
# ---------------------------
def get_guidance() -> str:
    return f"""
## Field Triage Guidance

- This app performs **visual triage**, not confirmed substance identification.
- Scores reflect similarity to configured labels, not laboratory confirmation.
- Use results as a **screening aid** and maintain manual review for operational decisions.
- Public IPFS uploads are optional and may be difficult to retract once published.
"""

def build_submission_note() -> str:
    return (
        "Pilot/demo artifact: supports image capture, camera URL ingestion, geolocation, visual triage, "
        "structured observation logging, optional IPFS evidence storage, and multi-backend note generation. "
        "Not represented as certified enforcement or forensic identification."
    )


# ---------------------------
# Main analysis
# ---------------------------
def analyze(
    uploaded_image: Optional[Image.Image],
    source_mode: str,
    camera_url: str,
    llm_backend: str,
    generate_report: bool,
    upload_ipfs: bool,
    lat_value: Optional[str],
    lon_value: Optional[str],
    accuracy_value: Optional[str],
):
    start_ts = time.perf_counter()
    try:
        raw_image, source_type, camera_url_used = load_preferred_image(uploaded_image, camera_url, source_mode)
        image = resize_for_inference(raw_image)

        whole = classify_image_patch(image)
        tiles = tile_scan(image)
        top_tiles = tiles[:TOP_K_TILES]

        tile_max = max((t["target_score"] for t in top_tiles), default=0.0)
        overall_score = max(float(whole["target_score"]), float(tile_max))

        if overall_score >= CLASSIFY_THRESHOLD_LIKELY:
            verdict = f"Likely {TARGET_NAME} present"
        elif overall_score >= CLASSIFY_THRESHOLD_REVIEW:
            verdict = f"Possible {TARGET_NAME} / needs review"
        else:
            verdict = f"No strong {TARGET_NAME} signal"

        high_conf_tiles = [t for t in top_tiles if t["target_score"] >= REGION_THRESHOLD]
        candidate_region_count = len(high_conf_tiles)

        scene_description = generate_scene_description_simple(image, whole["raw"])

        report_text = ""
        if generate_report:
            try:
                report_text = generate_report_with_backend(
                    backend=llm_backend,
                    verdict=verdict,
                    overall_score=overall_score,
                    candidate_region_count=candidate_region_count,
                    scene_desc=scene_description,
                    target_name=TARGET_NAME,
                )
            except Exception as e:
                logger.exception("LLM report generation failed")
                report_text = generate_template_report(
                    verdict=verdict,
                    overall_score=overall_score,
                    candidate_region_count=candidate_region_count,
                    scene_desc=scene_description,
                    target_name=TARGET_NAME,
                ) + f"\n\nFallback reason: {e}"

        overlay = draw_overlay(image, [t for t in top_tiles if t["target_score"] >= max(0.45, REGION_THRESHOLD - 0.15)])

        lat = parse_optional_float(lat_value)
        lon = parse_optional_float(lon_value)
        accuracy = parse_optional_float(accuracy_value)
        location_source = "browser" if lat is not None and lon is not None else None

        summary: Dict[str, Any] = {
            "verdict": verdict,
            "overall_score": round(overall_score, 4),
            "whole_image_score": round(float(whole["target_score"]), 4),
            "best_tile_score": round(float(tile_max), 4),
            "candidate_region_count": candidate_region_count,
            "target_name": TARGET_NAME,
            "model_id": MODEL_ID,
            "hf_llm_model_id": HF_LLM_MODEL_ID,
            "llm_backend": llm_backend,
            "device": DEVICE,
            "image_size": {"width": image.size[0], "height": image.size[1]},
            "scene_description": scene_description,
            "whole_image_top_labels": whole["raw"][:6],
            "source_type": source_type,
            "camera_url_used": camera_url_used,
            "location": {
                "lat": lat,
                "lon": lon,
                "accuracy": accuracy,
                "source": location_source,
            },
            "submission_note": build_submission_note(),
        }

        obs_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        original_upload = {}
        overlay_upload = {}
        ipfs_result = ""

        if upload_ipfs:
            common_keyvalues = {
                "app": "field-triage-app",
                "target": TARGET_NAME,
                "verdict": verdict,
                "score": f"{overall_score:.4f}",
                "candidate_region_count": str(candidate_region_count),
            }
            original_upload = upload_to_pinata(image, f"{obs_id}-original.png", {**common_keyvalues, "kind": "original"})
            overlay_upload = upload_to_pinata(overlay, f"{obs_id}-overlay.png", {**common_keyvalues, "kind": "overlay"})
            summary["ipfs"] = {"original": original_upload, "overlay": overlay_upload}

            parts = []
            if original_upload.get("ipfs_url"):
                parts.append(f"Original: {original_upload['ipfs_url']}")
            if overlay_upload.get("ipfs_url"):
                parts.append(f"Overlay: {overlay_upload['ipfs_url']}")
            if not parts:
                parts.append("IPFS upload failed. Check PINATA_JWT and logs.")
            ipfs_result = "\n".join(parts)

        record = {
            "id": obs_id,
            "created_at": created_at,
            "filename": f"{obs_id}.png",
            "source_type": source_type,
            "camera_url": camera_url_used,
            "verdict": verdict,
            "overall_score": round(overall_score, 4),
            "whole_image_score": round(float(whole["target_score"]), 4),
            "best_tile_score": round(float(tile_max), 4),
            "candidate_region_count": candidate_region_count,
            "scene_description": scene_description,
            "report_text": report_text,
            "llm_backend": llm_backend,
            "image_width": image.size[0],
            "image_height": image.size[1],
            "lat": lat,
            "lon": lon,
            "accuracy": accuracy,
            "location_source": location_source,
            "original_cid": original_upload.get("cid"),
            "original_ipfs_url": original_upload.get("ipfs_url"),
            "overlay_cid": overlay_upload.get("cid"),
            "overlay_ipfs_url": overlay_upload.get("ipfs_url"),
            "summary_json": summary,
        }
        save_observation(record)

        elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
        summary["processing_time_ms"] = elapsed_ms

        map_html = build_map_html(lat, lon, accuracy, verdict, overall_score)
        recent_rows = list_recent_observations()
        status_text = (
            "Location captured."
            if lat is not None and lon is not None
            else "Location not captured. Use the geolocation button and allow permission."
        )

        return (
            image,
            overlay,
            summary,
            summarize_tiles(top_tiles),
            report_text,
            ipfs_result,
            get_guidance(),
            recent_rows,
            map_html,
            status_text,
        )

    except Exception as e:
        logger.exception("Analysis failed")
        return (
            None,
            None,
            {"error": str(e)},
            [],
            "",
            "",
            get_guidance(),
            list_recent_observations(),
            build_map_html(None, None, None, "Error", 0.0),
            f"Analysis failed: {e}",
        )


# ---------------------------
# Camera refresh helper
# ---------------------------
def refresh_camera_preview(camera_url: str):
    try:
        img = fetch_image_from_camera_url(camera_url)
        return resize_for_inference(img), "Camera snapshot refreshed."
    except Exception as e:
        logger.exception("Camera refresh failed")
        return None, f"Camera refresh failed: {e}"


# ---------------------------
# CSS / JS
# ---------------------------
CUSTOM_CSS = """
footer { visibility: hidden; }
.geo-banner { padding: 12px; border-radius: 12px; background: #f5f7fb; border: 1px solid #d6dce8; }
"""

GEO_HTML = """
<div class='geo-banner'>
  <b>Capture device location</b><br>
  Use this before Analyze so the observation is stored with coordinates and shown on the map.
  <div style='margin-top:10px;'>
    <button id='capture-geo-btn' style='padding:10px 14px;border-radius:10px;border:1px solid #cbd5e1;background:#fff;cursor:pointer;'>Capture current location</button>
    <span id='geo-status' style='margin-left:10px;'>Waiting for location.</span>
  </div>
</div>
<script>
(function () {
  function setValue(containerId, value) {
    const host = document.getElementById(containerId);
    if (!host) return;
    const input = host.querySelector('input, textarea');
    if (!input) return;
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  const btn = document.getElementById('capture-geo-btn');
  const status = document.getElementById('geo-status');
  if (!btn || !status || btn.dataset.bound === '1') return;
  btn.dataset.bound = '1';

  btn.onclick = function () {
    if (!navigator.geolocation) {
      status.textContent = 'Geolocation is not supported in this browser.';
      return;
    }
    status.textContent = 'Capturing location...';
    navigator.geolocation.getCurrentPosition(
      function (position) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        const acc = position.coords.accuracy;
        setValue('lat_input', String(lat));
        setValue('lon_input', String(lon));
        setValue('accuracy_input', String(acc));
        status.textContent = `Captured: ${lat.toFixed(6)}, ${lon.toFixed(6)} (±${Math.round(acc)}m)`;
      },
      function (error) {
        status.textContent = 'Location failed: ' + error.message;
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
    );
  };
})();
</script>
"""

DESCRIPTION = """
This app supports:
- upload or browser webcam
- network camera snapshot URL input
- candidate-region visual triage
- geolocation capture and map display
- optional Pinata/IPFS evidence storage
- SQLite observation logging and CSV export
- report generation via template, local HF, Ollama, or OpenAI-compatible APIs (Groq)

Positioning: pilot/demo artifact for field triage.
"""


# ---------------------------
# UI
# ---------------------------
init_db()
config_issues = validate_config()

with gr.Blocks(title=APP_TITLE, css=CUSTOM_CSS) as demo:
    gr.Markdown(f"# {APP_TITLE}")
    gr.Markdown(DESCRIPTION)

    if config_issues:
        gr.Markdown("\n".join(f"- {x}" for x in config_issues))

    with gr.Row():
        with gr.Column(scale=1):
            source_mode = gr.Radio(
                choices=["Upload / Webcam", "Network Camera URL"],
                value="Upload / Webcam",
                label="Image source"
            )

            image_input = gr.Image(
                type="pil",
                label="Upload or use webcam",
                sources=["upload", "webcam", "clipboard"],
            )

            camera_url = gr.Textbox(
                label="Network camera snapshot URL",
                placeholder="https://camera.local/snapshot.jpg",
            )
            camera_refresh_btn = gr.Button("Refresh camera snapshot")
            camera_status = gr.Textbox(label="Camera Status", interactive=False)

            gr.HTML(GEO_HTML)
            lat_input = gr.Textbox(label="Latitude", visible=False, elem_id="lat_input")
            lon_input = gr.Textbox(label="Longitude", visible=False, elem_id="lon_input")
            accuracy_input = gr.Textbox(label="Accuracy", visible=False, elem_id="accuracy_input")
            location_status = gr.Textbox(label="Location Status", interactive=False)

            llm_backend = gr.Dropdown(
                choices=["template", "hf_local", "ollama", "openai_compat"],
                value="openai_compat",
                label="Report backend (Groq via OpenAI-compatible API)",
            )
            generate_report_check = gr.Checkbox(label="Generate report", value=True)
            upload_ipfs_check = gr.Checkbox(label="Upload original and overlay to Pinata/IPFS", value=False)

            run_btn = gr.Button("Analyze + Save", variant="primary")
            export_btn = gr.Button("Export observations CSV")
            export_file = gr.File(label="CSV export")

        with gr.Column(scale=1):
            source_preview = gr.Image(label="Source image")
            image_output = gr.Image(label="Overlay")
            map_output = gr.HTML(label="Observation Map")

    with gr.Tabs():
        with gr.TabItem("Summary"):
            json_output = gr.JSON(label="Analysis Summary")
        with gr.TabItem("Top Tiles"):
            table_output = gr.Dataframe(
                headers=["rank", "target_score", "clean_score", "box", "top_labels"],
                datatype=["number", "number", "number", "str", "str"],
                label="Top candidate tiles",
                wrap=True,
            )
        with gr.TabItem("Report"):
            report_output = gr.Textbox(label="Generated Report", lines=8)
        with gr.TabItem("IPFS"):
            ipfs_output = gr.Textbox(label="IPFS Result", lines=4)
        with gr.TabItem("Guidance"):
            guidance_output = gr.Markdown(label="Guidance")
        with gr.TabItem("Database Records"):
            db_output = gr.Dataframe(
                headers=[
                    "created_at",
                    "source_type",
                    "verdict",
                    "overall_score",
                    "candidate_region_count",
                    "lat",
                    "lon",
                    "accuracy",
                    "llm_backend",
                    "original_ipfs_url",
                    "overlay_ipfs_url",
                ],
                datatype=["str", "str", "str", "number", "number", "number", "number", "number", "str", "str", "str"],
                label="Recent observations",
                wrap=True,
            )

    camera_refresh_btn.click(
        fn=refresh_camera_preview,
        inputs=[camera_url],
        outputs=[source_preview, camera_status],
    )

    run_btn.click(
        fn=analyze,
        inputs=[
            image_input,
            source_mode,
            camera_url,
            llm_backend,
            generate_report_check,
            upload_ipfs_check,
            lat_input,
            lon_input,
            accuracy_input,
        ],
        outputs=[
            source_preview,
            image_output,
            json_output,
            table_output,
            report_output,
            ipfs_output,
            guidance_output,
            db_output,
            map_output,
            location_status,
        ],
    )

    export_btn.click(fn=export_observations_csv, inputs=None, outputs=export_file)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=PORT)
