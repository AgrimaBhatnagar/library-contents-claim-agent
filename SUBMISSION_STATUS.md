# Submission status — read before submitting

This package is the final **code prototype bundle** currently available. It is not, by itself, a complete take-home submission because the assignment requires evidence from a real, measured sweep.

## Implemented in this prototype

- Gemini vision-based extraction from periodic camera frames or uploaded images.
- Saved frame references and structured claim packet / HTML report.
- Confidence/review handling for uncertain titles, possible rare/signed books, and art.
- Deterministic Python totals; rectangular area calculations and provider-supplied RoomPlan geometry import. The browser-only room measurement fallback remains manual.
- Batched Gemini Google Search-grounded replacement-price lookup using the same `GOOGLE_API_KEY`; no Google Books or CSE credentials. Offers require a cited URL, title/author match, currency match, and exact price evidence from the accessible cited page. The lowest verified offer is selected.
- Separate Gemini-grounded search for used-market offers; if none is found, used value stays null and is queued for review.
- Evaluation templates, architecture note, and failure-log template.
- 15 regression tests cover packet calculations, repeated non-book sightings, grounded prices/page verification, non-book price integrity, voice corrections, RoomPlan import and irregular room handling.

## Known gaps — do not claim these are complete

- The companion is not merged into the reference app's Gemini Live WebSocket/ADK voice session. Browser speech input/output is not equivalent to the original Gemini Live conversation.
- The required ground-truth sweep (60+ books, 2+ shelving units, 8+ non-book items), tape measurements, 20 spine measurements, 15 hand-checked prices, measured pass-bar results, unedited demo video, and actual sweep packet/frames still need to be produced by running the app on a real space.
- RoomPlan summary import is now connected to the browser backend, but the iOS companion has not been compiled or device-tested, is not integrated with browser camera capture as one continuous native sweep, and does not calculate shelved-wall area. This is not yet a completed pass on automatic room measurement.
- Browser speech recognition/synthesis is not the same as full-duplex Gemini Live voice, and the existing reference app's Live session is not integrated into the companion sweep.
- Gemini-grounded price retrieval now includes direct cited-page verification and is covered by mocked tests, but live pricing has not been tested with the user's API key. Exact edition, stock, shipping and condition still require human verification. Non-book price ranges are attempted with grounded batch searches and direct cited-page checks, but live coverage is unverified and unknown items remain blank.
- Actual API cost and stage latency need to be measured from a real run. Do not invent them.
- Do not claim the assignment's accuracy pass bars have been met until the evaluation sheet is populated from ground truth.

## Integrity rule

Keep all unknowns blank/null and in the review queue. Do not submit sample/template rows as measured results. Replace the evaluation templates only with your own observations and sourced prices.


## RoomPlan integration update
The native SwiftUI RoomPlan companion now includes backend URL + active sweep ID fields and posts metric geometry to `/api/sweep/room-measurement`; the browser shows the active sweep ID. Added an XcodeGen `project.yml`, app entry point, Info.plist camera/local-network permissions and companion setup instructions. This is code-level integration only: it still needs an Xcode build and a real supported-device test, plus tape-measure ground-truth checks. Do not mark the room-area pass bars complete until the evaluation CSV contains measured results.

## Final revision note (2026-10-18)
- Book replacement-price search now also requests published physical dimensions from Google Search-grounded sources when available. The JSON packet records those dimensions with source URL and retrieval date; the HTML report displays them separately from camera-calibrated spine dimensions.
- Published book dimensions are specifications for a product/edition, not measurements of the individual copy. They do not determine room length.
- Shelf run is calculated only by summing calibrated spine thicknesses. Room length/width/height must come from RoomPlan/AR measurement or tape measurements. Adding book widths and a few inches estimates at most the shelf run and cannot validly infer the room's length.
- Automated regression suite: 15 passed after this revision. Physical iPhone RoomPlan integration and real-world accuracy pass bars remain unverified.
