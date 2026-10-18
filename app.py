from __future__ import annotations
import base64, json, os, re, time, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Any
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image
import io
from src.packet import build_packet, render_html_report, recalculate_totals

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
FRAMES = BASE / "outputs" / "frames"
OUT = BASE / "outputs"
FRAMES.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Library Contents Claim Agent", version="0.2.0")
app.mount("/static", StaticFiles(directory=str(BASE / "live_demo")), name="static")

# In-memory session state is intentional for this prototype; exported artifacts persist under outputs/.
SESSIONS: dict[str, dict[str, Any]] = {}

class StartSweep(BaseModel):
    country: str = "India"
    currency: str = "INR"
    second_country: str = "United States"
    second_currency: str = "USD"
    device: str = "browser webcam"

class FrameInput(BaseModel):
    sweep_id: str
    image_data_url: str
    shelf: str = "Shelf 1"
    elapsed_s: int = 0
    reference_height_cm: float | None = None
    reference_name: str = ""

class RoomInput(BaseModel):
    length_m: float | None = None
    width_m: float | None = None
    height_m: float | None = None
    floor_area_m2: float | None = None
    wall_area_m2: float | None = None
    shelved_wall_area_m2: float | None = None
    shape: str = "rectangular"
    scale_method: str = "Not established; dimensions require calibrated measurement"
    scale_confidence: float = 0.0

class Correction(BaseModel):
    sweep_id: str
    book_id: str | None = None
    item_id: str | None = None
    field: str
    value: str

class VoiceCommand(BaseModel):
    sweep_id: str
    transcript: str

class SpineDimensions(BaseModel):
    sweep_id: str
    book_id: str
    height_cm: float
    thickness_cm: float
    method: str = "user-measured with ruler"

class PriceEvidence(BaseModel):
    sweep_id: str
    target_id: str
    kind: str  # book_replacement | book_used | item_replacement
    amount: float | None = None
    low: float | None = None
    high: float | None = None
    currency: str
    source: str
    url: str
    condition_assumed: str = "unknown"

class FinalizeInput(BaseModel):
    sweep_id: str
    duration_s: int = 0
    room: RoomInput = Field(default_factory=RoomInput)


def _session(sweep_id: str) -> dict[str, Any]:
    if sweep_id not in SESSIONS:
        raise HTTPException(404, "Unknown sweep. Start a new sweep first.")
    return SESSIONS[sweep_id]

@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(BASE / "live_demo" / "index.html")

@app.get("/health")
def health():
    return {"status": "ok", "vision_configured": bool(os.getenv("GOOGLE_API_KEY")), "time": datetime.now(timezone.utc).isoformat()}

@app.post("/api/sweep/start")
def start_sweep(data: StartSweep):
    sid = "lib-" + uuid.uuid4().hex[:10]
    SESSIONS[sid] = {
        "sweep": {"id": sid, "captured_at": datetime.now(timezone.utc).isoformat(), "device": data.device,
                  "duration_s": 0, "country": data.country, "currency": data.currency,
                  "second_country": data.second_country, "second_currency": data.second_currency},
        "books": [], "items": [], "frames": [], "started": time.time(), "frame_counter": 0,
        "stage_timings": [], "corrections": [], "current_shelf": "Shelf 1", "api_usage": []
    }
    return {"sweep_id": sid, "message": "Sweep started. Pan slowly across each shelf, then walls and floor. Keep the camera moving continuously; pause briefly only when asked."}

VISION_PROMPT = '''You are a careful multilingual visual inventory assistant for an insurance contents claim. Inspect this single room/shelf frame.
Return ONLY a valid JSON object with keys: image_quality, guidance, scale_reference_bbox_norm, books, non_book_items.
image_quality: {blur: boolean, glare: boolean, occlusion: boolean, readable_spines_estimate: integer}. scale_reference_bbox_norm: [x1,y1,x2,y2] normalized 0..1000 for the clearly visible user-specified calibration object, or null if not visible. The user may supply the real height of a ruler/card in the same plane; only return its box if it is visibly clear.
guidance: short actionable capture instruction. books: array of visible book objects. Count each visually distinct book spine once, including clearly separable stacked/flat books. Fields: local_key, shelf_guess, position_left_to_right (integer), title, title_transliteration, author, author_transliteration, publisher, publisher_transliteration, edition, isbn, title_evidence (brief exact visible text evidence), confidence (0..1), possible_rare_or_signed (boolean), spine_bbox_norm ([x1,y1,x2,y2] normalized 0..1000), measurement_status.
CRITICAL MULTILINGUAL OCR RULES: Read the text actually printed on each spine in its original script. Explicitly recognize Hindi and Devanagari (हिन्दी/देवनागरी), as well as English and mixed-script spines. Preserve the exact Devanagari title/author/publisher in title/author/publisher; put optional Roman transliteration ONLY in the corresponding *_transliteration field. Never translate a title into English and present the translation as the printed title. Do not replace Devanagari with guessed English words. Inspect matras, conjunct consonants, and vowel marks carefully. Use empty strings when text is genuinely unreadable, with confidence <= 0.45; do not hallucinate or silently omit a visible book. title_evidence should quote the visible original-script characters when possible. If uncertain between similar characters, lower confidence and request a closer, straight-on, glare-free frame.
Do not claim precise physical dimensions from pixels without a visible known scale object in the same plane. The spine bbox is image geometry, not centimetres. non_book_items: array of visible non-book objects, excluding people; fields local_key, category, description, material, brand_model, confidence, bbox_norm. Art/portraits must set needs_appraisal=true unless clearly labeled print. Do not invent unseen objects. If the image is not a room/shelf, return empty arrays and guidance explaining what to capture.'''

def _record_api_usage(sweep_id: str | None, model: str, usage: dict[str, Any] | None) -> None:
    if not sweep_id or sweep_id not in SESSIONS or not isinstance(usage, dict):
        return
    try:
        record = {"model": model,
            "prompt_tokens": int(usage.get("promptTokenCount", 0) or 0),
            "output_tokens": int(usage.get("candidatesTokenCount", 0) or 0),
            "total_tokens": int(usage.get("totalTokenCount", 0) or 0),
            "at": datetime.now(timezone.utc).isoformat()}
        SESSIONS[sweep_id].setdefault("api_usage", []).append(record)
    except (TypeError, ValueError):
        return


def call_gemini(image_bytes: bytes, mime: str = "image/jpeg", reference_name: str = "", sweep_id: str | None = None) -> dict[str, Any]:
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        raise HTTPException(400, "GOOGLE_API_KEY is missing. Add it to .env and restart the app.")
    model = os.getenv("LIBRARY_VISION_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": VISION_PROMPT + (f"\nThe user says the calibration object is: {reference_name}. Only return its bounding box if that exact object is clearly visible." if reference_name else "\nNo calibration object name was supplied; return null for scale_reference_bbox_norm.")}, {"inline_data": {"mime_type": mime, "data": base64.b64encode(image_bytes).decode("ascii")}}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
    try:
        r = requests.post(url, json=body, timeout=45)
        r.raise_for_status()
        payload = r.json()
        _record_api_usage(sweep_id, model, payload.get("usageMetadata", {}))
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except requests.HTTPError as exc:
        # Never echo the request URL: the API key is carried in its query string.
        status = exc.response.status_code if exc.response is not None else "unknown"
        detail = (exc.response.text[:500] if exc.response is not None else "No provider response body")
        raise HTTPException(502, f"Gemini returned HTTP {status}. Check model access and API quota. Provider detail: {detail}")
    except requests.RequestException as exc:
        # Exception strings can include the full URL and therefore the API key.
        raise HTTPException(502, f"Gemini vision request failed ({type(exc).__name__}). Check network connectivity and retry.")
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise HTTPException(502, f"Could not parse structured vision response: {exc}")

