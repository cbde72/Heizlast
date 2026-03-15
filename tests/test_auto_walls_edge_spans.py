from __future__ import annotations

from heizlast.core.geometry import build_auto_walls_shared_merge, classify_floor_edge_spans


def test_two_adjacent_rect_rooms_create_one_shared_vertical_span(make_room_rect):
    a = make_room_rect('A', 0.0, 0.0, 2.0, 4.0)
    b = make_room_rect('B', 2.0, 0.0, 2.0, 4.0)
    spans = classify_floor_edge_spans([a, b])
    shared = [s for s in spans if s.element_type == 'Innenwand']
    assert len(shared) == 1
    s = shared[0]
    assert s.orient == 'V'
    assert float(s.c) == 2.0
    assert (float(s.a0), float(s.a1)) == (0.0, 4.0)
    assert set(s.room_ids) == {'A', 'B'}


def test_single_rect_room_creates_four_outer_spans(make_room_rect):
    r = make_room_rect('R1', 0.0, 0.0, 4.0, 3.0)
    spans = classify_floor_edge_spans([r])
    outer = [s for s in spans if s.element_type == 'Aussenwand']
    assert len(outer) == 4
    assert all(s.room_ids == ('R1',) for s in outer)


def test_l_room_creates_only_outer_spans_and_expected_count(make_room_poly):
    r = make_room_poly('L1')
    spans = classify_floor_edge_spans([r])
    outer = [s for s in spans if s.element_type == 'Aussenwand']
    assert len(outer) == 6
    assert len([s for s in spans if s.element_type == 'Innenwand']) == 0


def test_auto_wall_uids_are_deterministic_for_same_layout(make_room_rect):
    a1 = make_room_rect('A', 0.0, 0.0, 2.0, 4.0)
    b1 = make_room_rect('B', 2.0, 0.0, 2.0, 4.0)
    ids1 = [e.uid for e in build_auto_walls_shared_merge([a1, b1])]

    a2 = make_room_rect('A', 0.0, 0.0, 2.0, 4.0)
    b2 = make_room_rect('B', 2.0, 0.0, 2.0, 4.0)
    ids2 = [e.uid for e in build_auto_walls_shared_merge([a2, b2])]

    assert ids1 == ids2
    assert len(set(ids1)) == len(ids1)


def test_auto_wall_meta_contains_expected_anchor_fields(make_room_rect):
    r = make_room_rect('R1', 0.0, 0.0, 4.0, 3.0)
    elems = build_auto_walls_shared_merge([r])
    assert elems
    meta = elems[0].meta or ''
    assert 'line=' in meta
    assert 'orient=' in meta
    assert 'a0=' in meta
    assert 'a1=' in meta
    assert 'edge_uid=' in meta
