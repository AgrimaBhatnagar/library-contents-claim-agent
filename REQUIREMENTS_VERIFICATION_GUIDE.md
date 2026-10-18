# Six-capability verification guide

This package is a code prototype, not proof that the take-home pass bars have been met. Use this guide to verify each requirement with evidence. Never fill results with guesses.

## 1. Live sweep agent
- Run `uvicorn app:app --host 0.0.0.0 --port 8000` after installing `requirements.txt` and configuring `.env`.
- Open the app on a phone on the same network. Verify camera permission, audible voice in/out, live inventory updates, spoken corrections, and capture-quality feedback.
- Browser speech recognition and speech synthesis now support spoken corrections, rare/first-edition appraisal flags, shelf exclusion, and print confirmation. Still verify real-time usability on the target phone; the reference app Gemini Live/WebSocket is not integrated into this sweep client.
- Evidence: unedited video, sweep duration, notes on blur/glare/occlusion handling, and measured latency.

## 2. Books from spine
- Collect ground truth for at least 60 books across 2+ shelving units, including books stacked/lying flat.
- Hand-read every legible title and manually measure 20 spine heights/thicknesses.
- Verify each `frame_ref` opens a saved frame. Unreadable spines must remain unidentified, not guessed.
- Pass bars: count within 5%; at least 70% of human-legible titles correct; no more than 3% confidently wrong; sampled dimensions within 15%.

## 3. Book valuation
- Hand-check 15 book prices against the same source type used by the system; store local currency, source URL, retrieval date and assumed condition.
- Verify replacement and used values separately. Missing prices remain blank and excluded from totals.
- Run the same 10 books in a second country/currency and verify locale is a setting.
- Pass bar: price error within 25% on the 15-book sample. Do not automatically price rare/signed/antiquarian items.

## 4. Non-book contents
- Ground-truth at least 8 non-book items: shelves, furniture, lamp, framed art/portrait, rug, electronics and decor as available.
- Compare item recall and category accuracy. Verify dimensions, source URLs, retrieval dates and low/high range handling.
- Art/portraits must be flagged for appraisal unless the user confirms they are prints.
- Pass bar: at least 80% of items found with correct category.

## 5. Room surface area
- Measure room length, width, ceiling height and shelving-covered wall area manually for ground truth.
- The included iOS RoomPlan companion emits a metric summary JSON and the browser backend accepts it via **Import RoomPlan measurements**. It still requires an Xcode target and supported device, has not been compiled/device-tested here, and runs as a separate scan/export rather than the same integrated browser sweep. Shelved-wall area is still not detected automatically.
- On supported Apple devices, RoomPlan uses camera/LiDAR and ARKit. On Android, implement ARCore depth and a separate geometry calculation layer. Do not label a manual estimate as LiDAR.
- Verify room shape assumptions, total wall area and shelved wall area; use a non-rectangular-room method when appropriate.
- Pass bars: floor area within 10%; wall area within 15% of tape-measured ground truth.

## 6. Claim packet
- Finalize a real sweep and inspect `claim_packet.json`, the HTML report, and saved frames.
- Check every required schema field: sweep metadata, room metrics and scale method, books, replacement/used pricing evidence, non-book items, totals and review queue.
- Recompute totals in code from line items. Verify all `frame_ref` values resolve to saved frames and all price URLs/dates exist.
- Unknown values stay null/blank and are excluded from totals. Check the review queue includes every uncertain record.
- Pass bar: packet/report generated within five minutes after sweep ends.

## Required submission evidence beyond the six capabilities
1. Private repository, `.env.example`, no secrets committed.
2. One-take demo video <= 6 minutes.
3. Actual claim packet, readable report and referenced frames from the recorded sweep.
4. Ground-truth sheet and measured pass-bar results.
5. One-page architecture note.
6. One-page failure log with three worst errors, root causes, measured fix, cost per sweep and stage latency.

## Automated checks (run from project root)
```powershell
py -m pip install -r requirements-dev.txt
pytest -q
py -m py_compile app.py src/packet.py
node --check live_demo/app.js
```
These tests are necessary but not sufficient; they do not validate real-device LiDAR, real pricing accuracy, or the assignment pass bars.
