from heizlast.configs.project_config import ProjectCfg


def test_roof_material_roundtrip_and_upgrade():
    legacy = {"cfg_version": 9, "internal_project_version": "X", "attic": {"enabled": True}}
    cfg = ProjectCfg.from_json_dict(legacy)
    assert cfg.cfg_version == 10
    assert cfg.attic.roof_material == "ziegel"
    dumped = cfg.to_json_dict()
    assert dumped["attic"]["roof_material"] == "ziegel"
