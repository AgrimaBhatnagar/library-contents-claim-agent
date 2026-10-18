from __future__ import annotations
from datetime import datetime, timezone
from html import escape
from typing import Any


def build_packet(session: dict[str, Any], room_input: dict[str, Any]) -> dict[str, Any]:
    sweep = dict(session["sweep"])
    L, W, H = room_input.get("length_m"), room_input.get("width_m"), room_input.get("height_m")
    floor_input, wall_input = room_input.get("floor_area_m2"), room_input.get("wall_area_m2")
    shape = room_input.get("shape") or "rectangular"
    floor = round(float(floor_input), 3) if isinstance(floor_input, (int, float)) and floor_input >= 0 else (round(L * W, 3) if L is not None and W is not None and shape == "rectangular" else None)
    wall = round(float(wall_input), 3) if isinstance(wall_input, (int, float)) and wall_input >= 0 else (round(2 * (L + W) * H, 3) if None not in (L, W, H) and shape == "rectangular" else None)
    room = {"length_m": L, "width_m": W, "height_m": H, "floor_area_m2": floor,
            "floor_area_ft2": round(floor * 10.7639, 2) if floor is not None else None,
            "wall_area_m2": wall, "wall_area_ft2": round(wall * 10.7639, 2) if wall is not None else None,
            "shelved_wall_area_m2": room_input.get("shelved_wall_area_m2"),
            "shape": shape,
            "scale_method": room_input.get("scale_method") or "Not supplied", "confidence": room_input.get("scale_confidence", 0)}
    books = [dict(b) for b in session["books"]]
    items = [dict(i) for i in session["items"]]
    review = []
    for b in books:
        if not b.get("frame_ref"):
            review.append({"ref_id": b["id"], "reason": "Missing saved evidence frame."})
        if b.get("status") == "unidentified":
            review.append({"ref_id": b["id"], "reason": "Spine text not reliably legible; title intentionally left blank."})
        if b.get("excluded_by_user"):
            review.append({"ref_id": b["id"], "reason": "User excluded this item from claim totals; retained for audit."})
        if b.get("spine_height_cm") is None or b.get("spine_thickness_cm") is None:
            review.append({"ref_id": b["id"], "reason": "Physical dimensions not calibrated; do not infer centimetres from pixels."})
        if not b.get("title"):
            b["status"] = "unidentified" if b.get("status") != "needs_appraisal" else b["status"]
    for it in items:
        if any(k in (it.get("category", "") or "").lower() for k in ("art", "portrait", "painting", "picture")) and not it.get("print_confirmed"):
            it["status"] = "needs_appraisal"
            review.append({"ref_id": it["id"], "reason": "Art/portrait requires confirmation that it is a print or human appraisal."})
        if not it.get("replacement_cost", {}).get("source"):
            review.append({"ref_id": it["id"], "reason": "No verifiable local replacement-price source; price left blank."})
        if not it.get("frame_ref"):
            review.append({"ref_id": it["id"], "reason": "Missing saved evidence frame."})
        if it.get("excluded_by_user"):
            review.append({"ref_id": it["id"], "reason": "User excluded this item from claim totals; retained for audit."})
    priced_replacement = [b["replacement_cost"].get("amount") for b in books if not b.get("excluded_by_user") and isinstance(b.get("replacement_cost", {}).get("amount"), (int,float)) and b.get("status") != "needs_appraisal"]
    priced_used = [b["used_value"].get("amount") for b in books if not b.get("excluded_by_user") and isinstance(b.get("used_value", {}).get("amount"), (int,float)) and b.get("status") != "needs_appraisal"]
    item_lows = [i["replacement_cost"].get("low") for i in items if not i.get("excluded_by_user") and isinstance(i.get("replacement_cost", {}).get("low"), (int,float)) and i.get("status") != "needs_appraisal"]
    item_highs = [i["replacement_cost"].get("high") for i in items if not i.get("excluded_by_user") and isinstance(i.get("replacement_cost", {}).get("high"), (int,float)) and i.get("status") != "needs_appraisal"]
    excluded = sum(1 for b in books if b.get("status") == "needs_appraisal") + sum(1 for i in items if i.get("status") == "needs_appraisal")
    calibrated_thicknesses = [b["spine_thickness_cm"] for b in books if not b.get("excluded_by_user") and isinstance(b.get("spine_thickness_cm"), (int,float)) and b["spine_thickness_cm"] > 0]
    total_thickness = sum(calibrated_thicknesses)
    totals = {"book_count": len(books), "books_with_calibrated_thickness": len(calibrated_thicknesses), "books_identified": sum(1 for b in books if b.get("status") == "identified" and b.get("title")),
              "books_unidentified": sum(1 for b in books if b.get("status") == "unidentified"), "shelf_run_m": round(total_thickness / 100, 3),
              "books_replacement_cost": round(sum(priced_replacement), 2) if priced_replacement else None,
              "books_used_value": round(sum(priced_used), 2) if priced_used else None,
              "items_replacement_cost_low": round(sum(item_lows), 2) if item_lows else None,
              "items_replacement_cost_high": round(sum(item_highs), 2) if item_highs else None,
              "excluded_from_totals": excluded}
    return {"schema_version": "1.0", "sweep": sweep, "room": room, "books": books, "items": items, "totals": totals,
            "review_queue": review, "created_at": datetime.now(timezone.utc).isoformat(),
            "assumptions": ["Room is treated as rectangular for area calculations unless separately documented.",
                "Missing prices and measurements remain null and are excluded from totals.",
                "Vision-generated bounding boxes do not provide metric dimensions without a calibrated scale.",
                "Published book dimensions from web listings are product specifications only; they do not determine room length or replace same-plane calibrated spine measurements."]}


