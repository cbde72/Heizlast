from heizlast.configs.project_config import AtticCfgDTO
from heizlast.core.attic_auto import derive_auto_attic_elements, parse_attic_meta
from heizlast.domain.models import RoomModel


def _single_room():
    return RoomModel(id='DG1', floor='DG', name='DG', x_m=0.0, y_m=0.0, w_m=8.0, h_m=10.0, height_m=2.4)


def test_ridge_orientation_width_swaps_roof_and_gable_sides():
    autos = derive_auto_attic_elements([
        _single_room()
    ], AtticCfgDTO(
        enabled=True,
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        roof_type='satteldach',
        ridge_orientation='width',
    ))
    roofs = [e for e in autos if e.element_type == 'Dach']
    gables = [e for e in autos if e.element_type == 'Giebelwand']
    assert {parse_attic_meta(e.meta).get('attic_part') for e in roofs} == {'roof_front', 'roof_back'}
    assert {parse_attic_meta(e.meta).get('attic_part') for e in gables} == {'gable_left', 'gable_right'}


def test_walmdach_end_walls_reduce_to_knee_wall_rectangles():
    autos = derive_auto_attic_elements([
        _single_room()
    ], AtticCfgDTO(
        enabled=True,
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        roof_type='walmdach',
        ridge_orientation='length',
    ))
    gables = [e for e in autos if e.element_type == 'Giebelwand']
    assert len(gables) == 2
    assert abs(sum(e.area_m2 for e in gables) - 16.0) < 1e-6


def test_asymmetric_ridge_changes_left_and_right_roof_areas():
    autos = derive_auto_attic_elements([
        _single_room()
    ], AtticCfgDTO(
        enabled=True,
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        roof_type='satteldach',
        ridge_orientation='length',
        ridge_offset_ratio=0.30,
    ))
    roofs = [e for e in autos if e.element_type == 'Dach']
    by_part = {parse_attic_meta(e.meta).get('attic_part'): e for e in roofs}
    assert by_part['roof_left'].area_m2 != by_part['roof_right'].area_m2
    assert by_part['roof_right'].area_m2 < by_part['roof_left'].area_m2
