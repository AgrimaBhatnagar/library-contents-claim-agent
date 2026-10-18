# Architecture note

```text
Browser camera (continuous sweep; periodic frames)
       | JPEG + elapsed time + shelf label + optional known-scale object
       v
FastAPI /api/sweep/frame ----> saved evidence frame (outputs/frames)
       |                      |
       v                      +--> frame_ref URL + repository-relative path
Gemini Vision JSON extraction
       |  (book spines, non-books, confidence, bounding boxes, capture quality)
       v
Conservative inventory + optional same-plane scale calibration
       |
       +--> voice-command parser (title correction, rare/first-edition appraisal, shelf exclusion, print confirmation)
       +--> user corrections / review queue
       +--> Gemini Google Search grounding (new replacement offers; explicit price + cited URL)
       +--> Gemini Google Search grounding (used-market offers; condition when stated)
       +--> second-country local-market lookup for up to 10 titles
       |
       v
Deterministic Python packet builder
       |-- room geometry from tape-entered dimensions
       |-- totals from line items; user-excluded and unknown values omitted
       |-- token usage + stage latency; optional cost estimate from configured current token rates
       |-- human review flags for unknowns, art, rare copies, dimensions, prices
       v
claim_packet.json + HTML report + saved evidence frames
```

## Model / source boundaries

- Gemini vision identifies only what is visible and returns structured JSON. Confidence gates prevent low-confidence title fields from being filled. It is not the authority for prices or room measurements.
- A visible, user-named known-height reference object can calibrate rough spine dimensions only when in the same plane. The scale can be wrong if the reference is occluded, the perspective differs or the model draws a bad box. Verify 20 spines with a tape measure.
- Browser room dimensions are not inferred from webcam pixels. The browser backend accepts an imported RoomPlan summary from the included Swift companion, using native AR/RoomPlan geometry and provider-supplied area values. However, the native scanner now posts directly to the active sweep ID (with JSON export/import fallback), but room scanning and book-camera capture remain separate device workflows, and shelf-covered wall area is not automatically detected. This is a known remaining gap.
- Pricing uses Gemini with Google's Search grounding tool, not Google Books or Custom Search JSON API. URLs are restricted to grounding citations, and each reported offer is additionally checked against the cited page for title overlap, exact amount and currency. Pages blocked by retailers or prices rendered only by JavaScript remain unverified and blank. This improves integrity but does not guarantee current stock, exact edition, shipping or final checkout price.
- Browser speech input/output supports voice corrections for title, first-edition/rare flags, shelf exclusion, and print confirmation. It is not integrated with the reference app's Gemini Live/WebSocket conversation; that remains a gap to address before claiming a full live agent.
- All totals are Python-calculated. Every identified object links to a saved frame. Uncertainty goes to `review_queue`.

## Important limitation

This service is currently a companion to the reference app, not yet wired into its Gemini Live WebSocket/ADK graph. The final engineering step is to mount these routes in `live_demo/server.py` and connect the browser sweep to the existing live voice session. Test and document the merge before submission.
