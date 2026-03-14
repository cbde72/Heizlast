from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from heizlast.configs.project_config import ProjectCfg
from heizlast.core.anchors import parse_edge_anchor
from heizlast.core.polygon_ops import serialize_polygon_m
from heizlast.domain.house_state import HouseState
from heizlast.domain.models import ElementModel, RoomModel
from heizlast.domain.services.house_domain_service import HouseDomainService
from heizlast.domain.services.room_operation_service import RoomOperationService


def rect_room(room_id: str, x: float, y: float, w: float, h: float, *, floor: str = 'EG', name: str | None = None) -> RoomModel:
    return RoomModel(id=room_id, floor=floor, name=name or room_id, x_m=x, y_m=y, w_m=w, h_m=h)


def window_on_vertical_edge(room_id: str, x: float, y0: float, y1: float, *, floor: str = 'EG', uid: str = 'win_1', rooms: str | None = None) -> ElementModel:
    width = abs(y1 - y0)
    center = 0.5 * (y0 + y1)
    meta = f'parent=edge_1|orient=V|c={x:.3f}|a0=0.000|a1=4.000|s={center:.4f}|w={width:.4f}'
    if rooms is not None:
        meta += f'|rooms={rooms}'
    return ElementModel(
        room_id=room_id,
        floor=floor,
        element_type='Fenster',
        area_m2=1.0,
        u_w_m2k=1.2,
        x0_m=x,
        y0_m=y0,
        x1_m=x,
        y1_m=y1,
        length_m=width,
        uid=uid,
        meta=meta,
    )


def make_state(*rooms: RoomModel, elements: list[ElementModel] | None = None) -> HouseState:
    return HouseState(rooms={r.id: r for r in rooms}, elements=list(elements or []), project_cfg=ProjectCfg())


def service() -> RoomOperationService:
    return RoomOperationService(domain=HouseDomainService(), build_auto_walls=None)


def test_split_room_reanchors_window_and_supports_undo_redo():
    room = rect_room('R1', 0.0, 0.0, 4.0, 4.0)
    win = window_on_vertical_edge('R1', 4.0, 1.0, 2.0, rooms='R1')
    state = make_state(room, elements=[win])

    rec = service().split_room(state, 'R1', orientation='v', coord=2.0)
    assert rec is not None
    assert set(state.rooms.keys()) == {'R1', 'R1_2'}
    assert state.elements[0].room_id == 'R1_2'
    assert float(state.elements[0].x0_m) == 4.0
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



def test_merge_rooms_keeps_first_id_and_reanchors_window_to_merged_room():
    a = rect_room('A', 0.0, 0.0, 2.0, 4.0)
    b = rect_room('B', 2.0, 0.0, 2.0, 4.0)
    win = window_on_vertical_edge('B', 4.0, 1.0, 2.0, rooms='B')
    state = make_state(a, b, elements=[win])

    rec = service().merge_rooms(state, ['A', 'B'])
    assert rec is not None
    assert set(state.rooms.keys()) == {'A'}
    merged = state.rooms['A']
    assert round(merged.w_m, 6) == 4.0
    assert state.elements[0].room_id == 'A'
    anchor = parse_edge_anchor(state.elements[0].meta)
    assert anchor['orient'] == 'V'
    assert float(anchor['c']) == 4.0



def test_subtract_rooms_keeps_base_id_and_reanchors_remaining_window():
    base = rect_room('BASE', 0.0, 0.0, 4.0, 4.0)
    cutter = rect_room('CUT', 2.0, 0.0, 2.0, 4.0)
    left_win = window_on_vertical_edge('BASE', 0.0, 1.0, 2.0, rooms='BASE')
    cut_win = window_on_vertical_edge('CUT', 4.0, 1.0, 2.0, uid='win_cut', rooms='CUT')
    state = make_state(base, cutter, elements=[left_win, cut_win])

    rec = service().subtract_rooms(state, 'BASE', ['CUT'])
    assert rec is not None
    assert set(state.rooms.keys()) == {'BASE'}
    base_after = state.rooms['BASE']
    assert round(base_after.w_m, 6) == 2.0
    assert len(state.elements) == 1
    assert state.elements[0].uid == 'win_1'
    assert state.elements[0].room_id == 'BASE'
    anchor = parse_edge_anchor(state.elements[0].meta)
    assert anchor['orient'] == 'V'
    assert float(anchor['c']) == 0.0
