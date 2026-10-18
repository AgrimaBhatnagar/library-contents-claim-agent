# Library Contents Claim Agent (reference-app companion)

This project is a working **extension/prototype** for the take-home assignment. It is designed to sit alongside the already-running `Insurance Claim Live Agent Team` reference app you confirmed works at `http://127.0.0.1:4177`. It does not overwrite the reference files or pretend that the original app's insurance workflow is already a library inventory workflow.

## Gemini companion — reliability update (v0.2.0)

This revision stays on the Gemini-based companion app; it does not modify the separate no-token/Tesseract project.

- Repeated non-book objects observed on the same shelf within a short interval are linked to the original record instead of automatically inflating the item count. This is deliberately conservative and should still be reviewed against the saved frames.
- Per-frame `books_added` and `items_added` now report net-new records after deduplication, so spoken guidance and status counts are less misleading.
- Pausing camera capture and pressing Start resumes the existing sweep instead of silently creating a new session and mixing stale browser state with a new backend inventory.
- Gemini HTTP/network errors are more actionable and avoid echoing the request URL, which can contain the API key.
- App version is now 0.2.0.

## What it implements

- Browser camera capture during one continuous sweep; captures a frame every ~4.5 seconds and saves each frame under `outputs/frames/`.
- Browser speech recognition (where supported) and spoken capture guidance using speech synthesis; a text box is the fallback. Voice commands can correct a book title, flag the most recent book as first-edition/rare for appraisal, exclude the current shelf from claim totals, or confirm the most recent artwork as a print. The existing reference app remains available for Gemini Live conversation.
- Gemini vision extraction of visible books and non-book items into structured JSON, with confidence, visible text evidence, frame references and conservative blank fields.
- Optional metric scale calibration: put a ruler/known-height object in the same plane as the spines, enter its real height and name, and keep it visible. Bounding boxes can then yield rough height/thickness estimates. Perspective, angle and incorrect object detection can still cause errors; verify the sample against a tape measure.
- Room geometry can be sent directly from the native iOS RoomPlan companion to the active backend sweep, using the displayed sweep ID; JSON export/import remains as a fallback. The browser-only fallback still uses tape-measured inputs. RoomPlan is integrated into the same backend session, but the room scan and browser book-camera capture are still separate device workflows.
- Gemini vision extraction for book spines and non-book objects, with saved frames and confidence/review handling.
- Gemini Google Search grounding for replacement-price lookup using the same `GOOGLE_API_KEY` as vision. No Google Books or Google Custom Search Engine credentials are used. Price lookups are batched and concurrent; an offer is accepted only if its URL is cited, title/author match, currency matches, and the accessible cited page itself exposes the exact amount and currency. A blocked or unverifiable page leaves the price blank.
- A separate grounded search for used-market listings; used values remain blank and enter the review queue when no sourced used listing is found.
- Second-country replacement-price comparison for up to 10 identified titles using independent local-market grounded searches.
- `claim_packet.json`, readable HTML report, saved frames, a review queue, per-stage timing, Gemini token usage, and optional cost estimation when current model token rates are configured.

## What is not yet solved / honest limitations

- The app is a companion on port **4178**, not yet merged into the reference app's existing Gemini Live WebSocket and ADK graph. Keep the reference running at port 4177 and run this app separately. The README in your submission should describe this accurately.
- Browser speech recognition is not the same as the reference app's Gemini Live real-time audio conversation. Use the existing app for the reference live voice demo; this companion currently uses browser speech input/output and camera-frame analysis.
- Camera-frame detections can repeat the same book or miss books between frames. A conservative adjacent-frame deduplication heuristic is included, but the inventory must be reviewed against ground truth.
- Metric spine/item width-height estimates require a known-size reference in the same plane. A native iOS RoomPlan summary can be sent directly to the active sweep, but it does not yet derive shelf-covered wall area automatically. A normal webcam cannot reliably recover metric room dimensions by itself.
- Gemini Search grounding does not guarantee that a result page exposes a current price or that the edition is identical. The code now fetches the cited page and checks for a matching title, currency and exact amount in accessible structured metadata or page text. Retailer blocks and JavaScript-only prices can still cause a valid offer to remain blank. The app does not use Google Books.
- Cost is reported as unmeasured because Gemini billing data is not available from the API response used here. Measure it from provider billing/usage before claiming a cost per sweep.
- This code has not been evaluated against your required 60+ book ground-truth scene. Do not claim it meets the assignment pass bars until you run and record the tests.

