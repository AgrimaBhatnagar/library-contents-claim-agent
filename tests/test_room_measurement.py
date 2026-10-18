from app import StartSweep, start_sweep, import_room_measurement, SESSIONS
from src.packet import build_packet


def test_roomplan_measurement_is_attached_to_active_sweep():
    started = start_sweep(StartSweep(country="India", currency="INR", device="test"))
    sid = started["sweep_id"]
    response = import_room_measurement({
        "sweep_id": sid,
        "room": {
            "length_m": 4.2, "width_m": 3.4, "height_m": 2.7,
            "floor_area_m2": 14.28, "wall_area_m2": 41.04,
            "shelved_wall_area_m2": None,
            "shape": "roomplan_rectangular_approximation",
            "scale_method": "Apple RoomPlan / ARKit metric room capture",
            "confidence": 0.75,
            "measurement_source": "Apple RoomPlan CapturedRoom",
        },
    })
    assert response["ok"] is True
    assert SESSIONS[sid]["room_measurement"]["length_m"] == 4.2
    assert SESSIONS[sid]["room_measurement"]["floor_area_m2"] == 14.28


def test_irregular_room_does_not_get_rectangular_area_fabricated():
    packet = build_packet(
        {"sweep": {"id": "test", "country": "India", "currency": "INR"}, "books": [], "items": []},
        {"length_m": 4.2, "width_m": 3.4, "height_m": 2.7, "shape": "irregular", "scale_method": "RoomPlan", "scale_confidence": 0.7},
    )
    assert packet["room"]["floor_area_m2"] is None
    assert packet["room"]["wall_area_m2"] is None
