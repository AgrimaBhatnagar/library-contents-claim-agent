from src.packet import build_packet, recalculate_totals, render_html_report


def test_shelf_run_sums_only_positive_calibrated_non_excluded_thicknesses():
    session = {
        "sweep": {"id": "test", "country": "India", "currency": "INR"},
        "books": [
            {"id": "B1", "title": "A", "status": "identified", "spine_thickness_cm": 2.5},
            {"id": "B2", "title": "B", "status": "identified", "spine_thickness_cm": 2.4},
            {"id": "B3", "title": "C", "status": "identified", "spine_thickness_cm": None},
            {"id": "B4", "title": "D", "status": "identified", "spine_thickness_cm": 3.0, "excluded_by_user": True},
        ],
        "items": [],
    }
    packet = build_packet(session, {})
    assert packet["totals"]["shelf_run_m"] == 0.049
    assert packet["totals"]["books_with_calibrated_thickness"] == 2
    html = render_html_report(packet)
    assert "0.049 m from 2 measured books" in html


def test_recalculate_totals_keeps_measured_count_consistent():
    packet = {"books": [{"status": "identified", "spine_thickness_cm": 1.2}], "items": []}
    recalculate_totals(packet)
    assert packet["totals"]["shelf_run_m"] == 0.012
    assert packet["totals"]["books_with_calibrated_thickness"] == 1
