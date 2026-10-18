from fastapi import HTTPException
import pytest
from app import StartSweep, SpineDimensions, start_sweep, save_spine_dimensions, SESSIONS


def test_user_verified_spine_dimensions_are_saved_in_centimetres():
    started = start_sweep(StartSweep(country="India", currency="INR", device="test"))
    sid = started["sweep_id"]
    SESSIONS[sid]["books"].append({"id": "B001-001", "title": "गोदान", "spine_height_cm": None, "spine_thickness_cm": None})
    result = save_spine_dimensions(SpineDimensions(sweep_id=sid, book_id="B001-001", height_cm=21.0, thickness_cm=2.4))
    assert result["book"]["spine_height_cm"] == 21.0
    assert result["book"]["spine_thickness_cm"] == 2.4
    assert result["book"]["measurement_status"] == "user-verified in centimetres"


def test_rejects_unrealistic_spine_dimensions():
    started = start_sweep(StartSweep(country="India", currency="INR", device="test"))
    sid = started["sweep_id"]
    SESSIONS[sid]["books"].append({"id": "B001-001", "title": "Test"})
    with pytest.raises(HTTPException):
        save_spine_dimensions(SpineDimensions(sweep_id=sid, book_id="B001-001", height_cm=0, thickness_cm=2.4))
