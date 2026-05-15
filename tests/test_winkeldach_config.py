from heizlast.configs.project_config import ProjectCfg
from heizlast.core.roof_mesh import build_winkeldach_mesh


def test_winkeldach_roundtrip():
    cfg = ProjectCfg()
    cfg.attic.roof_type = "winkeldach"
    d = cfg.to_json_dict()
    loaded = ProjectCfg.from_json_dict(d)
    assert loaded.attic.roof_type == "winkeldach"


def test_winkeldach_mesh_for_l_shape():
    pts = [(0.0, 0.0), (8.0, 0.0), (8.0, 3.0), (5.0, 3.0), (5.0, 7.0), (0.0, 7.0)]
    faces, lines = build_winkeldach_mesh(pts, z_top=2.8, peak_height_m=1.4, target_cells=18)
    assert len(faces) > 20
    z_vals = [p[2] for face in faces for p in face]
    assert max(z_vals) > 3.2
