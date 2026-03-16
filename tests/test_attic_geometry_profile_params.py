from heizlast.core.attic_geometry import AtticGeometry


def test_asymmetric_ridge_changes_clear_width():
    g = AtticGeometry(8.0, 10.0, knee_wall_height_m=1.0, roof_pitch_deg=35.0, roof_type="satteldach", ridge_offset_ratio=0.3)
    assert g.ridge_x_m > 4.0
    assert g.clear_width_at_height_m(1.8) > 0.0


def test_pult_left_side_peak_and_width():
    g = AtticGeometry(8.0, 10.0, knee_wall_height_m=1.0, roof_pitch_deg=20.0, roof_type="pultdach", pult_rise_side="left")
    assert g.total_height_m > g.knee_wall_height_m
    assert g.clear_width_at_height_m(g.total_height_m - 1e-6) >= 0.0
