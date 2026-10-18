# Final submission checklist

Use this checklist before sending the take-home response.

- [ ] Push this code to a private GitHub repository and share access with the evaluator.
- [ ] Verify `.env` is excluded from Git and only `.env.example` is committed.
- [ ] Run the app from a clean environment using only the README instructions.
- [ ] Run `pytest -q`, `python -m py_compile app.py src/packet.py`, and `node --check live_demo/app.js`; save the output.
- [ ] Run a one-take, unedited demo (6 minutes or less) with audible agent voice, live inventory, and final packet.
- [ ] Capture at least 60 books across 2+ shelving units, 8+ non-book items, and one enclosed room with permission.
- [ ] Hand-count all books and hand-read every legible title; record all uncertain/missed items.
- [ ] Tape-measure 20 sample spines and room length, width, ceiling height, and shelved wall area.
- [ ] Hand-check 15 book prices using the same source type and record URLs, retrieval dates, condition assumptions, and currency.
- [ ] Populate all ground-truth CSVs and calculate each metric against the assignment's pass bars.
- [ ] Save the real `claim_packet.json`, readable report, and every evidence frame referenced by the packet.
- [ ] Measure and report latency per stage and cost per sweep from actual usage data.
- [ ] Complete the failure log with the three worst observed errors, root causes, and measured fixes.
- [ ] Confirm the architecture note accurately describes the actual implementation and scale source.
- [ ] Do not claim any unmeasured accuracy, costs, prices, dimensions, or successful end-to-end Gemini Live integration.