def render_html_report(packet: dict[str, Any]) -> str:
    esc = escape
    s, room, totals = packet["sweep"], packet["room"], packet["totals"]
    def money(v): return "Not verified" if v is None else f"{v:,.2f}"
    def book_price_cell(b):
        price = money(b.get('replacement_cost', {}).get('amount'))
        evidence = b.get('replacement_cost', {})
        source = esc(str(evidence.get('source', '')))
        url = evidence.get('url', '')
        if url.startswith(('https://', 'http://')):
            source += f"<br><a href=\"{esc(url)}\" target=\"_blank\" rel=\"noopener\">Price source</a>"
        links = b.get('price_search_links', [])
        if links:
            source += '<br><b>Verify a listing:</b> ' + ' · '.join(f"<a href=\"{esc(x['url'])}\" target=\"_blank\" rel=\"noopener\">{esc(x['source'])}</a>" for x in links)
        return f"{price}<br>{source}" if source else f"{price}<br><span>Source not found; use search links below if available.</span>"
    def used_price_cell(b):
        evidence = b.get("used_value", {})
        price = money(evidence.get("amount"))
        source = esc(str(evidence.get("source", "")))
        url = evidence.get("url", "")
        if url.startswith(("https://", "http://")):
            source += f"<br><a href=\"{esc(url)}\" target=\"_blank\" rel=\"noopener\">Used-price source</a>"
        return f"{price}<br>{source}<br><small>{esc(str(evidence.get('retrieved_at','')))} · {esc(str(evidence.get('condition_assumed','')))}</small>"
    def frame_link(ref):
        ref = str(ref or "")
        if ref.startswith("/api/frames/"):
            return f"<a href=\"{esc(ref)}\" target=\"_blank\" rel=\"noopener\">Open evidence frame</a>"
        return esc(ref or "Missing frame")
    def publisher_dims_cell(b):
        d = b.get("publisher_dimensions") or {}
        if not d:
            return "Not found in grounded source"
        parts = [f"{k.replace('_cm','')} {v} cm" for k, v in (("width_cm", d.get("width_cm")), ("height_cm", d.get("height_cm")), ("thickness_cm", d.get("thickness_cm"))) if isinstance(v, (int, float))]
        url = d.get("url", "")
        link = f"<br><a href=\"{esc(url)}\" target=\"_blank\" rel=\"noopener\">Dimension source</a>" if url.startswith(("https://", "http://")) else ""
        return esc(" · ".join(parts)) + link + "<br><small>Published spec; not a measurement of this copy.</small>"
    book_rows = "".join(f"<tr><td>{esc(str(b.get('id','')))}</td><td>{esc(str(b.get('title') or 'Unidentified'))}</td><td>{esc(str(b.get('author') or ''))}</td><td>{publisher_dims_cell(b)}</td><td>{esc(str('excluded by user' if b.get('excluded_by_user') else b.get('status','')))}</td><td>{book_price_cell(b)}<br><small>Retrieved: {esc(str(b.get('replacement_cost',{}).get('retrieved_at','')))}</small></td><td>{used_price_cell(b)}</td><td>{frame_link(b.get('frame_ref'))}</td></tr>" for b in packet["books"])
    def item_price_cell(i):
        c = i.get("replacement_cost", {})
        price = "Not verified" if c.get("low") is None or c.get("high") is None else (f"{c.get('low'):,.2f}" if c.get("low") == c.get("high") else f"{c.get('low'):,.2f}–{c.get('high'):,.2f}")
        url = c.get("url", "")
        source = esc(str(c.get("source", "")))
        if url.startswith(("https://", "http://")): source += f"<br><a href=\"{esc(url)}\" target=\"_blank\" rel=\"noopener\">Price source</a>"
        return f"{price}<br>{source}<br><small>{esc(str(c.get('retrieved_at','')))}</small>"
    item_rows = "".join(f"<tr><td>{esc(str(i.get('id','')))}</td><td>{esc(str(i.get('category','')))}</td><td>{esc(str(i.get('description','')))}</td><td>{esc(str(i.get('dimensions_cm',{})))}<br><small>{esc(str(i.get('measurement_status','')))}</small></td><td>{esc(str('excluded by user' if i.get('excluded_by_user') else i.get('status','')))}</td><td>{item_price_cell(i)}</td><td>{frame_link(i.get('frame_ref'))}</td></tr>" for i in packet["items"])
    review_rows = "".join(f"<li><b>{esc(str(x.get('ref_id','')))}</b>: {esc(str(x.get('reason','')))}</li>" for x in packet["review_queue"])
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>Library Contents Claim Report</title><style>body{{font:15px/1.5 Arial,sans-serif;max-width:1200px;margin:32px auto;padding:0 20px;color:#222}}h1,h2{{color:#26384a}}table{{border-collapse:collapse;width:100%;margin:12px 0 28px}}td,th{{border:1px solid #ddd;padding:7px;text-align:left;vertical-align:top}}th{{background:#eef2f5}}.warn{{background:#fff6df;padding:12px;border-left:4px solid #d69e2e}}.stats{{display:flex;gap:12px;flex-wrap:wrap}}.stats div{{padding:12px;border:1px solid #ddd;min-width:140px}}</style></head><body><h1>Library Contents Claim Report</h1><p>Sweep {esc(s.get('id',''))} · captured {esc(s.get('captured_at',''))} · country {esc(s.get('country',''))} ({esc(s.get('currency',''))}) · duration {s.get('duration_s',0)} seconds</p><div class="warn">This report preserves unknown values as blank. It is a prototype inventory, not a verified insurance valuation. Review all flagged lines before submission.</div><h2>Summary</h2><div class="stats"><div><b>Books detected</b><br>{totals['book_count']}</div><div><b>Identified</b><br>{totals['books_identified']}</div><div><b>Unidentified</b><br>{totals['books_unidentified']}</div><div><b>Shelf run</b><br>{totals['shelf_run_m']} m from {totals.get('books_with_calibrated_thickness', 0)} measured books</div><div><b>Replacement total</b><br>{money(totals['books_replacement_cost'])}</div></div><h2>Room</h2><p>Dimensions: {room.get('length_m') if room.get('length_m') is not None else 'Not measured'} m × {room.get('width_m') if room.get('width_m') is not None else 'Not measured'} m × {room.get('height_m') if room.get('height_m') is not None else 'Not measured'} m. Floor: {room.get('floor_area_m2') if room.get('floor_area_m2') is not None else 'Not calculated'} m² / {room.get('floor_area_ft2') if room.get('floor_area_ft2') is not None else 'Not calculated'} ft². Total wall area: {room.get('wall_area_m2') if room.get('wall_area_m2') is not None else 'Not calculated'} m² / {room.get('wall_area_ft2') if room.get('wall_area_ft2') is not None else 'Not calculated'} ft². Shelved wall: {room.get('shelved_wall_area_m2') if room.get('shelved_wall_area_m2') is not None else 'Not measured'} m². Shape handling: {esc(str(room.get('shape','unknown')))}. Scale method: {esc(str(room.get('scale_method','')))}. Measurement confidence: {room.get('confidence',0)}.</p><h2>Books</h2><table><tr><th>ID</th><th>Title</th><th>Author</th><th>Published physical dimensions</th><th>Status</th><th>Replacement price</th><th>Used market value</th><th>Evidence frame</th></tr>{book_rows}</table><h2>Non-book items</h2><table><tr><th>ID</th><th>Category</th><th>Description</th><th>Dimensions (cm)</th><th>Status</th><th>Replacement price range</th><th>Evidence frame</th></tr>{item_rows}</table><h2>Review queue ({len(packet['review_queue'])})</h2><ul>{review_rows}</ul><h2>Second-country comparison</h2><table><tr><th>Book</th><th>Country</th><th>Currency</th><th>Replacement price</th><th>Source</th></tr>{''.join(f"<tr><td>{esc(str(x.get('title','')))}</td><td>{esc(str(x.get('country','')))}</td><td>{esc(str(x.get('currency','')))}</td><td>{money(x.get('replacement_cost',{}).get('amount'))}</td><td>{esc(str(x.get('replacement_cost',{}).get('url','')))}</td></tr>" for x in packet.get('second_country_comparison',[]))}</table><p>Generated at {esc(packet.get('created_at',''))}. Frame references are relative to the project folder.</p></body></html>'''


def recalculate_totals(packet: dict[str, Any]) -> None:
    """Recompute every aggregate from current line items after all price lookups."""
    books, items = packet.get("books", []), packet.get("items", [])
    repl = [b.get("replacement_cost", {}).get("amount") for b in books if b.get("status") != "needs_appraisal" and not b.get("excluded_by_user") and isinstance(b.get("replacement_cost", {}).get("amount"), (int, float))]
    used = [b.get("used_value", {}).get("amount") for b in books if b.get("status") != "needs_appraisal" and not b.get("excluded_by_user") and isinstance(b.get("used_value", {}).get("amount"), (int, float))]
    lows = [i.get("replacement_cost", {}).get("low") for i in items if i.get("status") != "needs_appraisal" and not i.get("excluded_by_user") and isinstance(i.get("replacement_cost", {}).get("low"), (int, float))]
    highs = [i.get("replacement_cost", {}).get("high") for i in items if i.get("status") != "needs_appraisal" and not i.get("excluded_by_user") and isinstance(i.get("replacement_cost", {}).get("high"), (int, float))]
    calibrated_thicknesses = [b.get("spine_thickness_cm") for b in books if not b.get("excluded_by_user") and isinstance(b.get("spine_thickness_cm"), (int, float)) and b.get("spine_thickness_cm") > 0]
    thickness = sum(calibrated_thicknesses)
    packet["totals"] = {"book_count": len(books), "books_with_calibrated_thickness": len(calibrated_thicknesses), "books_identified": sum(1 for b in books if b.get("status") == "identified" and b.get("title")),
        "books_unidentified": sum(1 for b in books if b.get("status") == "unidentified"), "shelf_run_m": round(thickness / 100, 3),
        "books_replacement_cost": round(sum(repl), 2) if repl else None, "books_used_value": round(sum(used), 2) if used else None,
        "items_replacement_cost_low": round(sum(lows), 2) if lows else None, "items_replacement_cost_high": round(sum(highs), 2) if highs else None,
        "excluded_from_totals": sum(1 for b in books if b.get("status") == "needs_appraisal" or b.get("excluded_by_user")) + sum(1 for i in items if i.get("status") == "needs_appraisal" or i.get("excluded_by_user"))}
