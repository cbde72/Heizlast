from __future__ import annotations

from heizlast.core.anchors import parse_edge_anchor


def test_split_room_reanchors_window_and_supports_undo_redo(make_room_rect, make_window_on_edge, make_state, make_service):
    room = make_room_rect('R1', 0.0, 0.0, 4.0, 4.0)
    win = make_window_on_edge('R1', c=4.0, a0=0.0, a1=4.0, center=1.5, width=1.0, rooms=('R1',))
    state = make_state(room, elements=[win])

    rec = make_service().split_room(state, 'R1', orientation='v', coord=2.0)
    assert rec is not None
    assert set(state.rooms.keys()) == {'R1', 'R1_2'}
    assert state.elements[0].room_id == 'R1_2'
    anchor = parse_edge_anchor(state.elements[0].meta)
    assert anchor['orient'] == 'V'
    assert float(anchor['c']) == 4.0
    assert 'R1_2' in (anchor.get('rooms') or set())

    rec.undo(state)
    assert set(state.rooms.keys()) == {'R1'}
    assert state.elements[0].room_id == 'R1'
    rec.redo(state)
    assert set(state.rooms.keys()) == {'R1', 'R1_2'}
    assert state.elements[0].room_id == 'R1_2'


def test_merge_rooms_keeps_first_id_and_reanchors_window_to_merged_room(make_room_rect, make_window_on_edge, make_state, make_service):
    a = make_room_rect('A', 0.0, 0.0, 2.0, 4.0)
    b = make_room_rect('B', 2.0, 0.0, 2.0, 4.0)
    win = make_window_on_edge('B', c=4.0, a0=0.0, a1=4.0, center=1.5, width=1.0, rooms=('B',))
    state = make_state(a, b, elements=[win])

    rec = make_service().merge_rooms(state, ['A', 'B'])
    assert rec is not None
    assert set(state.rooms.keys()) == {'A'}
    merged = state.rooms['A']
    assert round(merged.w_m, 6) == 4.0
    assert state.elements[0].room_id == 'A'
    anchor = parse_edge_anchor(state.elements[0].meta)
    assert anchor['orient'] == 'V'
    assert float(anchor['c']) == 4.0


def test_subtract_rooms_keeps_base_id_and_reanchors_remaining_window(make_room_rect, make_window_on_edge, make_state, make_service):
    base = make_room_rect('BASE', 0.0, 0.0, 4.0, 4.0)
    cutter = make_room_rect('CUT', 2.0, 0.0, 2.0, 4.0)
    left_win = make_window_on_edge('BASE', c=0.0, a0=0.0, a1=4.0, center=1.5, width=1.0, rooms=('BASE',), uid='win_left')
    cut_win = make_window_on_edge('CUT', c=4.0, a0=0.0, a1=4.0, center=1.5, width=1.0, uid='win_cut', rooms=('CUT',))
    state = make_state(base, cutter, elements=[left_win, cut_win])

    rec = make_service().subtract_rooms(state, 'BASE', ['CUT'])
    assert rec is not None
    assert set(state.rooms.keys()) == {'BASE'}
    base_after = state.rooms['BASE']
    assert round(base_after.w_m, 6) == 2.0
    assert len(state.elements) == 1
    assert state.elements[0].uid == 'win_left'
    assert state.elements[0].room_id == 'BASE'
    anchor = parse_edge_anchor(state.elements[0].meta)
    assert anchor['orient'] == 'V'
    assert float(anchor['c']) == 0.0
