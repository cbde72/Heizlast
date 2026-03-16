from heizlast.configs.project_config import ProjectCfg


def test_project_config_roof_type_roundtrip_and_upgrade():
    legacy = {
        "cfg_version": 6,
        "attic": {
            "enabled": True,
            "building_width_m": 9.0,
            "building_length_m": 12.0,
            "knee_wall_height_m": 1.2,
            "roof_pitch_deg": 28.0,
        },
    }
    cfg = ProjectCfg.from_json_dict(legacy)
    assert cfg.cfg_version == 10
    assert cfg.attic.roof_type == "satteldach"

    cfg.attic.roof_type = "walmdach"
    d = cfg.to_json_dict()
    assert d["attic"]["roof_type"] == "walmdach"
