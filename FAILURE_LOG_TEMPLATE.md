# Failure log — fill after the recorded run

Do not claim these are measured failures until you observe them in your real run.

| Rank | Observed failure (frame/item) | Impact | Root cause evidence | Fix attempted | Before metric | After metric |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |

## Latency

Record actual wall-clock times for camera capture, Gemini vision per frame, pricing lookups, packet assembly and total time-to-packet. The app logs frame-vision latency in the packet. Do not substitute estimated timing.

## Cost

Read provider billing/usage for the test period, separate unrelated requests, and report the measured marginal cost for this sweep. The app leaves `cost_usd_estimate` null until you have a defensible measurement.

## What I would change with two more weeks

- 
