from heizlast.core.anchors import dump_meta, update_edge_anchor_meta
from heizlast.core.wall_openings import opening_geometry_from_element, wall_openings_for_element
from heizlast.domain.models import ElementModel, RoomModel


def _wall(uid='wall_1'):
    return ElementModel(
        room_id='R1', element_type='Außenwand', area_m2=10.0, u_w_m2k=0.2,
        floor='EG', x0_m=0.0, y0_m=0.0, x1_m=4.0, y1_m=0.0, length_m=4.0, height_m=2.6, uid=uid
    )


def test_window_uses_exact_sill_from_meta():
    meta = update_edge_anchor_meta('', parent='wall_1', orient='H', c=0.0, a0=0.0, a1=4.0, s=1.5, w=1.2, rooms=('R1',))
    meta += '|bruestung_m=1.10'
    win = ElementModel(room_id='R1', element_type='Fenster', area_m2=1.2, u_w_m2k=1.1, floor='EG', x0_m=0.9, y0_m=0.0, x1_m=2.1, y1_m=0.0, length_m=1.2, height_m=1.3, uid='win_1', meta=meta)
    sill_m, height_m = opening_geometry_from_element(win, default_sill_m=0.9)
    assert sill_m == 1.10
    assert height_m == 1.3


def test_door_is_included_with_zero_default_sill():
    wall = _wall()
    meta = update_edge_anchor_meta('', parent='wall_1', orient='H', c=0.0, a0=0.0, a1=4.0, s=0.6, w=1.0, rooms=('R1',))
    door = ElementModel(room_id='R1', element_type='Tür', area_m2=2.01, u_w_m2k=1.8, floor='EG', x0_m=0.1, y0_m=0.0, x1_m=1.1, y1_m=0.0, length_m=1.0, height_m=2.01, uid='door_1', meta=meta)
    openings = wall_openings_for_element(wall, [door], room=RoomModel(id='R1', floor='EG', name='R1', x_m=0, y_m=0, w_m=4, h_m=3))
    assert len(openings) == 1
    assert openings[0].opening_type == 'door'
    assert openings[0].sill_m == 0.0
    assert abs(openings[0].offset_m - 0.1) < 1e-9


def test_right_gap_can_be_derived_from_opening_data():
    wall = _wall()
    meta = dump_meta({'parent': 'wall_1', 'orient': 'H', 'c': '0.000', 'a0': '0.000', 'a1': '4.000', 's': '2.0000', 'w': '1.0000', 'rooms': 'R1'})
    win = ElementModel(room_id='R1', element_type='Fenster', area_m2=1.2, u_w_m2k=1.1, floor='EG', x0_m=1.5, y0_m=0.0, x1_m=2.5, y1_m=0.0, length_m=1.0, height_m=1.2, uid='win_2', meta=meta)
    openings = wall_openings_for_element(wall, [win], room=RoomModel(id='R1', floor='EG', name='R1', x_m=0, y_m=0, w_m=4, h_m=3))
    assert len(openings) == 1
    op = openings[0]
    right_gap = wall.length_m - op.offset_m - op.width_m
    assert right_gap == 1.5
