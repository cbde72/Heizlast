from heizlast.core.attic_geometry import AtticGeometry
from heizlast.core.attic_auto import _build_roof_model
from heizlast.configs.project_config import AtticCfgDTO, RoofLineCfgDTO


def test_attic_geometry_custom_roof_lines_affect_plan_and_area():
    base = AtticGeometry(building_width_m=8.0, building_length_m=10.0, knee_wall_height_m=1.0, roof_pitch_deg=35.0, roof_type='winkeldach')
    with_lines = AtticGeometry(
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        roof_type='winkeldach',
        roof_lines=(('first', 0.15, 0.50, 0.85, 0.50), ('kehle', 0.50, 0.50, 0.82, 0.82)),
    )
    segs = with_lines.custom_roof_line_segments()
    assert len(segs) == 2
    assert with_lines.roof_area_total_m2 > base.roof_area_total_m2


def test_roof_model_area_factor_increases_with_roof_lines():
    cfg_plain = AtticCfgDTO(enabled=True, building_width_m=8.0, building_length_m=10.0, roof_pitch_deg=35.0, roof_type='winkeldach')
    cfg_lines = AtticCfgDTO(
        enabled=True,
        building_width_m=8.0,
        building_length_m=10.0,
        roof_pitch_deg=35.0,
        roof_type='winkeldach',
        roof_lines=[RoofLineCfgDTO(kind='first', x1_ratio=0.10, y1_ratio=0.50, x2_ratio=0.90, y2_ratio=0.50), RoofLineCfgDTO(kind='kehle', x1_ratio=0.50, y1_ratio=0.50, x2_ratio=0.80, y2_ratio=0.80)],
    )
    plain = _build_roof_model(cfg_plain)
    lined = _build_roof_model(cfg_lines)
    assert lined.roof_line_area_factor > plain.roof_line_area_factor
