#!/usr/bin/env python3
"""Compute assignment pass-bar metrics from completed ground-truth CSVs and a claim packet.

This script never fills missing ground truth. Blank/incomplete measurements are reported as
NOT EVALUATED rather than counted as passing. Run from the project root after the real sweep.
"""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

def rows(path: Path) -> list[dict[str, str]]:
    if not path.exists(): return []
    with path.open(newline="", encoding="utf-8-sig") as f: return list(csv.DictReader(f))

def truthy(v: Any) -> bool:
    return str(v or "").strip().casefold() in {"1", "true", "yes", "y", "correct", "pass"}

def number(v: Any) -> float | None:
    try:
        if v is None or str(v).strip() == "": return None
        return float(v)
    except (TypeError, ValueError): return None

def pct_error(actual: float, truth: float) -> float | None:
    return abs(actual - truth) / abs(truth) * 100 if truth else None

def metric(name: str, value: float | None, threshold: float, direction: str = "min", unit: str = "%") -> dict[str, Any]:
    if value is None: return {"measure": name, "value": None, "pass_bar": f"{direction} {threshold}{unit}", "status": "NOT EVALUATED"}
    passed = value >= threshold if direction == "min" else value <= threshold
    return {"measure": name, "value": round(value, 3), "pass_bar": f"{direction} {threshold}{unit}", "status": "PASS" if passed else "FAIL"}

def evaluate(base: Path, packet_path: Path | None) -> dict[str, Any]:
    books = rows(base / "ground_truth_books.csv")
    nonbooks = rows(base / "ground_truth_nonbooks.csv")
    prices = rows(base / "ground_truth_prices.csv")
    rooms = rows(base / "room_measurements.csv")
    metrics: list[dict[str, Any]] = []
    if books:
        true_count = len([r for r in books if r.get("ground_truth_present", "true").strip().casefold() not in {"false", "0", "no"}])
        sys_count = sum(1 for r in books if truthy(r.get("system_detected")) or any(str(r.get(k, "")).strip() for k in ("system_title", "system_author", "system_height_cm", "system_thickness_cm")))
        count_error = pct_error(sys_count, true_count) if true_count else None
        count_accuracy = 100 - count_error if count_error is not None else None
        metrics.append(metric("Book count within 5%", count_accuracy, 95, "min"))
        legible = [r for r in books if truthy(r.get("legible_spine"))]
        correct = 0
        confident_wrong = 0
        for r in legible:
            explicit = r.get("correct_title", "").strip()
            sys_title, gt_title = r.get("system_title", "").strip().casefold(), r.get("title_as_read", "").strip().casefold()
            is_correct = truthy(explicit) if explicit else bool(sys_title and gt_title and sys_title == gt_title)
            correct += int(is_correct)
            confidence = number(r.get("system_confidence"))
            if not is_correct and confidence is not None and confidence >= 0.8: confident_wrong += 1
        metrics.append(metric("Legible title identification accuracy", correct / len(legible) * 100 if legible else None, 70, "min"))
        metrics.append(metric("Confidently wrong titles", confident_wrong / len(legible) * 100 if legible and all(number(r.get("system_confidence")) is not None for r in legible) else None, 3, "max"))
        dimension_errors = []
        for r in books:
            for hand_key, system_key in (("hand_height_cm", "system_height_cm"), ("hand_thickness_cm", "system_thickness_cm")):
                hand, system = number(r.get(hand_key)), number(r.get(system_key))
                if hand is not None and system is not None and hand > 0:
                    err = pct_error(system, hand)
                    if err is not None: dimension_errors.append(err)
        mean_error = sum(dimension_errors) / len(dimension_errors) if dimension_errors else None
        metrics.append(metric("Mean spine dimension accuracy", 100-mean_error if mean_error is not None else None, 85, "min"))
    else:
        metrics.extend(metric(n, None, t, d) for n,t,d in [("Book count within 5%",95,"min"),("Legible title identification accuracy",70,"min"),("Confidently wrong titles",3,"max"),("Mean spine dimension accuracy",85,"min")])

    if prices:
        checked = []
        for r in prices:
            hand, system = number(r.get("hand_checked_replacement_price")), number(r.get("system_replacement_price"))
            same_source = not r.get("source_type") or not r.get("system_source_type") or r.get("source_type", "").strip().casefold() == r.get("system_source_type", "").strip().casefold()
            if hand is not None and system is not None and hand > 0 and same_source:
                err = pct_error(system, hand)
                if err is not None: checked.append(err <= 25)
        metrics.append(metric("Book prices within 25% (same source type)", sum(checked) / len(checked) * 100 if checked else None, 100, "min"))
    else: metrics.append(metric("Book prices within 25% (same source type)", None, 100, "min"))

    if nonbooks:
        found = [r for r in nonbooks if truthy(r.get("system_detected"))]
        recall = len(found) / len(nonbooks) * 100 if nonbooks else None
        correct = sum(1 for r in found if (r.get("correct_category") or "").strip() and (r.get("system_category") or "").strip().casefold() == r.get("correct_category", "").strip().casefold())
        category_accuracy = correct / len(found) * 100 if found and all((r.get("correct_category") or "").strip() for r in found) else None
        metrics.append(metric("Non-book recall", recall, 80, "min"))
        metrics.append(metric("Non-book category accuracy", category_accuracy, 80, "min"))
        combined = correct / len(nonbooks) * 100 if nonbooks and all((r.get("correct_category") or "").strip() for r in nonbooks) else None
        metrics.append(metric("Non-book items found with correct category", combined, 80, "min"))
    else:
        metrics.append(metric("Non-book recall", None, 80, "min"))
        metrics.append(metric("Non-book category accuracy", None, 80, "min"))
        metrics.append(metric("Non-book items found with correct category", None, 80, "min"))

    if rooms:
        r = rooms[0]
        floor = number(r.get("floor_error_percent"))
        wall = number(r.get("wall_error_percent"))
        if floor is None:
            hand, system = number(r.get("tape_floor_area_m2")), number(r.get("system_floor_area_m2"))
            floor = pct_error(system, hand) if system is not None and hand is not None else None
        if wall is None:
            hand, system = number(r.get("tape_wall_area_m2")), number(r.get("system_wall_area_m2"))
            wall = pct_error(system, hand) if system is not None and hand is not None else None
        metrics.append(metric("Floor area error", 100-floor if floor is not None else None, 90, "min"))
        metrics.append(metric("Wall area error", 100-wall if wall is not None else None, 85, "min"))
    else:
        metrics.append(metric("Floor area error", None, 90, "min"))
        metrics.append(metric("Wall area error", None, 85, "min"))

    packet_seconds = None
    if packet_path and packet_path.exists():
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        perf = packet.get("performance", {})
        packet_seconds = number(perf.get("total_finalize_ms"))
        if packet_seconds is not None: packet_seconds /= 1000
    metrics.append(metric("Time to packet after sweep", 100 if packet_seconds is not None and packet_seconds < 300 else (0 if packet_seconds is not None else None), 100, "min", " score"))
    if packet_seconds is not None: metrics[-1]["value_seconds"] = round(packet_seconds, 3)
    return {"metrics": metrics, "summary": "PASS ALL" if metrics and all(m["status"] == "PASS" for m in metrics) else "NOT ALL PASS / INCOMPLETE", "ground_truth_rows": {"books": len(books), "nonbooks": len(nonbooks), "prices": len(prices), "room_measurements": len(rooms)}}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, help="Path to a real generated claim_packet.json")
    parser.add_argument("--evaluation-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.evaluation_dir, args.packet), indent=2))
