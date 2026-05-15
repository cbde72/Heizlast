from heizlast.configs.project_config import ProjectCfg
from heizlast.core.attic_geometry import AtticGeometry


def test_extended_attic_params_roundtrip_v26():
    raw = {
        "cfg_version": 10,
        "internal_project_version": "X",
        "attic": {
            "enabled": True,
            "roof_type": "krueppelwalmdach",
            "roof_overhang_m": 0.30,
            "eave_overhang_m": 0.55,
            "gable_overhang_m": 0.20,
            "half_hip_ratio": 0.40,
            "dormer_type": "schleppgaube",
            "dormer_width_m": 2.10,
            "dormer_height_m": 1.25,
            "dormer_offset_ratio": 0.15,
            "roof_window_count": 2,
            "roof_window_width_m": 0.94,
            "roof_window_height_m": 1.40,
            "roof_window_side": "both",
        },
    }
    cfg = ProjectCfg.from_json_dict(raw)
    assert cfg.attic.roof_type == "krueppelwalmdach"
    assert cfg.attic.eave_overhang_m == 0.55
    assert cfg.attic.gable_overhang_m == 0.20
    assert cfg.attic.dormer_type == "schleppgaube"
    assert cfg.attic.roof_window_count == 2
    dumped = cfg.to_json_dict()["attic"]
    assert dumped["eave_overhang_m"] == 0.55
    assert dumped["roof_window_side"] == "both"


def test_krueppelwalmdach_has_shorter_hip_than_full_walm():
    walm = AtticGeometry(8.0, 10.0, roof_type="walmdach", roof_pitch_deg=35.0, half_hip_ratio=0.40)
    kr = AtticGeometry(8.0, 10.0, roof_type="krueppelwalmdach", roof_pitch_deg=35.0, half_hip_ratio=0.40)
    assert kr.half_hip_run_m > 0.0
    assert kr.half_hip_run_m < walm.hip_run_m
    assert kr.gable_area_total_m2 < AtticGeometry(8.0, 10.0, roof_type="satteldach", roof_pitch_deg=35.0).gable_area_total_m2


def test_separate_overhangs_affect_plan_rect_and_openings_helpers():
    g = AtticGeometry(
        8.0,
        10.0,
        roof_type="satteldach",
        ridge_orientation="length",
        eave_overhang_m=0.60,
        gable_overhang_m=0.25,
        dormer_type="schleppgaube",
        roof_window_count=2,
    )
    outer = g.plan_outer_rect()
    assert abs(outer[2] - (8.0 + 2 * 0.60)) < 1e-9
    assert abs(outer[3] - (10.0 + 2 * 0.25)) < 1e-9
    assert g.dormer_rect() is not None
    assert len(g.roof_window_rects()) == 2