@app.post("/api/sweep/frame")
def analyze_frame(data: FrameInput):
    s = _session(data.sweep_id)
    started = time.perf_counter()
    m = re.match(r"^data:image/(jpeg|jpg|png|webp);base64,(.+)$", data.image_data_url)
    if not m:
        raise HTTPException(400, "Expected a base64 JPEG, PNG, or WebP data URL.")
    ext = "jpg" if m.group(1) in ("jpeg", "jpg") else m.group(1)
    try:
        image_bytes = base64.b64decode(m.group(2), validate=True)
    except Exception:
        raise HTTPException(400, "Invalid base64 image data.")
    s["frame_counter"] += 1
    s["current_shelf"] = data.shelf or "Shelf 1"
    frame_name = f"{s['sweep']['id']}_frame_{s['frame_counter']:04d}.{ext}"
    frame_path = FRAMES / frame_name
    frame_path.write_bytes(image_bytes)
    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            image_w, image_h = im.size
    except Exception:
        image_w, image_h = 0, 0
    frame_ref = f"/api/frames/{frame_name}"
    frame_record = {"frame_ref": frame_ref, "saved_path": f"outputs/frames/{frame_name}", "elapsed_s": data.elapsed_s, "shelf": data.shelf, "captured_at": datetime.now(timezone.utc).isoformat()}
    s["frames"].append(frame_record)
    vision = call_gemini(image_bytes, f"image/{'jpeg' if ext == 'jpg' else ext}", data.reference_name, sweep_id=data.sweep_id)
    # Count only newly added records in this frame; repeat sightings are linked to existing records.
    books_before = len(s["books"])
    items_before = len(s["items"])
    # Conservative dedup: merge repeated sightings only when several attributes agree and the sighting is close in time.
    scale_bbox = vision.get("scale_reference_bbox_norm")
    scale_px_per_cm = None
    if data.reference_height_cm and data.reference_height_cm > 0 and isinstance(scale_bbox, list) and len(scale_bbox) == 4 and image_h:
        scale_px_per_cm = ((float(scale_bbox[3]) - float(scale_bbox[1])) * image_h / 1000.0) / data.reference_height_cm
        if scale_px_per_cm <= 0: scale_px_per_cm = None
    for b in vision.get("books", []) if isinstance(vision.get("books"), list) else []:
        title = (b.get("title") or "").strip()
        conf = float(b.get("confidence") or 0)
        bid = f"B{s['frame_counter']:03d}-{len(s['books'])+1:03d}"
        status = "needs_appraisal" if b.get("possible_rare_or_signed") else ("identified" if title and conf >= 0.60 else "unidentified")
        bbox = b.get("spine_bbox_norm")
        height_cm = thickness_cm = None
        if scale_px_per_cm and isinstance(bbox, list) and len(bbox) == 4 and image_w and image_h:
            px_w = (float(bbox[2]) - float(bbox[0])) * image_w / 1000.0
            px_h = (float(bbox[3]) - float(bbox[1])) * image_h / 1000.0
            if px_w > 0 and px_h > 0:
                height_cm = round(px_h / scale_px_per_cm, 2)
                thickness_cm = round(px_w / scale_px_per_cm, 2)
        # Avoid repeated observations of the same clearly titled spine across adjacent frames; preserve possible duplicate copies when positions differ.
        pos = b.get("position_left_to_right")
        duplicate = next((old for old in reversed(s["books"]) if title and old.get("title", "").casefold() == title.casefold() and (old.get("author", "").casefold() == ((b.get("author") or "").strip().casefold())) and old.get("shelf") == (data.shelf or b.get("shelf_guess") or "Unknown shelf") and old.get("position") == pos and data.elapsed_s - old.get("elapsed_s", -999) <= 12), None)
        if duplicate:
            duplicate.setdefault("observed_again_in", []).append(frame_ref)
            continue
        s["books"].append({"id": bid, "shelf": data.shelf or b.get("shelf_guess") or "Unknown shelf",
            "position": pos, "frame_ref": frame_ref, "elapsed_s": data.elapsed_s, "status": status,
            "title": title if conf >= 0.60 else "", "title_transliteration": (b.get("title_transliteration") or "") if conf >= 0.60 else "",
            "author": (b.get("author") or "") if conf >= 0.60 else "", "author_transliteration": (b.get("author_transliteration") or "") if conf >= 0.60 else "",
            "publisher": (b.get("publisher") or "") if conf >= 0.60 else "", "publisher_transliteration": (b.get("publisher_transliteration") or "") if conf >= 0.60 else "", "edition": (b.get("edition") or "") if conf >= 0.70 else "",
            "isbn": (b.get("isbn") or "") if conf >= 0.75 else "", "title_evidence": b.get("title_evidence", ""),
            "spine_height_cm": height_cm, "spine_thickness_cm": thickness_cm, "id_confidence": max(0,min(1,conf)),
            "replacement_cost": {"amount": None, "source": "", "url": "", "retrieved_at": "", "converted": False},
            "used_value": {"amount": None, "source": "", "url": "", "retrieved_at": "", "condition_assumed": "unknown"},
            "bbox_norm": bbox, "measurement_status": "calibrated from visible reference object in same plane" if height_cm and thickness_cm else "needs a visible known reference in the same plane",
            "possible_rare_or_signed": bool(b.get("possible_rare_or_signed"))})
    for it in vision.get("non_book_items", []) if isinstance(vision.get("non_book_items"), list) else []:
        cat = (it.get("category") or "unknown").strip().lower()
        description = (it.get("description") or "").strip()
        brand_model = (it.get("brand_model") or "").strip()
        art = any(w in cat for w in ("art", "portrait", "painting", "picture")) or bool(it.get("needs_appraisal"))
        # Non-book objects are often visible in many consecutive frames. Link repeated observations
        # rather than inflating the contents count; require a matching category plus description/brand.
        prior = next((old for old in reversed(s["items"])
                      if old.get("category", "").casefold() == cat.casefold()
                      and old.get("shelf") == (data.shelf or "Shelf 1")
                      and data.elapsed_s - old.get("elapsed_s", -999) <= 12
                      and (brand_model and old.get("brand_model", "").casefold() == brand_model.casefold()
                           or description and old.get("description", "").casefold() == description.casefold())), None)
        if prior:
            prior.setdefault("observed_again_in", []).append(frame_ref)
            continue
        item_dims = {"w": None, "h": None, "d": None}
        item_bbox = it.get("bbox_norm")
        if scale_px_per_cm and isinstance(item_bbox, list) and len(item_bbox) == 4 and image_w and image_h:
            px_w = (float(item_bbox[2]) - float(item_bbox[0])) * image_w / 1000.0
            px_h = (float(item_bbox[3]) - float(item_bbox[1])) * image_h / 1000.0
            if px_w > 0 and px_h > 0:
                item_dims = {"w": round(px_w / scale_px_per_cm, 1), "h": round(px_h / scale_px_per_cm, 1), "d": None}
        s["items"].append({"id": f"I{s['frame_counter']:03d}-{len(s['items'])+1:03d}", "category": cat,
            "description": description, "material": it.get("material", ""), "brand_model": brand_model,
            "shelf": data.shelf or "Shelf 1", "elapsed_s": data.elapsed_s,
            "frame_ref": frame_ref, "dimensions_cm": item_dims,
            "measurement_status": "width/height scaled from a known reference in the same plane; depth unavailable" if item_dims["w"] else "needs metric scale",
            "status": "needs_appraisal" if art else "unpriced", "replacement_cost": {"low": None, "high": None, "source": "", "url": "", "retrieved_at": ""},
            "confidence": max(0,min(1,float(it.get("confidence") or 0))), "bbox_norm": item_bbox})
    elapsed_ms = round((time.perf_counter()-started)*1000)
    s["stage_timings"].append({"stage": "frame_vision", "ms": elapsed_ms})
    return {"frame": frame_record, "image_quality": vision.get("image_quality", {}), "guidance": vision.get("guidance", "Continue slowly across the next section."),
            "books_added": len(s["books"]) - books_before, "items_added": len(s["items"]) - items_before, "scale_calibrated": bool(scale_px_per_cm), "book_count_so_far": len(s["books"]),
            "item_count_so_far": len(s["items"]), "books": s["books"], "items": s["items"], "latency_ms": elapsed_ms}

