from heizlast.configs.project_config import ProjectCfg


def test_attic_profile_params_roundtrip():
    raw = {
        "cfg_version": 8,
        "internal_project_version": "X",
        "attic": {
            "enabled": True,
            "building_width_m": 8.0,
            "building_length_m": 10.0,
            "knee_wall_height_m": 1.1,
            "roof_type": "satteldach",
            "ridge_orientation": "width",
            "roof_overhang_m": 0.45,
            "ridge_offset_ratio": 0.2,
            "pult_rise_side": "left",
            "roof_pitch_deg": 32.0,
        },
    }
    cfg = ProjectCfg.from_json_dict(raw)
    assert cfg.attic.ridge_orientation == "width"
    assert abs(cfg.attic.roof_overhang_m - 0.45) < 1e-9
    assert abs(cfg.attic.ridge_offset_ratio - 0.2) < 1e-9
    assert cfg.attic.pult_rise_side == "left"
    dumped = cfg.to_json_dict()
    assert dumped["attic"]["ridge_orientation"] == "width"
    assert dumped["attic"]["pult_rise_side"] == "left"
