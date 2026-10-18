import json
import unittest
from unittest.mock import patch
import app

class FakeResponse:
    def __init__(self, payload=None, text="", status_code=200):
        self.payload, self.text, self.status_code = payload, text, status_code
    def raise_for_status(self): return None
    def json(self): return self.payload

def grounded_response(offers, urls):
    chunks = [{'web': {'uri': url, 'title': 'Example Bookstore'}} for url in urls]
    return {'candidates': [{'content': {'parts': [{'text': json.dumps({'offers': offers})}]},
                            'groundingMetadata': {'groundingChunks': chunks}}]}

class PriceSearchTests(unittest.TestCase):
    @patch.dict('os.environ', {'GOOGLE_API_KEY':'test-key', 'LIBRARY_PRICE_MODEL':'gemini-2.5-flash'}, clear=False)
    @patch('app.requests.get')
    @patch('app.requests.post')
    def test_extracts_grounded_price_and_source(self, post, get):
        url = 'https://bookstore.example/product-1'
        post.return_value = FakeResponse(grounded_response([{
            'amount': 349, 'currency': 'INR', 'title': 'The Example Book', 'author': 'A Author',
            'format': 'paperback', 'condition': 'new', 'url': url,
            'price_evidence': 'Product page lists ₹349', 'match_confidence': 0.9}], [url]))
        get.return_value = FakeResponse(text='<html><title>The Example Book</title><script type="application/ld+json">{"name":"The Example Book","price":"349.00","priceCurrency":"INR"}</script></html>')
        offers = app.web_book_price_offers('The Example Book', 'A Author', 'India', 'INR')
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]['amount'], 349.0)
        self.assertEqual(offers[0]['currency'], 'INR')
        self.assertEqual(offers[0]['url'], url)
        self.assertEqual(offers[0]['source'], 'Example Bookstore')
        self.assertIn('google_search', post.call_args.kwargs['json']['tools'][0])

    @patch.dict('os.environ', {'GOOGLE_API_KEY':'test-key'}, clear=False)
    @patch('app.requests.post')
    def test_rejects_uncited_or_fabricated_url(self, post):
        post.return_value = FakeResponse(grounded_response([{
            'amount': 349, 'currency': 'INR', 'title': 'The Example Book', 'author': 'A Author',
            'url': 'https://fake.example/not-cited', 'price_evidence': 'price ₹349'}], []))
        self.assertEqual(app.web_book_price_offers('The Example Book', 'A Author', 'India', 'INR'), [])

    @patch.dict('os.environ', {'GOOGLE_API_KEY':'test-key'}, clear=False)
    @patch('app.requests.post')
    def test_does_not_invent_price_when_no_offer(self, post):
        post.return_value = FakeResponse(grounded_response([], []))
        self.assertEqual(app.web_book_price_offers('The Example Book', 'A Author', 'India', 'INR'), [])


    @patch.dict('os.environ', {'GOOGLE_API_KEY':'test-key'}, clear=False)
    @patch('app.requests.get')
    @patch('app.requests.post')
    def test_rejects_grounded_url_when_page_does_not_confirm_amount(self, post, get):
        url = 'https://bookstore.example/product-1'
        post.return_value = FakeResponse(grounded_response([{
            'amount': 349, 'currency': 'INR', 'title': 'The Example Book', 'author': 'A Author',
            'url': url, 'price_evidence': 'Search result says ₹349'}], [url]))
        get.return_value = FakeResponse(text='<html><title>The Example Book</title><p>Out of stock</p><span>₹499</span></html>')
        self.assertEqual(app.web_book_price_offers('The Example Book', 'A Author', 'India', 'INR'), [])

    def test_requires_gemini_api_key(self):
        with patch.dict('os.environ', {'GOOGLE_API_KEY':'', 'GEMINI_API_KEY':''}, clear=False):
            self.assertEqual(app.web_book_price_offers('The Example Book', 'A Author', 'India', 'INR'), [])

if __name__ == '__main__': unittest.main()