@app.post("/api/sweep/correct")
def correct(data: Correction):
    s = _session(data.sweep_id)
    group = "books" if data.book_id else "items"
    target_id = data.book_id or data.item_id
    allowed = {"title", "author", "publisher", "edition", "isbn", "status", "category", "description", "brand_model"}
    if data.field not in allowed or not target_id:
        raise HTTPException(400, "Correction must identify a book/item and an allowed field.")
    for obj in s[group]:
        if obj["id"] == target_id:
            obj[data.field] = data.value
            if group == "books" and data.field == "title" and data.value.strip() and obj.get("status") == "unidentified":
                obj["status"] = "identified"
            s["corrections"].append({"id": target_id, "field": data.field, "value": data.value, "at": datetime.now(timezone.utc).isoformat()})
            return {"ok": True, "updated": obj}
    raise HTTPException(404, "Item ID not found")


@app.post("/api/sweep/voice-command")
def apply_voice_command(data: VoiceCommand):
    s = _session(data.sweep_id)
    text = (data.transcript or "").strip()
    low = text.casefold()
    if not text:
        raise HTTPException(400, "Voice command is empty.")
    # Explicit title correction by item ID.
    match = re.search(r"(?:title|book)\s+(B\d{3}-\d{3})\s+(?:is|should be)\s+(.+)", text, re.I)
    if match:
        bid, title = match.group(1), match.group(2).strip().strip(" .")
        book = next((b for b in s["books"] if b["id"] == bid), None)
        if not book or not title: raise HTTPException(404, "Book ID not found or title is empty.")
        book["title"], book["status"] = title, "identified"
        s["corrections"].append({"id": bid, "field": "title", "value": title, "source": "voice", "transcript": text, "at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "action": "correct_title", "message": f"Title correction saved for {bid}.", "books": s["books"], "items": s["items"]}
    # Edition/rarity corrections apply to the most recently observed book when no ID is stated.
    if any(term in low for term in ("first edition", "signed copy", "autographed", "antiquarian", "rare book", "collectible book")):
        book = next((b for b in reversed(s["books"]) if not b.get("excluded_by_user")), None)
        if not book: raise HTTPException(400, "No book is available to apply this correction to.")
        book["edition"] = "First edition (user-reported)" if "first edition" in low else (book.get("edition") or "User-reported rare/signed copy")
        book["possible_rare_or_signed"] = True
        book["status"] = "needs_appraisal"
        book["replacement_cost"] = {"amount": None, "source": "", "url": "", "retrieved_at": "", "converted": False}
        book["used_value"] = {"amount": None, "source": "", "url": "", "retrieved_at": "", "condition_assumed": "human appraisal required"}
        s["corrections"].append({"id": book["id"], "field": "possible_rare_or_signed", "value": "true", "source": "voice", "transcript": text, "at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "action": "flag_appraisal", "message": "Flagged the latest book for human appraisal; automatic pricing is disabled.", "books": s["books"], "items": s["items"]}
    if any(term in low for term in ("not mine", "skip that shelf", "skip this shelf", "exclude this shelf", "those are not mine")):
        shelf = s.get("current_shelf") or "Shelf 1"
        affected = 0
        for obj in s["books"] + s["items"]:
            if obj.get("shelf") == shelf:
                obj["excluded_by_user"] = True
                obj["user_exclusion_reason"] = text
                affected += 1
        s["corrections"].append({"id": shelf, "field": "excluded_by_user", "value": "true", "source": "voice", "transcript": text, "at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "action": "exclude_shelf", "message": f"Marked {affected} records from {shelf} as excluded from claim totals. Records remain in the audit trail.", "books": s["books"], "items": s["items"]}
    if "it's a print" in low or "it is a print" in low or "is a print" in low or "confirmed print" in low:
        item = next((i for i in reversed(s["items"]) if any(w in (i.get("category") or "").casefold() for w in ("art", "portrait", "painting", "picture"))), None)
        if not item: raise HTTPException(400, "No artwork record found to confirm as a print.")
        item["print_confirmed"] = True
        item["status"] = "unpriced"
        item["user_confirmation"] = "User confirmed artwork is a print"
        s["corrections"].append({"id": item["id"], "field": "print_confirmed", "value": "true", "source": "voice", "transcript": text, "at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "action": "confirm_print", "message": "Artwork marked as a print; it can be considered for ordinary replacement pricing.", "books": s["books"], "items": s["items"]}
    return {"ok": False, "action": "unparsed", "message": "I did not apply a change. Try: 'title B001-001 is [correct title]', 'that is a first edition', or 'skip this shelf, those are not mine'.", "books": s["books"], "items": s["items"]}


@app.post("/api/sweep/spine-dimensions")
def save_spine_dimensions(data: SpineDimensions):
    """Save verified physical spine measurements; never derive these from pixels alone."""
    s = _session(data.sweep_id)
    if not (0.1 <= data.height_cm <= 100.0 and 0.1 <= data.thickness_cm <= 20.0):
        raise HTTPException(400, "Enter realistic positive measurements in centimetres (height 0.1–100 cm; thickness 0.1–20 cm).")
    book = next((b for b in s["books"] if b.get("id") == data.book_id), None)
    if not book:
        raise HTTPException(404, "Book ID not found in this sweep.")
    book["spine_height_cm"] = round(data.height_cm, 2)
    book["spine_thickness_cm"] = round(data.thickness_cm, 2)
    book["measurement_status"] = "user-verified in centimetres"
    book["measurement_method"] = data.method[:120]
    s["corrections"].append({"id": data.book_id, "field": "spine_dimensions_cm", "value": {"height_cm": book["spine_height_cm"], "thickness_cm": book["spine_thickness_cm"]}, "source": data.method, "at": datetime.now(timezone.utc).isoformat()})
    return {"ok": True, "book": book, "message": "Verified spine measurements saved."}


@app.post("/api/sweep/price")
def add_price_evidence(data: PriceEvidence):
    s = _session(data.sweep_id)
    if not data.url.startswith(("https://", "http://")):
        raise HTTPException(400, "A source URL beginning with http:// or https:// is required.")
    if data.currency.upper() != s["sweep"]["currency"].upper():
        raise HTTPException(400, f"Price currency must match the sweep currency ({s['sweep']['currency']}); do not silently convert currencies.")
    if not data.source.strip():
        raise HTTPException(400, "Source name is required.")
    if data.kind in ("book_replacement", "book_used"):
        target = next((x for x in s["books"] if x["id"] == data.target_id), None)
        if not target: raise HTTPException(404, "Book ID not found")
        if data.amount is None or data.amount <= 0: raise HTTPException(400, "Price must be greater than zero")
        field = "replacement_cost" if data.kind == "book_replacement" else "used_value"
        target[field] = {"amount": data.amount, "source": data.source.strip() or urlparse(data.url).netloc, "url": data.url, "retrieved_at": datetime.now(timezone.utc).date().isoformat(), "converted": False, "currency": data.currency.upper()}
        if field == "used_value": target[field]["condition_assumed"] = data.condition_assumed
        return {"ok": True, "target": target}
    if data.kind == "item_replacement":
        target = next((x for x in s["items"] if x["id"] == data.target_id), None)
        if not target: raise HTTPException(404, "Item ID not found")
        if data.low is None or data.high is None or data.low <= 0 or data.high < data.low: raise HTTPException(400, "Provide a valid positive low/high price range")
        target["replacement_cost"] = {"low": data.low, "high": data.high, "source": data.source.strip() or urlparse(data.url).netloc, "url": data.url, "retrieved_at": datetime.now(timezone.utc).date().isoformat(), "currency": data.currency.upper()}
        target["status"] = "priced" if data.low == data.high else "range"
        return {"ok": True, "target": target}
    raise HTTPException(400, "Unknown price kind")

@app.post("/api/sweep/room-measurement")
def import_room_measurement(payload: dict[str, Any]):
    """Attach a calibrated native AR/RoomPlan summary to the current sweep.

    Accepts only measurements exported by a supported measurement provider; it does
    not infer metres from browser pixels. A RoomPlan summary can be generated by the
    native iOS companion and imported during the same inventory session.
    """
    sid = str(payload.get("sweep_id") or "")
    s = _session(sid)
    room = payload.get("room") if isinstance(payload.get("room"), dict) else payload
    try:
        L, W, H = (float(room[k]) for k in ("length_m", "width_m", "height_m"))
        confidence = float(room.get("confidence", 0))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Room measurement must include numeric length_m, width_m and height_m.")
    if min(L, W, H) <= 0 or max(L, W, H) > 100:
        raise HTTPException(400, "Room dimensions are outside plausible bounds; verify the measurement export.")
    if not 0 <= confidence <= 1:
        raise HTTPException(400, "confidence must be between 0 and 1.")
    floor = room.get("floor_area_m2")
    wall = room.get("wall_area_m2")
    shelved = room.get("shelved_wall_area_m2")
    for name, value in (("floor_area_m2", floor), ("wall_area_m2", wall), ("shelved_wall_area_m2", shelved)):
        if value is not None and (not isinstance(value, (int, float)) or value < 0):
            raise HTTPException(400, f"{name} must be a non-negative number or null.")
    measurement = {"length_m": L, "width_m": W, "height_m": H,
        "floor_area_m2": float(floor) if floor is not None else None,
        "wall_area_m2": float(wall) if wall is not None else None,
        "shelved_wall_area_m2": float(shelved) if shelved is not None else None,
        "shape": str(room.get("shape") or "unknown"),
        "scale_method": str(room.get("scale_method") or "Native AR/RoomPlan; verify device support"),
        "scale_confidence": confidence,
        "measurement_source": str(room.get("measurement_source") or "RoomPlan import"),
        "measured_at": datetime.now(timezone.utc).isoformat()}
    s["room_measurement"] = measurement
    return {"ok": True, "room": measurement, "message": "Calibrated room measurement attached to this sweep."}


@app.post("/api/sweep/finalize")
def finalize(data: FinalizeInput):
    finalize_started = time.perf_counter()
    s = _session(data.sweep_id)
    s["sweep"]["duration_s"] = data.duration_s or int(time.time()-s["started"])
    room = data.room.model_dump()
    imported = s.get("room_measurement")
    if imported:
        # The calibrated provider result takes precedence over empty/manual UI values.
        for key in ("length_m", "width_m", "height_m", "floor_area_m2", "wall_area_m2", "shelved_wall_area_m2", "shape", "scale_method", "scale_confidence"):
            value = imported.get(key)
            if value is not None:
                room[key] = value
    # If calibrated shelf/bookcase width and height were measured from same-plane scale
    # references during the camera sweep, provide an explicitly labelled approximation.
    # Do not infer shelf coverage from unscaled bounding boxes.
    if room.get("shelved_wall_area_m2") is None:
        shelf_area = 0.0
        shelf_count = 0
        for item in s["items"]:
            category = str(item.get("category") or "").casefold()
            dims = item.get("dimensions_cm") or {}
            w, h = dims.get("w"), dims.get("h")
            if any(term in category for term in ("shelf", "bookcase", "book shelf", "bookshelf", "shelving")) and isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0:
                shelf_area += (w / 100.0) * (h / 100.0)
                shelf_count += 1
        if shelf_count:
            room["shelved_wall_area_m2"] = round(shelf_area, 3)
            room["shelved_wall_area_method"] = "Approximation from calibrated shelf/bookcase bounding boxes; verify coverage and overlap against ground truth"
    packet = build_packet(s, room)
    if room.get("shelved_wall_area_method"):
        packet["room"]["shelved_wall_area_method"] = room["shelved_wall_area_method"]
        packet["review_queue"].append({"ref_id": "room.shelved_wall_area_m2", "reason": room["shelved_wall_area_method"]})
    # Mark rare/signed/first-edition candidates before automated valuation.
    for b in packet["books"]:
        if b.get("possible_rare_or_signed") or (b.get("edition") and any(w in b["edition"].lower() for w in ("first edition", "signed", "antiquarian"))):
            b["status"] = "needs_appraisal"
            b["replacement_cost"] = {"amount": None, "source": "", "url": "", "retrieved_at": "", "converted": False}
            b["used_value"] = {"amount": None, "source": "", "url": "", "retrieved_at": "", "condition_assumed": "human appraisal required"}
            packet["review_queue"].append({"ref_id": b["id"], "reason": "Potential rare/signed/antiquarian/first edition; automatic pricing disabled pending human appraisal."})

    for obj in packet["books"] + packet["items"]:
        if obj.get("excluded_by_user"):
            packet["review_queue"].append({"ref_id": obj.get("id", ""), "reason": "User explicitly excluded this item/shelf from claim totals; retained in the audit trail."})
    eligible = [b for b in packet["books"] if b.get("title") and b.get("status") == "identified" and not b.get("possible_rare_or_signed") and not b.get("excluded_by_user")]
    # Batch five books per grounded Search request. Run batches concurrently to keep a large
    # shelf within the five-minute target where provider quota and retailer response permit.
    jobs: list[tuple[str, str, str, list[dict[str, Any]]]] = []
    def chunks(items, size=5):
        return [items[i:i + size] for i in range(0, len(items), size)]
    replacement_targets = [b for b in eligible if not (b.get("replacement_cost", {}).get("source") and isinstance(b.get("replacement_cost", {}).get("amount"), (int, float)))]
    used_targets = [b for b in eligible if not (b.get("used_value", {}).get("source") and isinstance(b.get("used_value", {}).get("amount"), (int, float)))]
    second_targets = eligible[:10]
    item_targets = [i for i in packet["items"] if i.get("status") != "needs_appraisal" and not i.get("excluded_by_user") and not i.get("replacement_cost", {}).get("source")]
    for group in chunks(replacement_targets): jobs.append(("replacement", s["sweep"]["country"], s["sweep"]["currency"], group))
    for group in chunks(used_targets): jobs.append(("used", s["sweep"]["country"], s["sweep"]["currency"], group))
    for group in chunks(second_targets): jobs.append(("second", s["sweep"]["second_country"], s["sweep"]["second_currency"], group))
    for group in chunks(item_targets): jobs.append(("item", s["sweep"]["country"], s["sweep"]["currency"], group))
    lookup_results: list[tuple[str, str, str, list[dict[str, Any]], dict[str, list[dict[str, Any]]]]] = []
    pricing_started = time.perf_counter()
    def run_job(job):
        kind, country, currency, group = job
        if kind == "item":
            return (*job, web_item_price_ranges_batch(group, country, currency, sweep_id=data.sweep_id))
        price_type = "used" if kind == "used" else "replacement"
        return (*job, web_book_price_offers_batch(group, country, currency, price_type=price_type, sweep_id=data.sweep_id))
    if jobs:
        with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as pool:
            futures = [pool.submit(run_job, job) for job in jobs]
            for future in as_completed(futures):
                try: lookup_results.append(future.result())
                except Exception: continue
    s["stage_timings"].append({"stage": "price_search_and_page_verification", "ms": round((time.perf_counter() - pricing_started) * 1000)})
    replacement_map: dict[str, list[dict[str, Any]]] = {}
    used_map: dict[str, list[dict[str, Any]]] = {}
    second_map: dict[str, list[dict[str, Any]]] = {}
    item_map: dict[str, list[dict[str, Any]]] = {}
    for kind, country, currency, group, values in lookup_results:
        target_map = replacement_map if kind == "replacement" else used_map if kind == "used" else second_map if kind == "second" else item_map
        target_map.update(values)

    for b in eligible:
        bid = str(b["id"])
        if bid in replacement_map:
            offers = replacement_map[bid]
            b["price_offers"] = offers[:10]
            if offers:
                selected = min(offers, key=lambda x: x["amount"])
                b["replacement_cost"] = {"amount": selected["amount"], "source": selected["source"], "url": selected["url"], "retrieved_at": selected["retrieved_at"], "converted": False, "currency": selected["currency"]}
                if selected.get("publisher_dimensions"):
                    b["publisher_dimensions"] = selected["publisher_dimensions"]
                b["replacement_price_second"] = next((x for x in offers if x is not selected), None)
                b["price_selection_note"] = "Lowest directly page-verified matching-currency offer retrieved from grounded Google Search sources; exact edition/stock still needs review."
            else:
                b["price_search_links"] = price_search_links(b["title"], b.get("author", ""), s["sweep"]["country"])
                packet["review_queue"].append({"ref_id": bid, "reason": "No matching price could be verified on an accessible cited retailer page. Search links are provided; price remains blank."})
        if bid in used_map:
            used_offers = used_map[bid]
            b["used_price_offers"] = used_offers[:5]
            if used_offers:
                used = min(used_offers, key=lambda x: x["amount"])
                b["used_value"] = {"amount": used["amount"], "source": used["source"], "url": used["url"], "retrieved_at": used["retrieved_at"], "condition_assumed": used.get("condition", "condition not stated"), "currency": used["currency"], "price_evidence": used.get("price_evidence", "")}
            else:
                packet["review_queue"].append({"ref_id": bid, "reason": "No directly page-verified used-market price found; used value remains blank."})

    for item in packet["items"]:
        if item.get("status") == "needs_appraisal" or item.get("excluded_by_user"):
            continue
        offers = item_map.get(str(item["id"]), [])
        item["price_offers"] = offers[:5]
        if offers:
            selected = min(offers, key=lambda x: x["low"])
            item["replacement_cost"] = {"low": selected["low"], "high": selected["high"], "source": selected["source"], "url": selected["url"], "retrieved_at": selected["retrieved_at"], "currency": selected["currency"]}
            item["status"] = "priced" if selected["low"] == selected["high"] else "range"
        else:
            packet["review_queue"].append({"ref_id": item["id"], "reason": "No non-book replacement price range was verified from an accessible cited page; value remains blank."})

    # Keep a comparison row for each of the same first 10 non-rare identified books, even if
    # no price is available in the second locale; never silently omit failed lookups.
    comparisons = []
    for b in second_targets:
        p2 = second_map.get(str(b["id"]), [])
        selected = min(p2, key=lambda x: x["amount"]) if p2 else None
        comparisons.append({"book_id": b["id"], "title": b["title"], "country": s["sweep"]["second_country"], "currency": s["sweep"]["second_currency"],
            "replacement_cost": ({"amount": selected["amount"], "source": selected["source"], "url": selected["url"], "retrieved_at": selected["retrieved_at"], "converted": False, "currency": selected["currency"]} if selected else {"amount": None, "source": "", "url": "", "retrieved_at": "", "converted": False}),
            "price_offers": p2[:2]})
        if not selected:
            packet["review_queue"].append({"ref_id": b["id"], "reason": f"No page-verified replacement price found for the second-country comparison ({s['sweep']['second_country']}); comparison remains blank."})
    recalculate_totals(packet)
    s["stage_timings"].append({"stage": "packet_totals_and_report_data", "ms": round((time.perf_counter() - finalize_started) * 1000)})
    usage = s.get("api_usage", [])
    prompt_tokens = sum(int(x.get("prompt_tokens", 0)) for x in usage)
    output_tokens = sum(int(x.get("output_tokens", 0)) for x in usage)
    total_tokens = sum(int(x.get("total_tokens", 0)) for x in usage)
    try:
        input_rate = float(os.getenv("GEMINI_INPUT_USD_PER_MILLION_TOKENS", ""))
        output_rate = float(os.getenv("GEMINI_OUTPUT_USD_PER_MILLION_TOKENS", ""))
        cost_estimate = round(prompt_tokens * input_rate / 1_000_000 + output_tokens * output_rate / 1_000_000, 6)
        cost_note = "Estimated from Gemini usageMetadata and the per-million-token rates configured in .env; confirm rates against current provider billing."
    except (TypeError, ValueError):
        cost_estimate = None
        cost_note = "Token usage is measured, but cost remains unknown until current model input/output rates are configured in .env."
    packet["performance"] = {"stage_timings": s["stage_timings"], "total_frame_count": len(s["frames"]), "frame_count": len(s["frames"]), "correction_count": len(s["corrections"]),
        "api_usage": {"request_count": len(usage), "prompt_tokens": prompt_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens},
        "cost_usd_estimate": cost_estimate, "cost_note": cost_note,
        "total_finalize_ms": round((time.perf_counter() - finalize_started) * 1000)}
    packet["frames"] = s["frames"]
    packet["corrections"] = s["corrections"]
    json_path = OUT / f"{data.sweep_id}_claim_packet.json"
    html_path = OUT / f"{data.sweep_id}_report.html"
    json_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(render_html_report(packet), encoding="utf-8")
    return {"packet": packet, "json_url": f"/api/download/{json_path.name}", "report_url": f"/api/download/{html_path.name}", "summary": {"book_count": packet["totals"]["book_count"], "identified": packet["totals"]["books_identified"], "review_items": len(packet["review_queue"]), "frame_count": len(s["frames"]), "packet_path": str(json_path)}}

def _page_has_price_evidence(url: str, amount: float, currency: str, title: str) -> tuple[bool, str]:
    """Verify a grounded offer against price data on the cited page itself.

    Google Search grounding provides source URLs but not a trustworthy machine-readable
    snippet contract. This extra fetch rejects model-reported amounts that are not present
    in accessible retailer page metadata/text. If the retailer blocks access, the offer is
    not counted as verified.
    """
    try:
        r = requests.get(url, timeout=(2.0, 3.0), headers={
            "User-Agent": "Mozilla/5.0 (compatible; LibraryClaimAgent/1.0; price verification)"
        }, allow_redirects=True)
        if r.status_code >= 400 or not r.text:
            return False, ""
        html = r.text[:2_000_000]
    except requests.RequestException:
        return False, ""

    # Reject a cited page that does not appear to be about the target title.
    normalized_page = re.sub(r"[^a-z0-9]+", " ", html.casefold())
    page_tokens = [t for t in re.sub(r"[^a-z0-9]+", " ", (title or "").casefold()).split() if len(t) > 2]
    if not page_tokens:
        return False, ""
    title_overlap = sum(1 for token in page_tokens if token in normalized_page)
    if title_overlap < (1 if len(page_tokens) == 1 else min(2, len(page_tokens))):
        return False, ""

    expected = currency.upper()
    numeric = {round(float(amount), 2), round(float(amount), 0)}
    # Structured product metadata is strongest because price and currency are separate fields.
    currency_candidates = re.findall(r'"priceCurrency"\s*:\s*"([A-Za-z]{3})"', html, flags=re.I)
    currency_candidates += re.findall(r'(?:product:price:currency|og:price:currency)["\']?\s+content=["\']([A-Za-z]{3})', html, flags=re.I)
    currency_candidates += re.findall(r'itemprop=["\']priceCurrency["\'][^>]*content=["\']([A-Za-z]{3})', html, flags=re.I)
    structured_currency = next((v.upper() for v in currency_candidates if v), "")
    price_candidates = re.findall(r'"price"\s*:\s*"?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)"?', html, flags=re.I)
    price_candidates += re.findall(r'itemprop=["\']price["\'][^>]*content=["\']([0-9,.]+)', html, flags=re.I)
    price_candidates += re.findall(r'(?:product:price:amount|og:price:amount)["\']?\s+content=["\']([0-9,.]+)', html, flags=re.I)
    price_values = [(v,) for v in price_candidates]
    if structured_currency == expected:
        for groups in price_values:
            raw = next((g for g in groups if g), "")
            try:
                val = round(float(raw.replace(",", "")), 2)
            except ValueError:
                continue
            if abs(val - float(amount)) <= 0.01:
                return True, "Cited retailer page structured price metadata matches the reported amount and currency."

    # Fallback: visible currency markers adjacent to the exact numeric amount.
    formatted = {f"{v:,.2f}" for v in numeric} | {f"{v:,.0f}" for v in numeric}
    text = re.sub(r"<script\b[^>]*>[\s\S]*?</script>|<style\b[^>]*>[\s\S]*?</style>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    markers = {
        "INR": r"(?:₹|\bRs\.?\s*|\bINR\s*)",
        "USD": r"(?:\$|\bUSD\s*)",
        "GBP": r"(?:£|\bGBP\s*)",
        "CAD": r"(?:\bCAD\s*\$|\bC\$|\bCAD\s*)",
        "AUD": r"(?:\bAUD\s*\$|\bA\$|\bAUD\s*)",
    }
    marker = markers.get(expected)
    if not marker:
        return False, ""
    for value in sorted(formatted, key=len, reverse=True):
        pattern = marker + re.escape(value) + r"(?![0-9])"
        if re.search(pattern, text, flags=re.I):
            return True, "Exact amount and requested-currency marker found in cited retailer page text."
    return False, ""


def web_book_price_offers(title: str, author: str, country: str, currency: str,
                         price_type: str = "replacement") -> list[dict[str, Any]]:
    """Use Gemini with Google Search grounding to retrieve sourced web prices.

    Uses the existing GOOGLE_API_KEY (same key as vision); no Custom Search Engine
    ID or Google Books API is required. Only accepts offers whose URL is present in
    Gemini's grounding citations. If the grounded response is unusable, return []
    rather than inventing a value.
    """
    title, author = (title or "").strip(), (author or "").strip()
    api_key = os.getenv("GOOGLE_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not title or not api_key:
        return []
    if country.casefold() == "india" or currency.upper() == "INR":
        market_hint = "India; quote only INR prices marked ₹, Rs, or INR"
    else:
        market_hint = f"{country}; quote only prices explicitly denominated in {currency.upper()}"
    if price_type == "used":
        value_kind = "used-market listing for a used physical copy, including condition if the source states it"
        query_hint = "used copy second hand pre-owned price"
    else:
        value_kind = "new replacement cost for a new physical copy or the closest currently purchasable equivalent"
        query_hint = "buy new paperback hardcover price"

    prompt = f"""Search the live web for prices for this book. This is an insurance contents claim, so never guess or use model memory.
Book title: {title}
Author: {author or "unknown"}
Country/market: {market_hint}
Price type required: {value_kind}
Search intent: {query_hint}

Return ONLY a JSON object with key "offers" containing at most 8 offers. Each offer must have:
{{"amount": number, "currency": "{currency.upper()}", "title": string, "author": string, "format": string, "condition": string, "source_title": string, "url": string, "price_evidence": string, "match_confidence": number, "publisher_dimensions_cm": {{"width": number|null, "height": number|null, "thickness": number|null, "source_url": string}}}}
Also search for the edition's published physical dimensions (cover width x height x thickness) where available. Only return publisher_dimensions_cm when a grounded source explicitly reports them; source_url must be an exact Google Search grounding URL. Dimensions are bibliographic product specs, not measurements of this particular copy.
Rules:
- Use Google Search results and open/current retailer or marketplace pages where possible. Do not use Google Books.
- Include only a price explicitly visible/reported by a cited source, in the requested currency, for a physical book. Exclude ebook, audiobook, rental, bundle, shipping-only, and unrelated results.
- URLs must be exact source URLs returned by Google Search grounding, not fabricated URLs or search-query URLs.
- Match the title and author. If edition is not established, say so in format; do not claim exact edition.
- For replacement prices prefer new copies. For used prices use used listings and state the listed condition, or "condition not stated".
- Do not convert currencies. Do not infer a price from a price range unless a numeric low/high is explicitly stated; this output is for a single explicit listed amount.
- If no verifiable result exists, return {{"offers": []}}.
- Keep price_evidence short and specific; it must say where the number appeared (e.g. product page or search snippet). Do not treat a source as evidence just because it sells books.
"""
    model = os.getenv("LIBRARY_PRICE_MODEL", "gemini-2.5-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        response = requests.post(
            endpoint, params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "tools": [{"google_search": {}}],
                  "generationConfig": {"temperature": 0.0}},
            headers={"Accept": "application/json"}, timeout=45)
        response.raise_for_status()
        payload = response.json()
        candidate = (payload.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if isinstance(p, dict))
        metadata = candidate.get("groundingMetadata") or {}
        grounded = {}
        for chunk in metadata.get("groundingChunks", []) or []:
            web = chunk.get("web") or {}
            url = web.get("uri") or ""
            if url.startswith(("https://", "http://")):
                grounded[url] = web.get("title") or (urlparse(url).hostname or "Web source")
        if not text:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                return []
            data = json.loads(match.group(0))
        raw_offers = data.get("offers", []) if isinstance(data, dict) else []
        if not isinstance(raw_offers, list):
            return []
        norm = lambda v: re.sub(r"[^a-z0-9]+", " ", (v or "").casefold()).strip()
        title_tokens = [t for t in norm(title).split() if len(t) > 2]
        found, seen = [], set()
        for offer in raw_offers:
            if not isinstance(offer, dict):
                continue
            url = str(offer.get("url") or "").strip()
            try:
                amount = float(offer.get("amount"))
            except (TypeError, ValueError):
                continue
            if url not in grounded or amount <= 0 or amount > 1000000:
                continue
            if str(offer.get("currency") or "").upper() != currency.upper():
                continue
            result_title = str(offer.get("title") or "")
            result_author = str(offer.get("author") or "")
            evidence = str(offer.get("price_evidence") or "").strip()
            combined = norm(" ".join([result_title, result_author]))
            overlap = sum(1 for token in title_tokens if token in combined)
            required = 1 if len(title_tokens) <= 1 else min(2, len(title_tokens))
            author_tokens = [t for t in norm(author).split() if len(t) > 2]
            author_match = not author_tokens or any(t in norm(result_author) for t in author_tokens)
            if not title_tokens or overlap < required or not author_match or not evidence:
                continue
            page_verified, page_evidence = _page_has_price_evidence(url, amount, currency.upper(), title)
            if not page_verified:
                continue
            evidence = evidence + " " + page_evidence
            dedupe_key = (url, amount, currency.upper())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            try:
                confidence = max(0.0, min(1.0, float(offer.get("match_confidence") or 0.5)))
            except (TypeError, ValueError):
                confidence = 0.5
            dimensions = offer.get("publisher_dimensions_cm") if isinstance(offer.get("publisher_dimensions_cm"), dict) else None
            safe_dimensions = None
            if dimensions:
                dim_url = str(dimensions.get("source_url") or "").strip()
                try:
                    dw = float(dimensions.get("width")) if dimensions.get("width") is not None else None
                    dh = float(dimensions.get("height")) if dimensions.get("height") is not None else None
                    dt = float(dimensions.get("thickness")) if dimensions.get("thickness") is not None else None
                    if dim_url in grounded and all(v is None or 0 < v < 100 for v in (dw, dh, dt)) and any(v is not None for v in (dw, dh, dt)):
                        safe_dimensions = {"width_cm": dw, "height_cm": dh, "thickness_cm": dt, "source": grounded[dim_url], "url": dim_url, "retrieved_at": datetime.now(timezone.utc).date().isoformat(), "note": "Publisher/listing specification; not a physical measurement of this copy."}
                except (TypeError, ValueError):
                    safe_dimensions = None
            found.append({"amount": amount, "currency": currency.upper(), "source": grounded[url], "url": url,
                "publisher_dimensions": safe_dimensions,
                "retrieved_at": datetime.now(timezone.utc).date().isoformat(), "title": result_title,
                "author": result_author, "format": str(offer.get("format") or "not established"),
                "condition": str(offer.get("condition") or ("condition not stated" if price_type == "used" else "new; verify listing")),
                "price_evidence": evidence, "match_confidence": confidence,
                "match_note": "Gemini Google Search-grounded offer; confirm exact edition, format, stock, seller and shipping."})
        return sorted(found, key=lambda item: item["amount"])
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        # External lookup failure must never break packet generation or invent a value.
        return []

def web_book_price_offers_batch(books: list[dict[str, Any]], country: str, currency: str,
                                price_type: str = "replacement", sweep_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Search a small batch of books in one grounded Gemini request to reduce latency.

    Every returned offer still has to cite a grounding URL, match the target title/author,
    and have the exact amount/currency visible in the cited retailer page. Missing evidence
    means an empty list, not a model-generated estimate.
    """
    api_key = os.getenv("GOOGLE_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
    result: dict[str, list[dict[str, Any]]] = {str(b.get("id")): [] for b in books}
    if not api_key or not books:
        return result
    market_hint = f"{country}; quote only prices explicitly denominated in {currency.upper()}"
    if price_type == "used":
        kind = "used physical copies, including listing condition where available"
        query_hint = "used copy second hand pre-owned price"
    else:
        kind = "new physical copy or closest currently purchasable equivalent"
        query_hint = "buy new paperback hardcover price"
    book_lines = "\n".join(f"- id={b.get('id')}; title={b.get('title')}; author={b.get('author') or 'unknown'}" for b in books)
    prompt = f"""Use Google Search grounding to search live web prices for each book below. This is an insurance claim; never use model memory or invent a price.
Country/currency: {market_hint}
Price type: {kind}; search intent: {query_hint}
Books:
{book_lines}
Return ONLY JSON: {{"offers":[{{"book_id":"exact input id","amount":number,"currency":"{currency.upper()}","title":string,"author":string,"format":string,"condition":string,"url":string,"price_evidence":string,"match_confidence":number}}]}}
Rules: physical books only; exclude ebooks, audio, rentals, bundles, shipping-only offers; only explicit numeric prices in requested currency; exact cited URLs from Google Search grounding, not search query URLs; title/author must match; no currency conversion; state unknown edition/condition honestly; return [] for any book with no grounded price. Do not use Google Books."""
    model = os.getenv("LIBRARY_PRICE_MODEL", "gemini-2.5-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        response = requests.post(endpoint, params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}],
                  "generationConfig": {"temperature": 0.0}}, timeout=35)
        response.raise_for_status()
        response_payload = response.json()
        _record_api_usage(sweep_id, model, response_payload.get("usageMetadata", {}))
        candidate = (response_payload.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if isinstance(p, dict))
        metadata = candidate.get("groundingMetadata") or {}
        grounded: dict[str, str] = {}
        for chunk in metadata.get("groundingChunks", []) or []:
            web = chunk.get("web") or {}
            url = web.get("uri") or ""
            if url.startswith(("https://", "http://")):
                grounded[url] = web.get("title") or (urlparse(url).hostname or "Web source")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", text)
            if not m: return result
            data = json.loads(m.group(0))
        by_id = {str(b.get("id")): b for b in books}
        for offer in data.get("offers", []) if isinstance(data, dict) else []:
            if not isinstance(offer, dict): continue
            bid = str(offer.get("book_id") or "")
            target = by_id.get(bid)
            url = str(offer.get("url") or "").strip()
            try: amount = float(offer.get("amount"))
            except (TypeError, ValueError): continue
            if not target or url not in grounded or amount <= 0 or amount > 1_000_000: continue
            if str(offer.get("currency") or "").upper() != currency.upper(): continue
            result_title = str(offer.get("title") or "")
            result_author = str(offer.get("author") or "")
            norm = lambda v: re.sub(r"[^a-z0-9]+", " ", (v or "").casefold()).strip()
            title_tokens = [t for t in norm(str(target.get("title") or "")).split() if len(t) > 2]
            title_joined = norm(result_title)
            if not title_tokens or sum(t in title_joined for t in title_tokens) < (1 if len(title_tokens) == 1 else min(2, len(title_tokens))): continue
            author_tokens = [t for t in norm(str(target.get("author") or "")).split() if len(t) > 2]
            if author_tokens and not any(t in norm(result_author) for t in author_tokens): continue
            evidence = str(offer.get("price_evidence") or "").strip()
            if not evidence: continue
            verified, page_note = _page_has_price_evidence(url, amount, currency.upper(), str(target.get("title") or ""))
            if not verified: continue
            result[bid].append({"amount": amount, "currency": currency.upper(), "source": grounded[url], "url": url,
                "retrieved_at": datetime.now(timezone.utc).date().isoformat(), "title": result_title,
                "author": result_author, "format": str(offer.get("format") or "not established"),
                "condition": str(offer.get("condition") or ("condition not stated" if price_type == "used" else "new; verify listing")),
                "price_evidence": evidence + " " + page_note,
                "match_confidence": max(0.0, min(1.0, float(offer.get("match_confidence") or 0.5))),
                "match_note": "Google Search-grounded and cited retailer page price-checked; exact edition, stock, seller and shipping still require review."})
        for bid in result: result[bid].sort(key=lambda x: x["amount"])
        return result
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        return result


def web_item_price_ranges_batch(items: list[dict[str, Any]], country: str, currency: str, sweep_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Search sourced replacement prices for visible non-book items in small batches."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
    result: dict[str, list[dict[str, Any]]] = {str(i.get("id")): [] for i in items}
    if not api_key or not items:
        return result
    item_lines = "\n".join(f"- id={i.get('id')}; category={i.get('category')}; description={i.get('description')}; brand/model={i.get('brand_model') or 'unknown'}; visible material={i.get('material') or 'unknown'}" for i in items)
    prompt = f"""Use Google Search grounding to find current local replacement prices for these non-book household/library contents.
Country: {country}. Currency: {currency.upper()}.
Items:
{item_lines}
Return ONLY JSON {{"offers":[{{"item_id":"exact input id","low":number,"high":number,"currency":"{currency.upper()}","match_title":string,"source_title":string,"url":string,"price_evidence":string,"match_confidence":number}}]}}
Rules: use live cited results, never model memory; exact currency only; physical replacement goods only; no shipping-only prices; if exact brand/model is unknown, return a defensible range only if the source supports the numbers; do not make up a range. URL must exactly match a Google Search grounding citation. For art, portraits and potentially collectible items, return no offer and leave them for appraisal. If no verifiable offer exists, omit that item."""
    model = os.getenv("LIBRARY_PRICE_MODEL", "gemini-2.5-flash")
    try:
        response = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key}, json={"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.0}}, timeout=35)
        response.raise_for_status()
        response_payload = response.json()
        _record_api_usage(sweep_id, model, response_payload.get("usageMetadata", {}))
        candidate = (response_payload.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if isinstance(p, dict))
        metadata = candidate.get("groundingMetadata") or {}
        grounded = {}
        for chunk in metadata.get("groundingChunks", []) or []:
            web = chunk.get("web") or {}; url = web.get("uri") or ""
            if url.startswith(("https://", "http://")): grounded[url] = web.get("title") or (urlparse(url).hostname or "Web source")
        try: data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match: return result
            data = json.loads(match.group(0))
        by_id = {str(i.get("id")): i for i in items}
        for offer in data.get("offers", []) if isinstance(data, dict) else []:
            if not isinstance(offer, dict): continue
            iid, url = str(offer.get("item_id") or ""), str(offer.get("url") or "").strip()
            target = by_id.get(iid)
            try: low, high = float(offer.get("low")), float(offer.get("high"))
            except (TypeError, ValueError): continue
            if not target or url not in grounded or low <= 0 or high < low or high > 100_000_000: continue
            if str(offer.get("currency") or "").upper() != currency.upper(): continue
            category = str(target.get("category") or "")
            if any(word in category.casefold() for word in ("art", "portrait", "painting", "antique", "collectible")) and not target.get("print_confirmed"): continue
            evidence = str(offer.get("price_evidence") or "").strip()
            match_title = str(offer.get("match_title") or "")
            if not evidence or not match_title: continue
            title_query = " ".join(x for x in (category, str(target.get("description") or ""), str(target.get("brand_model") or "")) if x)
            low_ok, _ = _page_has_price_evidence(url, low, currency.upper(), title_query)
            high_ok, _ = _page_has_price_evidence(url, high, currency.upper(), title_query)
            if not low_ok or not high_ok: continue
            result[iid].append({"low": low, "high": high, "currency": currency.upper(), "source": grounded[url], "url": url,
                "retrieved_at": datetime.now(timezone.utc).date().isoformat(), "price_evidence": evidence,
                "match_title": match_title, "match_confidence": max(0.0, min(1.0, float(offer.get("match_confidence") or 0.5))),
                "verification_note": "Both range endpoints were found on the cited page with matching currency; check model equivalence and stock."})
        return result
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        return result


def price_search_links(title: str, author: str, country: str) -> list[dict[str, str]]:
    """Return search pages, not claimed prices, for manual verification when no API price exists."""
    query = " ".join(x.strip() for x in (title or "", author or "") if x and x.strip())
    encoded = requests.utils.quote(query)
    links = [{"source": "Google Shopping search", "url": f"https://www.google.com/search?tbm=shop&q={encoded}"}]
    if country == "India":
        links.extend([
            {"source": "Amazon India search", "url": f"https://www.amazon.in/s?k={encoded}"},
            {"source": "Bookswagon search", "url": f"https://www.bookswagon.com/search-books/{encoded}"},
        ])
    elif country == "United States":
        links.extend([
            {"source": "Amazon search", "url": f"https://www.amazon.com/s?k={encoded}"},
            {"source": "AbeBooks search", "url": f"https://www.abebooks.com/servlet/SearchResults?kn={encoded}"},
        ])
    return links

@app.get("/api/frames/{filename}")
def open_frame(filename: str):
    if "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid frame name")
    p = FRAMES / filename
    if not p.exists():
        raise HTTPException(404, "Frame not found")
    return FileResponse(p)

@app.get("/api/download/{filename}")
def download(filename: str):
    if "/" in filename or "\\" in filename or not filename.endswith((".json", ".html")):
        raise HTTPException(400, "Invalid file name")
    p = OUT / filename
    if not p.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(p, filename=filename)
