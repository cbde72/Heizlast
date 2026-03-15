from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest

from heizlast.configs.project_config import ProjectCfg
from heizlast.core.anchors import update_edge_anchor_meta
from heizlast.domain.house_state import HouseState
from heizlast.domain.models import ElementModel, RoomModel
from heizlast.domain.services.house_domain_service import HouseDomainService
from heizlast.domain.services.room_operation_service import RoomOperationService


def _make_room_rect(room_id: str = 'R1', x: float = 0.0, y: float = 0.0, w: float = 4.0, h: float = 3.0, *, floor: str = 'EG', name: str | None = None) -> RoomModel:
    return RoomModel(id=room_id, floor=floor, name=name or room_id, x_m=x, y_m=y, w_m=w, h_m=h)


def _make_room_poly(room_id: str = 'P1', points: list[tuple[float, float]] | None = None, *, floor: str = 'EG', name: str | None = None) -> RoomModel:
    pts = points or [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (2.0, 2.0), (2.0, 4.0), (0.0, 4.0)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    r = RoomModel(id=room_id, floor=floor, name=name or room_id, x_m=min(xs), y_m=min(ys), w_m=max(xs) - min(xs), h_m=max(ys) - min(ys))
    r.set_polygon_points(list(pts))
    return r


def _make_window_on_edge(room_id: str, *, floor: str = 'EG', uid: str = 'win_1', orient: str = 'V', c: float = 4.0, a0: float = 0.0, a1: float = 4.0, center: float = 1.5, width: float = 1.0, rooms: tuple[str, ...] | None = None) -> ElementModel:
    if orient.upper().startswith('H'):
        x0, y0, x1, y1 = center - 0.5 * width, c, center + 0.5 * width, c
    else:
        x0, y0, x1, y1 = c, center - 0.5 * width, c, center + 0.5 * width
    meta = update_edge_anchor_meta('', parent='edge_1', orient=orient, c=c, a0=a0, a1=a1, s=center, w=width, rooms=rooms or (room_id,))
    return ElementModel(
        room_id=room_id,
        floor=floor,
        element_type='Fenster',
        area_m2=max(0.2, width * 1.0),
        u_w_m2k=1.2,
        x0_m=x0,
        y0_m=y0,
        x1_m=x1,
        y1_m=y1,
        length_m=width,
        height_m=1.0,
        uid=uid,
        meta=meta,
    )


def _make_state(*rooms: RoomModel, elements: list[ElementModel] | None = None) -> HouseState:
    return HouseState(rooms={r.id: r for r in rooms}, elements=list(elements or []), project_cfg=ProjectCfg())


def _make_service() -> RoomOperationService:
    return RoomOperationService(domain=HouseDomainService(), build_auto_walls=None)


@pytest.fixture
def make_room_rect():
    return _make_room_rect


@pytest.fixture
def make_room_poly():
    return _make_room_poly


@pytest.fixture
def make_window_on_edge():
    return _make_window_on_edge


@pytest.fixture
def make_state():
    return _make_state


@pytest.fixture
def make_service():
    return _make_service


@pytest.fixture
def room_rect():
    return _make_room_rect()


@pytest.fixture
def room_poly():
    return _make_room_poly()


@pytest.fixture
def service():
    return _make_service()
