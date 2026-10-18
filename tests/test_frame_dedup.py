import base64
import io
import unittest
from unittest.mock import patch
from PIL import Image
import app as app_module


class FrameDedupTests(unittest.TestCase):
    def test_repeated_non_book_sighting_does_not_inflate_count(self):
        sweep_id = "test-dedup-sweep"
        app_module.SESSIONS[sweep_id] = {
            "sweep": {"id": sweep_id}, "books": [], "items": [], "frames": [],
            "started": 0, "frame_counter": 0, "stage_timings": [], "corrections": []
        }
        image_buffer = io.BytesIO()
        Image.new("RGB", (120, 80), "white").save(image_buffer, format="JPEG")
        image_data_url = "data:image/jpeg;base64," + base64.b64encode(image_buffer.getvalue()).decode("ascii")
        vision = {
            "image_quality": {}, "guidance": "Continue slowly.", "scale_reference_bbox_norm": None,
            "books": [], "non_book_items": [{
                "category": "lamp", "description": "desk lamp", "material": "metal",
                "brand_model": "Acme Lamp", "confidence": 0.9, "bbox_norm": [1, 1, 100, 100]
            }]
        }
        with patch.object(app_module, "call_gemini", return_value=vision):
            first = app_module.analyze_frame(app_module.FrameInput(
                sweep_id=sweep_id, image_data_url=image_data_url, shelf="Shelf 1", elapsed_s=0))
            second = app_module.analyze_frame(app_module.FrameInput(
                sweep_id=sweep_id, image_data_url=image_data_url, shelf="Shelf 1", elapsed_s=5))
        self.assertEqual(first["items_added"], 1)
        self.assertEqual(second["items_added"], 0)
        self.assertEqual(len(second["items"]), 1)
        self.assertEqual(len(second["items"][0]["observed_again_in"]), 1)
        app_module.SESSIONS.pop(sweep_id, None)


if __name__ == "__main__":
    unittest.main()
