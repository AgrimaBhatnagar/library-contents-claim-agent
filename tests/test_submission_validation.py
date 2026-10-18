"""Deterministic end-to-end validation fixtures; these are not live vision tests."""
from app import StartSweep, SpineDimensions, PriceEvidence, start_sweep, save_spine_dimensions, add_price_evidence, SESSIONS, import_room_measurement
from src.packet import build_packet


def test_bilingual_titles_preserved_and_calibrated_shelf_run():
    sid = start_sweep(StartSweep(country='India', currency='INR', device='validation fixture'))['sweep_id']
    SESSIONS[sid]['books'] = [
        {'id':'B001','title':'The Hobbit','author':'J. R. R. Tolkien','status':'identified','replacement_cost':{},'used_value':{}},
        {'id':'B002','title':'गोदान','author':'मुंशी प्रेमचंद','status':'identified','replacement_cost':{},'used_value':{}},
        {'id':'B003','title':'One of Us Is Lying','author':'Karen M. McManus','status':'identified','replacement_cost':{},'used_value':{}},
    ]
    for bid, h, t in [('B001',20.0,2.5),('B002',21.0,2.4),('B003',20.8,2.2)]:
        save_spine_dimensions(SpineDimensions(sweep_id=sid, book_id=bid, height_cm=h, thickness_cm=t, method='validation fixture / ruler values'))
    p = build_packet(SESSIONS[sid], {'length_m':4.2,'width_m':3.4,'height_m':2.7,'shape':'rectangular','scale_method':'test fixture, not a real room scan','scale_confidence':1.0})
    assert [b['title'] for b in p['books']] == ['The Hobbit','गोदान','One of Us Is Lying']
    assert p['totals']['shelf_run_m'] == 0.071
    assert p['room']['floor_area_m2'] == 14.28
    assert p['room']['wall_area_m2'] == 41.04


def test_replacement_and_used_prices_are_recorded_separately():
    sid = start_sweep(StartSweep(country='India', currency='INR', device='validation fixture'))['sweep_id']
    SESSIONS[sid]['books'] = [{'id':'B001','title':'गोदान','status':'identified','replacement_cost':{},'used_value':{}}]
    add_price_evidence(PriceEvidence(sweep_id=sid,target_id='B001',kind='book_replacement',amount=149,currency='INR',source='Fixture retailer listing',url='https://example.com/godan-new'))
    add_price_evidence(PriceEvidence(sweep_id=sid,target_id='B001',kind='book_used',amount=80,currency='INR',source='Fixture used listing',url='https://example.com/godan-used',condition_assumed='good'))
    b = SESSIONS[sid]['books'][0]
    assert b['replacement_cost']['amount'] == 149
    assert b['used_value']['amount'] == 80
    assert b['replacement_cost']['url'] != b['used_value']['url']


def test_room_import_rejects_missing_or_impossible_dimensions():
    sid = start_sweep(StartSweep(device='validation fixture'))['sweep_id']
    from fastapi import HTTPException
    try:
        import_room_measurement({'sweep_id':sid,'room':{'length_m':0,'width_m':3,'height_m':2.5,'confidence':0.9}})
        assert False, 'zero length should be rejected'
    except HTTPException as e:
        assert e.status_code == 400
