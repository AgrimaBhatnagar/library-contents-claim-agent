from app import StartSweep, VoiceCommand, start_sweep, apply_voice_command, SESSIONS


def _session_with_book():
    sid = start_sweep(StartSweep(country="India", currency="INR", device="test"))["sweep_id"]
    SESSIONS[sid]["books"].append({"id": "B001-001", "shelf": "Shelf 1", "title": "Example", "author": "A", "status": "identified", "replacement_cost": {"amount": 20, "source": "x", "url": "https://example.com", "retrieved_at": "2026-10-18"}, "used_value": {"amount": 10, "source": "x", "url": "https://example.com", "retrieved_at": "2026-10-18"}})
    return sid


def test_voice_first_edition_flags_appraisal_and_clears_prices():
    sid = _session_with_book()
    result = apply_voice_command(VoiceCommand(sweep_id=sid, transcript="That is a first edition"))
    book = SESSIONS[sid]["books"][0]
    assert result["action"] == "flag_appraisal"
    assert book["status"] == "needs_appraisal"
    assert book["replacement_cost"]["amount"] is None
    assert book["used_value"]["amount"] is None


def test_voice_skip_shelf_excludes_records_from_claim_totals():
    sid = _session_with_book()
    result = apply_voice_command(VoiceCommand(sweep_id=sid, transcript="Skip this shelf, those are not mine"))
    assert result["action"] == "exclude_shelf"
    assert SESSIONS[sid]["books"][0]["excluded_by_user"] is True
