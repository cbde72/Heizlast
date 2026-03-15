from __future__ import annotations

from heizlast.core.anchors import parse_edge_anchor


def test_window_reanchors_to_right_split_room(make_room_rect, make_window_on_edge, make_state, make_service):
    room = make_room_rect('R1', 0.0, 0.0, 6.0, 4.0)
    win = make_window_on_edge('R1', c=6.0, a0=0.0, a1=4.0, center=2.0, width=1.0, rooms=('R1',), uid='W1')
    state = make_state(room, elements=[win])

    make_service().split_room(state, 'R1', orientation='v', coord=3.0)
    e = state.elements[0]
    a = parse_edge_anchor(e.meta)
    assert e.uid == 'W1'
    assert e.room_id == 'R1_2'
    assert a['orient'] == 'V'
    assert float(a['c']) == 6.0


def test_window_reanchors_to_merged_room_and_keeps_uid(make_room_rect, make_window_on_edge, make_state, make_service):
    a = make_room_rect('A', 0.0, 0.0, 2.0, 4.0)
    b = make_room_rect('B', 2.0, 0.0, 2.0, 4.0)
    win = make_window_on_edge('B', c=4.0, a0=0.0, a1=4.0, center=2.0, width=1.0, rooms=('B',), uid='W2')
    state = make_state(a, b, elements=[win])

    make_service().merge_rooms(state, ['A', 'B'])
    e = state.elements[0]
    a = parse_edge_anchor(e.meta)
    assert e.uid == 'W2'
    assert e.room_id == 'A'
    assert a['rooms'] == {'A'}


def test_subtract_removes_window_without_valid_target_edge(make_room_rect, make_window_on_edge, make_state, make_service):
    base = make_room_rect('BASE', 0.0, 0.0, 4.0, 4.0)
    cutter = make_room_rect('CUT', 2.0, 0.0, 2.0, 4.0)
    win_cut = make_window_on_edge('CUT', c=4.0, a0=0.0, a1=4.0, center=2.0, width=1.0, rooms=('CUT',), uid='W3')
    state = make_state(base, cutter, elements=[win_cut])

    make_service().subtract_rooms(state, 'BASE', ['CUT'])
    assert state.elements == []
