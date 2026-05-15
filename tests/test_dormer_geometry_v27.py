from heizlast.configs.project_config import ProjectCfg
from heizlast.core.dormer_auto_elements import build_dormer_results_from_attic_cfg, dormer_cutout_area_total, dormer_to_auto_elements
from heizlast.core.dormer_geometry import DormerGeometry, DormerInput, RoofContext


def test_dormer_geometry_shed_produces_positive_areas():
    roof = RoofContext(roof_type="satteldach", ridge_direction="length", building_length_m=10.0, building_width_m=8.0)
    result = DormerGeometry(roof).build(DormerInput(id="d1", dormer_type="shed", roof_side="right", center_along_m=5.0, width_m=1.8, depth_m=1.4, front_height_m=1.2))
    assert result.areas.dormer_roof_m2 > 0.0
    assert result.areas.front_wall_net_m2 > 0.0
    assert result.areas.cutout_main_roof_m2 > 0.0


def test_project_cfg_roundtrip_supports_dormer_list():
    raw = {
        "cfg_version": 11,
        "attic": {
            "enabled": True,
            "building_width_m": 8.0,
            "building_length_m": 10.0,
            "ridge_orientation": "length",
            "dormers": [
                {
                    "id": "gaube_1",
                    "dormer_type": "schleppgaube",
                    "roof_side": "right",
                    "center_along_m": 4.2,
                    "width_m": 1.9,
                    "depth_m": 1.4,
                    "front_height_m": 1.2,
                    "window_count": 2,
                }
            ],
        },
    }
    cfg = ProjectCfg.from_json_dict(raw)
    assert len(cfg.attic.dormers) == 1
    assert cfg.attic.dormers[0].id == "gaube_1"
    dumped = cfg.to_json_dict()
    assert dumped["attic"]["dormers"][0]["roof_side"] == "right"


def test_build_dormer_results_and_auto_elements_from_cfg():
    cfg = ProjectCfg.from_json_dict({
        "attic": {
            "enabled": True,
            "building_width_m": 8.0,
            "building_length_m": 10.0,
            "ridge_orientation": "length",
            "dormers": [{
                "id": "gaube_1",
                "dormer_type": "flachdachgaube",
                "roof_side": "left",
                "center_along_m": 5.0,
                "width_m": 2.0,
                "depth_m": 1.5,
                "front_height_m": 1.25,
            }]
        }
    })
    results = build_dormer_results_from_attic_cfg(cfg.attic)
    assert len(results) == 1
    assert dormer_cutout_area_total(results) > 0.0
    elems = dormer_to_auto_elements(results[0], room_id="r1")
    assert {e.element_type for e in elems} == {"Außenwand", "Dach", "Fenster"}
