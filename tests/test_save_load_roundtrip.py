from __future__ import annotations

from pathlib import Path

from heizlast.configs.project_config import ProjectCfg
from heizlast.core.anchors import parse_edge_anchor
from heizlast.domain.models import RoomModel
from heizlast.infrastructure.project_repo import ProjectRepository


def test_project_repository_roundtrip_preserves_polygon_and_window_meta(tmp_path, make_room_rect, make_room_poly, make_window_on_edge):
    repo = ProjectRepository(delimiter=';')
    r1 = make_room_rect('R1', 0.0, 0.0, 4.0, 3.0)
    r2 = make_room_poly('L1')
    win = make_window_on_edge('R1', c=4.0, a0=0.0, a1=3.0, center=1.5, width=1.0, rooms=('R1',))
    rooms_path = tmp_path / 'rooms.csv'

    repo.save(rooms_path, [r1, r2], [win], ProjectCfg())
    data = repo.load(rooms_path)

    assert sorted(r.id for r in data.rooms) == ['L1', 'R1']
    loaded_r1 = next(r for r in data.rooms if r.id == 'R1')
    loaded_r2 = next(r for r in data.rooms if r.id == 'L1')
    assert loaded_r1.polygon_m
    assert loaded_r2.polygon_m == r2.polygon_m
    assert len(data.elements) == 1
    a = parse_edge_anchor(data.elements[0].meta)
    assert a['orient'] == 'V'
    assert float(a['c']) == 4.0
    assert a['rooms'] == {'R1'}


def test_load_rooms_migrates_missing_polygon_field_via_roommodel(tmp_path):
    rooms_path = tmp_path / 'legacy_rooms.csv'
    rooms_path.write_text(
        'id;floor;name;x_m;y_m;w_m;h_m;polygon_m;length_m;width_m;area_m2;perimeter_m;height_m;t_inside_c;volume_m3;air_change_1ph;usage_type\n'
        'R1;EG;Room 1;0,000;0,000;4,000;3,000;;4,000;3,000;12,000;14,000;2,500;20,0;30,000;0,500;\n',
        encoding='utf-8'
    )
    repo = ProjectRepository(delimiter=';')
    data = repo.load(rooms_path)
    assert len(data.rooms) == 1
    room = data.rooms[0]
    assert isinstance(room, RoomModel)
    assert room.polygon_m
    assert room.is_axis_aligned_rect_polygon()
    assert room.area_m2() == 12.0



def test_project_cfg_roundtrip_preserves_attic_u_values(tmp_path):
    from heizlast.configs.project_config import ProjectCfg, save_project_cfg, load_project_cfg

    path = tmp_path / 'project.json'
    cfg = ProjectCfg()
    cfg.attic.enabled = True
    cfg.attic.u_roof_w_m2k = 0.19
    cfg.attic.u_gable_w_m2k = 0.23

    save_project_cfg(path, cfg)
    loaded = load_project_cfg(path)

    assert loaded.cfg_version == 5
    assert loaded.attic.enabled is True
    assert loaded.attic.u_roof_w_m2k == 0.19
    assert loaded.attic.u_gable_w_m2k == 0.23
