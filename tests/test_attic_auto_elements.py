from heizlast.configs.project_config import AtticCfgDTO
from heizlast.core.attic_auto import derive_auto_attic_elements
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
