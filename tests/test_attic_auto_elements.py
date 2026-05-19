from heizlast.configs.project_config import AtticCfgDTO, DormerCfgDTO
from heizlast.core.attic_auto import derive_auto_attic_elements, rebuild_auto_attic_elements
from heizlast.domain.models import RoomModel


def test_attic_auto_elements_for_single_full_dg_room():
    room = RoomModel(
        id='DG1', floor='DG', name='DG',
        x_m=0.0, y_m=0.0, w_m=8.0, h_m=10.0,
        height_m=2.4,
    )
    cfg = AtticCfgDTO(enabled=True, building_width_m=8.0, building_length_m=10.0, knee_wall_height_m=1.0, roof_pitch_deg=35.0)
    autos = derive_auto_attic_elements([room], cfg)
    by_type = {}
    for e in autos:
        by_type.setdefault(e.element_type, []).append(e)
    assert len(by_type.get('Dach', [])) == 2
    assert len(by_type.get('Giebelwand', [])) == 2
    roof_sum = sum(e.area_m2 for e in by_type['Dach'])
    gable_sum = sum(e.area_m2 for e in by_type['Giebelwand'])
    assert abs(roof_sum - 97.662) < 0.05
    assert abs(gable_sum - 38.407) < 0.05


def test_attic_auto_elements_split_gable_and_roof_by_contact_edges():
    left = RoomModel(id='L', floor='DG', name='L', x_m=0.0, y_m=0.0, w_m=4.0, h_m=10.0, height_m=2.4)
    right = RoomModel(id='R', floor='DG', name='R', x_m=4.0, y_m=0.0, w_m=4.0, h_m=10.0, height_m=2.4)
    cfg = AtticCfgDTO(enabled=True, building_width_m=8.0, building_length_m=10.0, knee_wall_height_m=1.0, roof_pitch_deg=35.0)
    autos = derive_auto_attic_elements([left, right], cfg)
    left_roof = [e for e in autos if e.room_id == 'L' and e.element_type == 'Dach']
    right_roof = [e for e in autos if e.room_id == 'R' and e.element_type == 'Dach']
    assert len(left_roof) == 1
    assert len(right_roof) == 1
    assert abs(left_roof[0].area_m2 - right_roof[0].area_m2) < 1e-6



def test_attic_auto_elements_use_project_specific_u_values():
    from heizlast.configs.project_config import AtticCfgDTO
    from heizlast.core.attic_auto import derive_auto_attic_elements
    from heizlast.domain.models import RoomModel

    rooms = [RoomModel(id='DG1', floor='DG', name='DG1', x_m=0.0, y_m=0.0, w_m=8.0, h_m=10.0)]
    cfg = AtticCfgDTO(
        enabled=True,
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        u_roof_w_m2k=0.18,
        u_gable_w_m2k=0.24,
    )

    elems = derive_auto_attic_elements(rooms, cfg)

    roofs = [e for e in elems if e.element_type == 'Dach']
    gables = [e for e in elems if e.element_type == 'Giebelwand']

    assert roofs
    assert gables
    assert all(abs(e.u_w_m2k - 0.18) < 1e-12 for e in roofs)
    assert all(abs(e.u_w_m2k - 0.24) < 1e-12 for e in gables)


def test_attic_auto_subtracts_roof_windows_and_adds_window_elements():
    room = RoomModel(id='DG1', floor='DG', name='DG', x_m=0.0, y_m=0.0, w_m=8.0, h_m=10.0)
    base_cfg = AtticCfgDTO(enabled=True, building_width_m=8.0, building_length_m=10.0, knee_wall_height_m=1.0, roof_pitch_deg=35.0)
    with_window_cfg = AtticCfgDTO(
        enabled=True,
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        roof_window_count=1,
        roof_window_width_m=1.0,
        roof_window_height_m=1.2,
        roof_window_side="right",
    )

    base = derive_auto_attic_elements([room], base_cfg)
    with_window = derive_auto_attic_elements([room], with_window_cfg)

    base_roof = sum(e.area_m2 for e in base if e.element_type == 'Dach')
    roof_after = sum(e.area_m2 for e in with_window if e.element_type == 'Dach')
    windows = [e for e in with_window if e.uid and e.uid.startswith("auto_roof_window_")]

    assert len(windows) == 1
    assert abs(windows[0].area_m2 - 1.2) < 1e-9
    assert abs((base_roof - roof_after) - 1.2) < 1e-6


def test_attic_auto_subtracts_dormer_cutout_and_adds_dormer_elements():
    room = RoomModel(id='DG1', floor='DG', name='DG', x_m=0.0, y_m=0.0, w_m=8.0, h_m=10.0)
    base_cfg = AtticCfgDTO(enabled=True, building_width_m=8.0, building_length_m=10.0, knee_wall_height_m=1.0, roof_pitch_deg=35.0)
    dormer_cfg = AtticCfgDTO(
        enabled=True,
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        dormers=[DormerCfgDTO(id="gaube_1", roof_side="right", center_along_m=5.0, width_m=1.8, depth_m=1.4)],
    )

    base = derive_auto_attic_elements([room], base_cfg)
    with_dormer = derive_auto_attic_elements([room], dormer_cfg)

    base_main_roof = sum(e.area_m2 for e in base if e.element_type == 'Dach')
    main_roof_after = sum(e.area_m2 for e in with_dormer if e.element_type == 'Dach' and not str(e.uid or "").startswith("auto_dormer_"))
    dormer_elems = [e for e in with_dormer if str(e.uid or "").startswith("auto_dormer_")]

    assert dormer_elems
    assert abs((base_main_roof - main_roof_after) - 2.6088959746334143) < 1e-6


def test_attic_auto_unheated_roof_boundary_applies_factor_to_roof_only():
    room = RoomModel(id='DG1', floor='DG', name='DG', x_m=0.0, y_m=0.0, w_m=8.0, h_m=10.0)
    cfg = AtticCfgDTO(
        enabled=True,
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        roof_boundary="unheated_attic",
        roof_unheated_factor=0.8,
    )

    elems = derive_auto_attic_elements([room], cfg)

    assert all(abs(e.factor - 0.8) < 1e-12 for e in elems if e.element_type == 'Dach')
    assert all(abs(e.factor - 1.0) < 1e-12 for e in elems if e.element_type == 'Giebelwand')


def test_rebuild_auto_attic_removes_previous_dormer_elements():
    room = RoomModel(id='DG1', floor='DG', name='DG', x_m=0.0, y_m=0.0, w_m=8.0, h_m=10.0)
    cfg = AtticCfgDTO(
        enabled=True,
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        dormers=[DormerCfgDTO(id="gaube_1", roof_side="right", center_along_m=5.0, width_m=1.8, depth_m=1.4)],
    )
    elems = []

    rebuild_auto_attic_elements(rooms=[room], elements=elems, attic_cfg=cfg)
    first_count = len([e for e in elems if str(e.uid or "").startswith("auto_dormer_")])
    rebuild_auto_attic_elements(rooms=[room], elements=elems, attic_cfg=cfg)
    second_count = len([e for e in elems if str(e.uid or "").startswith("auto_dormer_")])

    assert first_count > 0
    assert second_count == first_count
