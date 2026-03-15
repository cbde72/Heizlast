from __future__ import annotations


def test_undo_redo_chain_split_merge(make_room_rect, make_window_on_edge, make_state, make_service):
    room = make_room_rect('R1', 0.0, 0.0, 4.0, 4.0)
    win = make_window_on_edge('R1', c=4.0, a0=0.0, a1=4.0, center=1.5, width=1.0, rooms=('R1',), uid='W1')
    state = make_state(room, elements=[win])
    srv = make_service()

    rec1 = srv.split_room(state, 'R1', orientation='v', coord=2.0)
    assert set(state.rooms.keys()) == {'R1', 'R1_2'}

    rec2 = srv.merge_rooms(state, ['R1', 'R1_2'])
    assert set(state.rooms.keys()) == {'R1'}
    assert state.elements[0].room_id == 'R1'

    rec2.undo(state)
    assert set(state.rooms.keys()) == {'R1', 'R1_2'}
    rec1.undo(state)
    assert set(state.rooms.keys()) == {'R1'}
    assert state.elements[0].room_id == 'R1'

    rec1.redo(state)
    assert set(state.rooms.keys()) == {'R1', 'R1_2'}
    rec2.redo(state)
    assert set(state.rooms.keys()) == {'R1'}
    assert state.elements[0].room_id == 'R1'


def test_undo_redo_chain_subtract(make_room_rect, make_window_on_edge, make_state, make_service):
    base = make_room_rect('BASE', 0.0, 0.0, 4.0, 4.0)
    cutter = make_room_rect('CUT', 2.0, 0.0, 2.0, 4.0)
    left_win = make_window_on_edge('BASE', c=0.0, a0=0.0, a1=4.0, center=1.5, width=1.0, rooms=('BASE',), uid='WL')
    state = make_state(base, cutter, elements=[left_win])
    srv = make_service()

    rec = srv.subtract_rooms(state, 'BASE', ['CUT'])
    assert set(state.rooms.keys()) == {'BASE'}
    assert round(state.rooms['BASE'].w_m, 6) == 2.0

    rec.undo(state)
    assert set(state.rooms.keys()) == {'BASE', 'CUT'}
    rec.redo(state)
    assert set(state.rooms.keys()) == {'BASE'}