## Setup (Windows PowerShell)

Use the **same Python 3.12 environment** or create a separate one. From this directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Put your Google AI Studio key in `.env`:

```dotenv
GOOGLE_API_KEY=your_real_key_here
LIBRARY_VISION_MODEL=gemini-2.5-flash
```

Keep `.env` private and never commit it. Then start this companion app:

```powershell
python -m uvicorn app:app --reload --host 0.0.0.0 --port 4178
```

Open [http://127.0.0.1:4178](http://127.0.0.1:4178) on the same computer. The backend listens on the LAN interface so the native RoomPlan companion can send geometry to the active sweep. The browser camera on a phone still requires a secure HTTPS context. Your original reference remains at [http://127.0.0.1:4177](http://127.0.0.1:4177).

If `GOOGLE_API_KEY` is missing, `/health` will say the vision API is not configured and frame analysis will return a clear error. The key must have access to the configured Gemini API model.

## Identify books from existing photos (new)

1. Open `http://127.0.0.1:4178` and find **Upload book pictures** in the left panel.
2. Choose one or multiple JPG, PNG or WebP photos, then click **Analyze selected photos**.
3. The first upload automatically creates a photo-import session if you have not started a live sweep. Gemini analyzes each photo sequentially, saves the image under `outputs/frames/`, and adds detected books and non-book objects to the inventory.
4. Review titles, confidence and frame links. Correct uncertain titles before exporting. If you also want a room measurement and final packet, enter the room's tape-measured dimensions and click **Finish & build claim packet**.

The upload flow resizes images to a maximum width of 1600 pixels in the browser before sending them to the configured Gemini Vision model. Images are processed one at a time. This is a prototype: multiple overlapping photos may duplicate books, and identification must be checked against the originals. Uploading pictures does not by itself establish metric dimensions or market prices.

## How to run a live sweep

1. Choose local country/currency and a second country.
2. Start sweep and allow browser camera access.
3. Pan slowly across all shelves, stacks, walls and floor, without pulling books or photographing books one by one. The camera sends periodic evidence frames.
4. For metric spine estimates, place a ruler or another known-height object beside the spines in the same plane, enter its real height and its name, and keep it visible in captured frames. If not available, leave it blank and dimensions should remain unmeasured.
5. Enter room length, width, ceiling height and shelved wall area from a tape measure. These are ground-truth inputs, not computer-vision estimates.
6. End capture and finish the packet. Download the JSON and open the HTML report. Review all flags, source URLs, frame links, prices and measurements.

Correction text formats include `title B001-001 is [correct title]`, `that is a first edition`, `skip this shelf, those are not mine`, and `that portrait is a print`. Title corrections are tied to an explicit book ID; first-edition/rare and print confirmations apply to the most recent matching record. Shelf exclusion is retained in the audit trail but removed from claim totals. The app intentionally does not accept arbitrary prices by voice; pricing must be traceable to an external source.

## Run tests

```powershell
pip install -r requirements-dev.txt
pytest -q
python evaluation/evaluate_pass_bars.py --packet outputs/<real_sweep_id>_claim_packet.json
```

## Reference project: what we kept / changed / discarded

- **Kept:** the reference interaction concept (camera + voice, inventory/state visible while working, final adjuster packet), Gemini as a provider, and the principle of structured extraction with deterministic business logic.
- **Changed:** the claim schema, capture loop, evidence references, room geometry fields, price integrity checks, review queue and output files are library-specific.
- **Discarded for this task:** mock policy lookup, insurance coverage routing, damage sketches and the original damage-oriented extraction schema. They do not answer the book-count/measurement/pricing requirements.
- **Integration note:** this is intentionally a companion service to protect the known-working reference app. A final submission should merge the library endpoints into the reference server and connect the capture session to its Gemini Live workflow, then re-test the whole flow.

## Output locations

- `outputs/frames/<sweep>_frame_XXXX.jpg` — saved evidence frames.
- `outputs/<sweep>_claim_packet.json` — structured claim packet.
- `outputs/<sweep>_report.html` — human-readable report.

Frame references in the packet use `/api/frames/<filename>` so they open while the server is running; `saved_path` also records the repository-relative disk path.

## Required evaluation work still to do

The project includes blank ground-truth templates and `evaluation/evaluate_pass_bars.py`. You must capture a real room with at least 60 books across 2+ shelving units and 8+ non-book items, hand-count it, hand-read legible titles, tape-measure 20 spines and the room, and hand-check 15 prices. Fill the templates with your actual observations and run the evaluator. Missing values report as `NOT EVALUATED`; do not fill templates with synthetic data.

## Pricing and room-dimension reliability notes

- The finalize step uses Gemini Google Search grounding in batches of five books per request. It requires a cited URL and then fetches the page to verify the exact amount/currency and title against accessible metadata or page text. If a retailer blocks requests or prices are JavaScript-only, it leaves the price blank and adds review/search links rather than guessing.
- The price lookup uses Gemini with the Google Search grounding tool and the same `GOOGLE_API_KEY` as book recognition. No `GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_CX`, or Google Books access is needed. New replacement and used-market prices are searched separately. It filters URLs to grounding citations, checks title/author and currency, then verifies the amount against the cited page. The lowest directly page-verified offer is selected. If none qualifies, the price remains null and a search link/review reason is retained.
- Search-grounded pages may refer to an ebook, another edition, shipping-excluded price or a marketplace seller. Therefore a captured amount is source-backed but still requires the user to confirm the exact physical edition and availability before an insurance claim.
- The browser app still does **not** measure room length/width/height from its webcam. The included SwiftUI RoomPlan companion now sends its summary directly to the active backend sweep (or can export JSON as fallback). It remains a separate native room-scan workflow rather than a single unified native camera session; shelf-covered wall area is not automatically segmented, and Swift has not been compiled in Xcode or tested on a supported iOS device in this environment. A normal webcam cannot recover metric dimensions from pixels alone.
- Automated tests cover grounded price parsing and page verification, no-price behavior, RoomPlan import, irregular-room area handling, packet totals and frame deduplication. They do not prove live retailer coverage, iOS compilation, room measurement accuracy or the assignment pass bars; these still require a real target-device run and ground-truth evaluation.


## Gemini Google Search-grounded book pricing (not Google Books)

The same `GOOGLE_API_KEY` used for Gemini vision is used to request Gemini Google Search grounding. No separate Programmable Search Engine ID or Custom Search API key is needed. In `.env`, set:

```dotenv
GOOGLE_API_KEY=your_real_gemini_api_key
LIBRARY_VISION_MODEL=gemini-2.5-flash
LIBRARY_PRICE_MODEL=gemini-2.5-flash
```

Gemini is asked to search the requested local market and return explicit price evidence, a numeric amount, and source URLs. The code accepts only URLs present in the response's grounding citations, with a matching currency and title overlap. The lowest accepted replacement offer is selected; a separate query searches used listings. If Gemini returns no verifiable price, the app leaves the value blank rather than inventing one. Confirm the edition, physical format, seller, stock, condition, and shipping on the cited page before using a price in an insurance claim. Grounding may have usage charges and rate limits; check Google AI Studio usage for actual cost.


## Latest revision notes (2026-10-18)
- Vision instructions now explicitly require Hindi/Devanagari and mixed-script spine reading, preserving the printed original-script title and storing Roman transliteration separately when available. This is a prompt-level improvement; Hindi accuracy still requires validation on real Hindi-spine photos.
- Book cards now show `spine height ... cm` and `spine thickness ... cm` separately, and clearly say `not calibrated` instead of an ambiguous `— × — cm`.
- Numeric dimensions are only computed when a known-height reference object is visible in the same plane and its real height is entered. A search result's published book dimensions describe a product/edition and are not a measurement of the copy on the shelf.

## Generate the app-style claim report from the final Gemini workbook

The project includes `generate_claim_report.py`, which exports the spreadsheet into the app-style HTML report format with the sweep ID `lib-40b3687c8a`.

```bash
pip install -r requirements.txt
python generate_claim_report.py sample_data/Library_Books_Inventory.xlsx outputs/Library_Contents_Claim_Report.html
```

You can pass any compatible inventory workbook as the first argument and any destination `.html` path as the optional second argument. The generator reads the `Book #`, `Frame / Shelf Section`, `Book Title`, `Author / Contributor`, `Category / Topic`, `Verification Status`, `Est. Spine Width (cm)`, and `Est. Amazon Price (USD)` columns. It intentionally does not display a verification-status or tentative-title column. If a title is unverified, both the displayed title and its price are rendered as `Unverified`. The report includes the six non-book detections associated with this sweep and does not invent room measurements or second-country prices.
