from heizlast.core.attic_geometry import AtticGeometry


def test_cross_span_follows_ridge_orientation():
    g = AtticGeometry(8.0, 10.0, knee_wall_height_m=1.0, roof_pitch_deg=35.0, roof_type="satteldach", ridge_orientation="width")
    pts = g.cross_section_points()
    assert g.cross_span_m == 10.0
    assert pts[0] == (0.0, 0.0)
    assert pts[-1] == (10.0, 0.0)


def test_walmdach_plan_uses_exact_hip_run():
    g = AtticGeometry(8.0, 10.0, knee_wall_height_m=1.0, roof_pitch_deg=35.0, roof_type="walmdach", ridge_orientation="length", ridge_offset_ratio=0.3, roof_overhang_m=0.3)
    ridge = g.plan_ridge_or_slope_line()
    hips = g.plan_hip_lines()
    assert len(ridge) == 2
    assert len(hips) == 4
    assert abs(ridge[0][0] - (0.3 + g.ridge_pos_m)) < 1e-9
    assert abs(ridge[0][1] - (0.3 + g.hip_run_m)) < 1e-9
    assert abs(ridge[1][1] - (0.3 + g.building_length_m - g.hip_run_m)) < 1e-9


def test_pult_plan_line_follows_selected_rise_side():
    g = AtticGeometry(8.0, 10.0, knee_wall_height_m=1.0, roof_pitch_deg=15.0, roof_type="pultdach", ridge_orientation="length", pult_rise_side="left", roof_overhang_m=0.2)
    line = g.plan_ridge_or_slope_line()
    assert line[0][0] > line[1][0]
    assert abs(line[0][1] - line[1][1]) < 1e-9
