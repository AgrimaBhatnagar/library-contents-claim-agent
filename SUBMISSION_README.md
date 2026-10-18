# Library Contents Claim Agent — Submission Bundle

## What is included

- FastAPI + browser-camera prototype for live frame capture and Gemini vision extraction.
- Structured `claim_packet.json` and human-readable HTML report generation.
- Evidence-frame references, review queue, deterministic totals, grounded pricing attempts, voice correction commands, and room-measurement import endpoint.
- Native iOS RoomPlan companion source (`native_ios/RoomScan/`) for a supported Apple device.
- Regression tests, architecture notes, evaluator, and ground-truth templates.
- `evidence/latest_actual_sweep_report.md`: the actual report produced during the latest recorded sweep, included without alteration.

## Quick start (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python -m uvicorn app:app --reload --host 0.0.0.0 --port 4178
```

Set `GOOGLE_API_KEY` to a valid Google AI Studio API key and ensure `LIBRARY_VISION_MODEL` / `LIBRARY_PRICE_MODEL` are model IDs currently enabled for that key. Open `http://127.0.0.1:4178`. Run tests with `pip install -r requirements-dev.txt` then `pytest -q`.

## Verification performed in this bundle

- Automated regression suite: **15 passed** in the packaging environment.
- Python syntax compilation and ZIP integrity checks were run for the packaged source.
- These are software checks, not proof of real-scene accuracy or live pricing coverage.

## Important result honesty

The included actual sweep report contains 23 detected books (21 identified, 2 unidentified), but no verified replacement/used prices, no calibrated spine dimensions, no measured room dimensions/areas, no detected non-book items, and no second-country prices. Consequently, the assignment's accuracy pass bars are **not yet demonstrated**. Do not present this report as a fully passing evaluation. The code package is a prototype submission, not a verified complete solution.

The assignment's full ground-truth deliverables (60+ books across two shelving units, 8+ non-book items, 20 tape-measured spines, 15 hand-checked prices, room tape measurements, unedited demo video, and populated evaluation results) were not present in the available evidence at packaging time. The RoomPlan Swift source is included, but it still requires Xcode compilation and testing on a supported Apple device. The browser sweep and RoomPlan scan remain separate device workflows.

## Suggested reviewer demo

1. Start the companion server and show the live capture UI.
2. Show a saved frame and the generated inventory/claim packet.
3. Show a title correction via voice/text and the review queue.
4. Show the RoomPlan import path and explain it is code-level integration pending device validation.
5. Open `evidence/latest_actual_sweep_report.md` and clearly distinguish implemented paths from requirements not yet measured or passed.
