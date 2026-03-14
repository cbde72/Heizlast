from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Literal
import json
from pathlib import Path

ThicknessMode = Literal["half", "full"]
FloorAreaMode = Literal["inner", "outer"]
TBMode = Literal["none", "delta_u", "psi", "percent"]
GroundMode = Literal["none", "simplified", "perimeter"]


@dataclass
class ThermalBridgeCfgDTO:
    mode: TBMode = "none"
    delta_u_w_m2k: float = 0.05
    psi_default_w_mk: float = 0.0
    percent_of_trans: float = 0.0
    use_element_meta_psi: bool = True
    include_out: bool = True
    include_keller: bool = True
    include_oben: bool = True


@dataclass
class GroundModelCfgDTO:
    mode: GroundMode = "simplified"
    ground_temp_c: float = 10.0
    f_slab: float = 0.40
    f_wall: float = 0.60
    psi_perimeter_w_mk: float = 0.0


@dataclass
class ProjectCfg:
    cfg_version: int = 4

    # Randbedingungen
    t_out_c: float = -10.0
    t_keller_c: float = 14.0
    t_oben_c: float = 12.0
    t_out_source: str = "manual"

    # Geometrie
    thickness_mode: ThicknessMode = "full"
    area_shrink_factor: float = 0.97
    floor_area_mode: FloorAreaMode = "inner"

    # Lüftung
    c_air: float = 0.34

    # Wanddicken
    wall_thickness_outer_m: float = 0.455
    wall_thickness_inner_m: float = 0.115

    # Auto-Decken
    u_kellerdecke_w_m2k: float = 0.45
    u_eg_geschossdecke_w_m2k: float = 0.30
    u_dg_geschossdecke_w_m2k: float = 0.25

    # Wärmebrücken
    tb: ThermalBridgeCfgDTO = field(default_factory=ThermalBridgeCfgDTO)

    # Erdreichmodell
    ground: GroundModelCfgDTO = field(default_factory=GroundModelCfgDTO)

    def to_json_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_json_dict(d: Dict[str, Any]) -> "ProjectCfg":
        if not isinstance(d, dict):
            return ProjectCfg()

        version = int(d.get("cfg_version", 1) or 1)

        if version < 2:
            d.setdefault("t_out_source", "manual")
            version = 2
        if version < 3:
            if "tb" not in d or not isinstance(d["tb"], dict):
                d["tb"] = {}
            version = 3
        if version < 4:
            if "ground" not in d or not isinstance(d["ground"], dict):
                d["ground"] = {}
            version = 4

        tb_raw = d.get("tb", {}) if isinstance(d.get("tb", {}), dict) else {}
        g_raw = d.get("ground", {}) if isinstance(d.get("ground", {}), dict) else {}

        return ProjectCfg(
            cfg_version=4,
            t_out_c=float(d.get("t_out_c", -10.0)),
            t_keller_c=float(d.get("t_keller_c", 14.0)),
            t_oben_c=float(d.get("t_oben_c", 12.0)),
            t_out_source=str(d.get("t_out_source", "manual")),
            thickness_mode=str(d.get("thickness_mode", "full")),
            area_shrink_factor=float(d.get("area_shrink_factor", 0.97)),
            floor_area_mode=str(d.get("floor_area_mode", "inner")),
            c_air=float(d.get("c_air", 0.34)),
            wall_thickness_outer_m=float(d.get("wall_thickness_outer_m", 0.455)),
            wall_thickness_inner_m=float(d.get("wall_thickness_inner_m", 0.115)),
            u_kellerdecke_w_m2k=float(d.get("u_kellerdecke_w_m2k", 0.45)),
            u_eg_geschossdecke_w_m2k=float(d.get("u_eg_geschossdecke_w_m2k", 0.30)),
            u_dg_geschossdecke_w_m2k=float(d.get("u_dg_geschossdecke_w_m2k", 0.25)),
            tb=ThermalBridgeCfgDTO(
                mode=str(tb_raw.get("mode", "none")),
                delta_u_w_m2k=float(tb_raw.get("delta_u_w_m2k", 0.05)),
                psi_default_w_mk=float(tb_raw.get("psi_default_w_mk", 0.0)),
                percent_of_trans=float(tb_raw.get("percent_of_trans", 0.0)),
                use_element_meta_psi=bool(tb_raw.get("use_element_meta_psi", True)),
                include_out=bool(tb_raw.get("include_out", True)),
                include_keller=bool(tb_raw.get("include_keller", True)),
                include_oben=bool(tb_raw.get("include_oben", True)),
            ),
            ground=GroundModelCfgDTO(
                mode=str(g_raw.get("mode", "simplified")),
                ground_temp_c=float(g_raw.get("ground_temp_c", 10.0)),
                f_slab=float(g_raw.get("f_slab", 0.40)),
                f_wall=float(g_raw.get("f_wall", 0.60)),
                psi_perimeter_w_mk=float(g_raw.get("psi_perimeter_w_mk", 0.0)),
            ),
        )


def save_project_cfg(path: Path, cfg: ProjectCfg) -> None:
    path.write_text(json.dumps(cfg.to_json_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def load_project_cfg(path: Path) -> ProjectCfg:
    if not path.exists():
        return ProjectCfg()
    d = json.loads(path.read_text(encoding="utf-8"))
    cfg = ProjectCfg.from_json_dict(d)
    if int(d.get("cfg_version", 1) or 1) < 4:
        save_project_cfg(path, cfg)
    return cfg