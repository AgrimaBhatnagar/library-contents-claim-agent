import json
from unittest.mock import patch
import app

class FakeResponse:
    def __init__(self, payload=None, text="", status_code=200):
        self.payload, self.text, self.status_code = payload, text, status_code
    def raise_for_status(self): return None
    def json(self): return self.payload

def test_nonbook_price_range_requires_cited_page_amounts_and_currency():
    url = "https://shop.example/desk-lamp"
    response = {
        "candidates": [{
            "content": {"parts": [{"text": json.dumps({"offers": [{
                "item_id": "I001-001", "low": 100, "high": 120, "currency": "INR",
                "match_title": "Desk lamp", "url": url,
                "price_evidence": "Retailer page lists ₹100–₹120", "match_confidence": 0.8
            }]})}]},
            "groundingMetadata": {"groundingChunks": [{"web": {"uri": url, "title": "Desk Lamp Store"}}]}
        }]
    }
    page = '<html><title>Desk lamp</title><script type="application/ld+json">{"price":"100","priceCurrency":"INR"}</script><p>₹120</p></html>'
    with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}, clear=False), \
         patch("app.requests.post", return_value=FakeResponse(payload=response)), \
         patch("app.requests.get", return_value=FakeResponse(text=page)):
        result = app.web_item_price_ranges_batch([{"id": "I001-001", "category": "lamp", "description": "desk lamp"}], "India", "INR")
    assert result["I001-001"][0]["low"] == 100
    assert result["I001-001"][0]["high"] == 120


def test_nonbook_pricing_never_autopriced_for_art():
    url = "https://shop.example/art"
    response = {"candidates": [{"content": {"parts": [{"text": json.dumps({"offers": [{"item_id": "I001", "low": 100, "high": 120, "currency": "INR", "match_title": "portrait print", "url": url, "price_evidence": "₹100–₹120"}]})}]}, "groundingMetadata": {"groundingChunks": [{"web": {"uri": url, "title": "Art"}}]}}]}
    with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}, clear=False), patch("app.requests.post", return_value=FakeResponse(payload=response)):
        result = app.web_item_price_ranges_batch([{"id": "I001", "category": "portrait", "description": "portrait"}], "India", "INR")
    assert result["I001"] == []
