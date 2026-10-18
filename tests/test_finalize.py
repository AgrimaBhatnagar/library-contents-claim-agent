from app import StartSweep, FrameInput, FinalizeInput, start_sweep, finalize, SESSIONS
from unittest.mock import patch


def test_finalize_preserves_unknowns_and_creates_artifacts(tmp_path, monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, "OUT", tmp_path)
    started = start_sweep(StartSweep(country="India", currency="INR", device="test"))
    sid = started["sweep_id"]
    SESSIONS[sid]["books"].append({
        "id": "B001-001", "shelf": "Shelf 1", "position": 1,
        "frame_ref": "/api/frames/test.jpg", "status": "identified",
        "title": "Example Book", "author": "A Author", "edition": "",
        "spine_height_cm": None, "spine_thickness_cm": None, "id_confidence": 0.9,
        "replacement_cost": {"amount": None, "source": "", "url": "", "retrieved_at": "", "converted": False},
        "used_value": {"amount": None, "source": "", "url": "", "retrieved_at": "", "condition_assumed": "unknown"},
        "possible_rare_or_signed": False,
    })
    with patch.object(app_module, "web_book_price_offers_batch", return_value={"B001-001": []}):
        result = finalize(FinalizeInput(sweep_id=sid, duration_s=60))
    packet = result["packet"]
    assert packet["books"][0]["replacement_cost"]["amount"] is None
    assert packet["totals"]["book_count"] == 1
    assert packet["room"]["length_m"] is None
    assert (tmp_path / f"{sid}_claim_packet.json").exists()
    assert (tmp_path / f"{sid}_report.html").exists()
