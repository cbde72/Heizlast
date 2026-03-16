from heizlast.configs.project_config import ProjectCfg


def test_facade_material_roundtrip():
    raw = {
        "cfg_version": 9,
        "internal_project_version": "X",
        "attic": {
            "enabled": True,
            "facade_material": "holz",
        },
    }
    cfg = ProjectCfg.from_json_dict(raw)
    assert cfg.attic.facade_material == "holz"
    dumped = cfg.to_json_dict()
    assert dumped["attic"]["facade_material"] == "holz"
