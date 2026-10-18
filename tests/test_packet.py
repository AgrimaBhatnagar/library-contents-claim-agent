import unittest
from src.packet import build_packet, recalculate_totals

class PacketTests(unittest.TestCase):
    def test_totals_are_computed_from_lines(self):
        session = {"sweep": {"id":"x","captured_at":"2026-01-01T00:00:00Z","device":"test","duration_s":10,"country":"India","currency":"INR"},
                   "books": [{"id":"B1","status":"identified","title":"Book","author":"A","frame_ref":"/api/frames/a.jpg","spine_height_cm":20,"spine_thickness_cm":2,"id_confidence":0.9,"replacement_cost":{"amount":100,"source":"source","url":"https://example.com","retrieved_at":"2026-01-01"},"used_value":{"amount":None}}],
                   "items": [], "frames": []}
        packet = build_packet(session, {"length_m":4,"width_m":3,"height_m":2.5,"scale_method":"tape","scale_confidence":0.9})
        self.assertEqual(packet["totals"]["book_count"],1)
        self.assertEqual(packet["totals"]["books_replacement_cost"],100)
        self.assertEqual(packet["totals"]["shelf_run_m"],0.02)
        self.assertEqual(packet["room"]["floor_area_m2"],12)
        self.assertEqual(packet["room"]["wall_area_m2"],35)
        recalculate_totals(packet)
        self.assertEqual(packet["totals"]["books_replacement_cost"],100)

    def test_unknown_values_stay_null(self):
        session = {"sweep":{"id":"x","country":"India","currency":"INR"},"books":[],"items":[],"frames":[]}
        packet = build_packet(session, {})
        self.assertIsNone(packet["room"]["floor_area_m2"])
        self.assertIsNone(packet["totals"]["books_replacement_cost"])

if __name__ == '__main__': unittest.main()
