# Last-run validation report

Run date: 2026-10-18  
Project: Library Contents Claim Agent

## Automated checks executed

- `pytest -q`: **22 passed**.
- `python -m py_compile app.py src/packet.py`: passed.
- `node --check live_demo/app.js`: passed.

These checks validate the current automated test suite and syntax only. They do not establish the real-world assessment pass bars.

## Live inference and pricing status

A previous attempt to call `/api/sweep/frame` with supplied photos failed with HTTP 400 because `GOOGLE_API_KEY` was not configured. No live Gemini title recognition, object detection, physical dimensions, or automated prices are claimed as validated. Configure a private `.env` from `.env.example` and rerun on the target device to test these flows.

## Fixture-only checks (not real-world measurements)

The deterministic tests exercise preservation of English/Hindi text, storage of separately sourced replacement/used prices, shelf-run arithmetic, and room-geometry arithmetic. Example fixture values used by tests are synthetic and must not be presented as measurements or live price results.

## Current pass-bar status

| Criterion | Status | Reason |
|---|---|---|
| Automated tests | PASS | 22 tests passed |
| Python syntax | PASS | Compile check passed |
| Browser JavaScript syntax | PASS | Node syntax check passed |
| English title accuracy | NOT EVALUATED | No live inference with annotated ground truth |
| Hindi title accuracy | NOT EVALUATED | No validated Hindi image run |
| Spine dimensions within target tolerance | NOT EVALUATED | Real ruler measurements required |
| 15 prices within target error | NOT EVALUATED | Live source-backed results and hand checks required |
| Shelf run | FORMULA TESTED; REAL VALUE NOT VALIDATED | Requires calibrated individual spine thicknesses |
| Room/floor/wall area | FORMULA TESTED; REAL ROOM NOT VALIDATED | Requires RoomPlan/tape ground truth; browser camera alone cannot infer metres |
| Non-book detection | NOT EVALUATED | Requires live inference and labelled ground truth |
| Native iOS RoomPlan build/device integration | NOT VERIFIED | Requires Xcode build and supported physical Apple device |
| Gemini Live full-duplex voice integration | NOT COMPLETE | Browser speech is not equivalent to the reference Gemini Live session |

## Submission integrity

Do not describe this prototype as 100% assessment-complete. The code checks pass, but several assessment criteria require real-device integration and evidence gathered from a measured space. Keep unknown values blank/null and do not invent pass-bar results, prices, measurements, cost, or latency.
