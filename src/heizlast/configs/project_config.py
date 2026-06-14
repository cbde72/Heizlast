from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Literal, Optional
import json
from pathlib import Path
from .. import PROJECT_SCHEMA_VERSION

ThicknessMode = Literal["half", "full"]
FloorAreaMode = Literal["inner", "outer"]
TBMode = Literal["none", "delta_u", "psi", "percent"]
GroundMode = Literal["none", "simplified", "perimeter", "din_ts"]
VentilationMode = Literal["natural", "mechanical"]
RoofType = Literal["satteldach", "pultdach", "walmdach", "krueppelwalmdach", "flachdach", "winkeldach"]
RoofLineKind = Literal["first", "grat", "kehle"]
RidgeOrientation = Literal["length", "width"]
PultRiseSide = Literal["left", "right"]
FacadeMaterial = Literal["klinker", "putz", "holz", "beton"]
RoofMaterial = Literal["ziegel"]
DormerType = Literal["none", "schleppgaube", "satteldachgaube", "flachdachgaube", "spitzgaube"]
RoofWindowSide = Literal["left", "right", "both"]


@dataclass
class RoofLineCfgDTO:
    kind: RoofLineKind = "first"
    x1_ratio: float = 0.20
    y1_ratio: float = 0.50
    x2_ratio: float = 0.80
    y2_ratio: float = 0.50


@dataclass
class AtticCfgDTO:
    enabled: bool = False
    building_width_m: float = 8.0
    building_length_m: float = 10.0
    knee_wall_height_m: float = 1.0
    roof_type: RoofType = "satteldach"
    ridge_orientation: RidgeOrientation = "length"
    roof_overhang_m: float = 0.30
    eave_overhang_m: float = 0.30
    gable_overhang_m: float = 0.30
    ridge_offset_ratio: float = 0.0
    ridge_height_m: Optional[float] = None
    pult_rise_side: PultRiseSide = "right"
    half_hip_ratio: float = 0.45
    dormer_type: DormerType = "none"
    dormer_width_m: float = 1.80
    dormer_height_m: float = 1.20
    dormer_offset_ratio: float = 0.0
    roof_window_count: int = 0
    roof_window_width_m: float = 0.78
    roof_window_height_m: float = 1.18
    roof_window_side: RoofWindowSide = "right"
    roof_pitch_deg: float = 35.0
    roof_boundary: Literal["outside", "unheated_attic"] = "outside"
    roof_unheated_factor: float = 0.80
    facade_material: FacadeMaterial = "klinker"
    roof_material: RoofMaterial = "ziegel"
    u_roof_w_m2k: float = 0.30
    u_gable_w_m2k: float = 0.45
    zero_roof_gable_transmission: bool = False
    dormers: list[DormerCfgDTO] = field(default_factory=list)
    roof_lines: list[RoofLineCfgDTO] = field(default_factory=list)


@dataclass
class DormerCfgDTO:
    id: str = "dormer_1"
    dormer_type: DormerType = "schleppgaube"
    roof_side: str = "right"
    center_along_m: float = 0.0
    width_m: float = 1.80
    depth_m: float = 1.40
    front_height_m: float = 1.20
    window_count: int = 1
    window_width_m: float = 1.20
    window_height_m: float = 1.20
    sill_height_m: float = 0.90
    roof_pitch_deg: Optional[float] = None
    min_edge_clearance_m: float = 0.40


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
    din_ts_f_slab: float = 0.35
    din_ts_f_wall: float = 0.50
    din_ts_source: str = ""


@dataclass
class ProjectCfg:
    cfg_version: int = PROJECT_SCHEMA_VERSION
    internal_project_version: str = "V33-intern-01"

    # Randbedingungen
    t_out_c: float = -10.0
    t_keller_c: float = 14.0
    t_oben_c: float = 12.0
    t_out_source: str = "manual"
    norm_edition: str = "DIN EN 12831-1:2017-09 / DIN/TS 12831-1:2020-04"
    t_out_source_detail: str = ""
    climate_station: str = ""
    climate_altitude_correction: str = ""
    thermal_bridge_source: str = ""
    ground_source: str = ""
    ventilation_source: str = ""
    reheat_source: str = ""
    u_value_source: str = ""
    reviewer_note: str = ""
    ground_norm_inputs: str = ""
    reheat_norm_basis: str = ""
    proof_export_enabled: bool = False
    change_log_note: str = ""

    # Geometrie
    thickness_mode: ThicknessMode = "full"
    area_shrink_factor: float = 0.97
    floor_area_mode: FloorAreaMode = "inner"

    # Lüftung
    c_air: float = 0.34
    ventilation_mode: VentilationMode = "natural"
    min_air_change_1ph: float = 0.0
    infiltration_air_change_1ph: float = 0.0
    mech_supply_m3h: float = 0.0
    mech_exhaust_m3h: float = 0.0
    heat_recovery_efficiency: float = 0.0

    # Aufheizzuschlag
    reheat_enabled: bool = False
    reheat_power_w_m2: float = 0.0
    reheat_duration_h: float = 2.0
    reheat_temp_drop_k: float = 0.0
    reheat_capacity_wh_m2k: float = 20.0

    # Wanddicken
    wall_thickness_outer_m: float = 0.455
    wall_thickness_inner_m: float = 0.115
    wall_heat_transfer_coeff_inside_w_m2k: float = 7.69
    wall_heat_transfer_coeff_outside_w_m2k: float = 25.0

    # Auto-Decken
    u_aussenwand_w_m2k: float = 0.45
    u_fenster_w_m2k: float = 2.80
    u_tuer_w_m2k: float = 1.80
    u_kellerdecke_w_m2k: float = 0.45
    u_eg_geschossdecke_w_m2k: float = 0.30
    u_dg_geschossdecke_w_m2k: float = 0.25
    auto_deck_assumptions_confirmed: bool = False
    auto_deck_boundary_source: str = ""
    auto_deck_create_eg_kellerdecke: bool = True
    auto_deck_create_eg_geschossdecke: bool = True
    auto_deck_create_dg_speicherdecke: bool = True
    u_bodenplatte_w_m2k: float = 0.40
    u_erdberuehrte_wand_w_m2k: float = 0.60

    # Wärmebrücken
    tb: ThermalBridgeCfgDTO = field(default_factory=ThermalBridgeCfgDTO)

    # Erdreichmodell
    ground: GroundModelCfgDTO = field(default_factory=GroundModelCfgDTO)

    # DG Dach / Giebel
    attic: AtticCfgDTO = field(default_factory=AtticCfgDTO)

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
        if version < 5:
            if "attic" not in d or not isinstance(d.get("attic", {}), dict):
                d["attic"] = {}
            version = 5
        if version < 6:
            d.setdefault("internal_project_version", "V11-intern-01")
            version = 6
        if version < 7:
            if "attic" not in d or not isinstance(d.get("attic", {}), dict):
                d["attic"] = {}
            d.setdefault("internal_project_version", "V13-intern-01")
            version = 7
        if version < 8:
            if "attic" not in d or not isinstance(d.get("attic", {}), dict):
                d["attic"] = {}
            a = d.get("attic", {})
            if isinstance(a, dict):
                a.setdefault("ridge_orientation", "length")
                a.setdefault("roof_overhang_m", 0.30)
                a.setdefault("ridge_offset_ratio", 0.0)
                a.setdefault("pult_rise_side", "right")
            d.setdefault("internal_project_version", "V15-intern-01")
            version = 8
        if version < 9:
            if "attic" not in d or not isinstance(d.get("attic", {}), dict):
                d["attic"] = {}
            a = d.get("attic", {})
            if isinstance(a, dict):
                a.setdefault("facade_material", "klinker")
            d.setdefault("internal_project_version", "V18-intern-01")
            version = 9
        if version < 10:
            if "attic" not in d or not isinstance(d.get("attic", {}), dict):
                d["attic"] = {}
            a = d.get("attic", {})
            if isinstance(a, dict):
                a.setdefault("roof_material", "ziegel")
            d.setdefault("internal_project_version", "V19-intern-01")
            version = 10

        if version < 12:
            if "attic" not in d or not isinstance(d.get("attic", {}), dict):
                d["attic"] = {}
            a = d.get("attic", {})
            if isinstance(a, dict):
                a.setdefault("dormers", [])
            d.setdefault("internal_project_version", "V27-intern-01")
            version = 12
        if version < 13:
            if "attic" not in d or not isinstance(d.get("attic", {}), dict):
                d["attic"] = {}
            a = d.get("attic", {})
            if isinstance(a, dict):
                a.setdefault("dormers", [])
            d.setdefault("internal_project_version", "V28-intern-01")
            version = 13

        if version < 14:
            if "attic" not in d or not isinstance(d.get("attic", {}), dict):
                d["attic"] = {}
            a = d.get("attic", {})
            if isinstance(a, dict):
                rt = str(a.get("roof_type", "satteldach") or "satteldach").strip().lower()
                if rt not in {"satteldach", "pultdach", "walmdach", "krueppelwalmdach", "flachdach", "winkeldach"}:
                    a["roof_type"] = "satteldach"
            d.setdefault("internal_project_version", "V29-intern-01")
            version = 14
        if version < 15:
            if "attic" not in d or not isinstance(d.get("attic", {}), dict):
                d["attic"] = {}
            a = d.get("attic", {})
            if isinstance(a, dict):
                a.setdefault("roof_lines", [])
            d.setdefault("internal_project_version", "V30-intern-01")
            version = 15
        if version < 17:
            if "attic" not in d or not isinstance(d.get("attic", {}), dict):
                d["attic"] = {}
            a = d.get("attic", {})
            if isinstance(a, dict):
                a.setdefault("ridge_height_m", None)
                a.setdefault("roof_boundary", "outside")
                a.setdefault("roof_unheated_factor", 0.80)
            d.setdefault("internal_project_version", "V33-intern-01")
            version = 17
        if version < 18:
            d.setdefault("norm_edition", "DIN EN 12831-1:2017-09 / DIN/TS 12831-1:2020-04")
            d.setdefault("t_out_source_detail", "")
            d.setdefault("thermal_bridge_source", "")
            d.setdefault("ground_source", "")
            d.setdefault("ventilation_source", "")
            d.setdefault("reheat_source", "")
            d.setdefault("reviewer_note", "")
            d.setdefault("ventilation_mode", "natural")
            d.setdefault("mech_supply_m3h", 0.0)
            d.setdefault("mech_exhaust_m3h", 0.0)
            d.setdefault("heat_recovery_efficiency", 0.0)
            d.setdefault("reheat_enabled", False)
            d.setdefault("reheat_power_w_m2", 0.0)
            version = 18
        if version < 19:
            d.setdefault("climate_station", "")
            d.setdefault("climate_altitude_correction", "")
            d.setdefault("reheat_duration_h", 2.0)
            d.setdefault("reheat_temp_drop_k", 0.0)
            d.setdefault("reheat_capacity_wh_m2k", 20.0)
            if "ground" not in d or not isinstance(d.get("ground", {}), dict):
                d["ground"] = {}
            g = d.get("ground", {})
            if isinstance(g, dict):
                g.setdefault("din_ts_f_slab", 0.35)
                g.setdefault("din_ts_f_wall", 0.50)
                g.setdefault("din_ts_source", "")
            version = 19
        if version < 20:
            d.setdefault("wall_heat_transfer_coeff_inside_w_m2k", 7.69)
            d.setdefault("wall_heat_transfer_coeff_outside_w_m2k", 25.0)
            version = 20
        if version < 21:
            d.setdefault("min_air_change_1ph", 0.0)
            d.setdefault("infiltration_air_change_1ph", 0.0)
            version = 21
        if version < 22:
            d.setdefault("u_bodenplatte_w_m2k", 0.40)
            d.setdefault("u_erdberuehrte_wand_w_m2k", 0.60)
            version = 22
        if version < 23:
            d.setdefault("u_aussenwand_w_m2k", 0.45)
            version = 23
        if version < 24:
            d.setdefault("u_fenster_w_m2k", 2.80)
            d.setdefault("u_tuer_w_m2k", 1.80)
            d.setdefault("u_value_source", "")
            version = 24
        if version < 25:
            d.setdefault("auto_deck_assumptions_confirmed", False)
            d.setdefault("auto_deck_boundary_source", "")
            d.setdefault("auto_deck_create_eg_kellerdecke", True)
            d.setdefault("auto_deck_create_eg_geschossdecke", True)
            d.setdefault("auto_deck_create_dg_speicherdecke", True)
            version = 25
        if version < 26:
            d.setdefault("ground_norm_inputs", "")
            d.setdefault("reheat_norm_basis", "")
            d.setdefault("proof_export_enabled", False)
            d.setdefault("change_log_note", "")
            version = 26

        tb_raw = d.get("tb", {}) if isinstance(d.get("tb", {}), dict) else {}
        g_raw = d.get("ground", {}) if isinstance(d.get("ground", {}), dict) else {}
        a_raw = d.get("attic", {}) if isinstance(d.get("attic", {}), dict) else {}

        return ProjectCfg(
            cfg_version=PROJECT_SCHEMA_VERSION,
            internal_project_version=str(d.get("internal_project_version", "V30-intern-01")),
            t_out_c=float(d.get("t_out_c", -10.0)),
            t_keller_c=float(d.get("t_keller_c", 14.0)),
            t_oben_c=float(d.get("t_oben_c", 12.0)),
            t_out_source=str(d.get("t_out_source", "manual")),
            norm_edition=str(d.get("norm_edition", "DIN EN 12831-1:2017-09 / DIN/TS 12831-1:2020-04")),
            t_out_source_detail=str(d.get("t_out_source_detail", "")),
            climate_station=str(d.get("climate_station", "")),
            climate_altitude_correction=str(d.get("climate_altitude_correction", "")),
            thermal_bridge_source=str(d.get("thermal_bridge_source", "")),
            ground_source=str(d.get("ground_source", "")),
            ventilation_source=str(d.get("ventilation_source", "")),
            reheat_source=str(d.get("reheat_source", "")),
            u_value_source=str(d.get("u_value_source", "")),
            reviewer_note=str(d.get("reviewer_note", "")),
            ground_norm_inputs=str(d.get("ground_norm_inputs", "")),
            reheat_norm_basis=str(d.get("reheat_norm_basis", "")),
            proof_export_enabled=bool(d.get("proof_export_enabled", False)),
            change_log_note=str(d.get("change_log_note", "")),
            thickness_mode=str(d.get("thickness_mode", "full")),
            area_shrink_factor=float(d.get("area_shrink_factor", 0.97)),
            floor_area_mode=str(d.get("floor_area_mode", "inner")),
            c_air=float(d.get("c_air", 0.34)),
            ventilation_mode=str(d.get("ventilation_mode", "natural")),
            min_air_change_1ph=float(d.get("min_air_change_1ph", 0.0)),
            infiltration_air_change_1ph=float(d.get("infiltration_air_change_1ph", 0.0)),
            mech_supply_m3h=float(d.get("mech_supply_m3h", 0.0)),
            mech_exhaust_m3h=float(d.get("mech_exhaust_m3h", 0.0)),
            heat_recovery_efficiency=float(d.get("heat_recovery_efficiency", 0.0)),
            reheat_enabled=bool(d.get("reheat_enabled", False)),
            reheat_power_w_m2=float(d.get("reheat_power_w_m2", 0.0)),
            reheat_duration_h=float(d.get("reheat_duration_h", 2.0)),
            reheat_temp_drop_k=float(d.get("reheat_temp_drop_k", 0.0)),
            reheat_capacity_wh_m2k=float(d.get("reheat_capacity_wh_m2k", 20.0)),
            wall_thickness_outer_m=float(d.get("wall_thickness_outer_m", 0.455)),
            wall_thickness_inner_m=float(d.get("wall_thickness_inner_m", 0.115)),
            wall_heat_transfer_coeff_inside_w_m2k=float(d.get("wall_heat_transfer_coeff_inside_w_m2k", 7.69)),
            wall_heat_transfer_coeff_outside_w_m2k=float(d.get("wall_heat_transfer_coeff_outside_w_m2k", 25.0)),
            u_aussenwand_w_m2k=float(d.get("u_aussenwand_w_m2k", 0.45)),
            u_fenster_w_m2k=float(d.get("u_fenster_w_m2k", 2.80)),
            u_tuer_w_m2k=float(d.get("u_tuer_w_m2k", 1.80)),
            u_kellerdecke_w_m2k=float(d.get("u_kellerdecke_w_m2k", 0.45)),
            u_eg_geschossdecke_w_m2k=float(d.get("u_eg_geschossdecke_w_m2k", 0.30)),
            u_dg_geschossdecke_w_m2k=float(d.get("u_dg_geschossdecke_w_m2k", 0.25)),
            auto_deck_assumptions_confirmed=bool(d.get("auto_deck_assumptions_confirmed", False)),
            auto_deck_boundary_source=str(d.get("auto_deck_boundary_source", "")),
            auto_deck_create_eg_kellerdecke=bool(d.get("auto_deck_create_eg_kellerdecke", True)),
            auto_deck_create_eg_geschossdecke=bool(d.get("auto_deck_create_eg_geschossdecke", True)),
            auto_deck_create_dg_speicherdecke=bool(d.get("auto_deck_create_dg_speicherdecke", True)),
            u_bodenplatte_w_m2k=float(d.get("u_bodenplatte_w_m2k", 0.40)),
            u_erdberuehrte_wand_w_m2k=float(d.get("u_erdberuehrte_wand_w_m2k", 0.60)),
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
                din_ts_f_slab=float(g_raw.get("din_ts_f_slab", 0.35)),
                din_ts_f_wall=float(g_raw.get("din_ts_f_wall", 0.50)),
                din_ts_source=str(g_raw.get("din_ts_source", "")),
            ),
            attic=AtticCfgDTO(
                enabled=bool(a_raw.get("enabled", False)),
                building_width_m=float(a_raw.get("building_width_m", 8.0)),
                building_length_m=float(a_raw.get("building_length_m", 10.0)),
                knee_wall_height_m=float(a_raw.get("knee_wall_height_m", 1.0)),
                roof_type=str(a_raw.get("roof_type", "satteldach") or "satteldach").strip().lower(),
                ridge_orientation=str(a_raw.get("ridge_orientation", "length") or "length").strip().lower(),
                roof_overhang_m=float(a_raw.get("roof_overhang_m", 0.30)),
                eave_overhang_m=float(a_raw.get("eave_overhang_m", a_raw.get("roof_overhang_m", 0.30))),
                gable_overhang_m=float(a_raw.get("gable_overhang_m", a_raw.get("roof_overhang_m", 0.30))),
                ridge_offset_ratio=float(a_raw.get("ridge_offset_ratio", 0.0)),
                ridge_height_m=(float(a_raw.get("ridge_height_m")) if a_raw.get("ridge_height_m") not in (None, "") else None),
                pult_rise_side=str(a_raw.get("pult_rise_side", "right") or "right").strip().lower(),
                half_hip_ratio=float(a_raw.get("half_hip_ratio", 0.45)),
                dormer_type=str(a_raw.get("dormer_type", "none") or "none").strip().lower(),
                dormer_width_m=float(a_raw.get("dormer_width_m", 1.80)),
                dormer_height_m=float(a_raw.get("dormer_height_m", 1.20)),
                dormer_offset_ratio=float(a_raw.get("dormer_offset_ratio", 0.0)),
                roof_window_count=int(a_raw.get("roof_window_count", 0) or 0),
                roof_window_width_m=float(a_raw.get("roof_window_width_m", 0.78)),
                roof_window_height_m=float(a_raw.get("roof_window_height_m", 1.18)),
                roof_window_side=str(a_raw.get("roof_window_side", "right") or "right").strip().lower(),
                roof_pitch_deg=float(a_raw.get("roof_pitch_deg", 35.0)),
                roof_boundary=str(a_raw.get("roof_boundary", "outside") or "outside").strip().lower(),
                roof_unheated_factor=float(a_raw.get("roof_unheated_factor", 0.80)),
                facade_material=str(a_raw.get("facade_material", "klinker") or "klinker").strip().lower(),
                roof_material=str(a_raw.get("roof_material", "ziegel") or "ziegel").strip().lower(),
                u_roof_w_m2k=float(a_raw.get("u_roof_w_m2k", 0.30)),
                u_gable_w_m2k=float(a_raw.get("u_gable_w_m2k", 0.45)),
                zero_roof_gable_transmission=bool(a_raw.get("zero_roof_gable_transmission", False)),
                dormers=[
                    DormerCfgDTO(
                        id=str(item.get("id", f"dormer_{idx+1}")),
                        dormer_type=str(item.get("dormer_type", "schleppgaube") or "schleppgaube").strip().lower(),
                        roof_side=str(item.get("roof_side", "right") or "right").strip().lower(),
                        center_along_m=float(item.get("center_along_m", 0.0) or 0.0),
                        width_m=float(item.get("width_m", 1.80) or 1.80),
                        depth_m=float(item.get("depth_m", 1.40) or 1.40),
                        front_height_m=float(item.get("front_height_m", 1.20) or 1.20),
                        window_count=int(item.get("window_count", 1) or 0),
                        window_width_m=float(item.get("window_width_m", 1.20) or 1.20),
                        window_height_m=float(item.get("window_height_m", 1.20) or 1.20),
                        sill_height_m=float(item.get("sill_height_m", 0.90) or 0.90),
                        roof_pitch_deg=(float(item.get("roof_pitch_deg")) if item.get("roof_pitch_deg") is not None else None),
                        min_edge_clearance_m=float(item.get("min_edge_clearance_m", 0.40) or 0.40),
                    )
                    for idx, item in enumerate(a_raw.get("dormers", []) if isinstance(a_raw.get("dormers", []), list) else [])
                    if isinstance(item, dict)
                ],
                roof_lines=[
                    RoofLineCfgDTO(
                        kind=str(item.get("kind", "first") or "first").strip().lower(),
                        x1_ratio=float(item.get("x1_ratio", 0.20) or 0.20),
                        y1_ratio=float(item.get("y1_ratio", 0.50) or 0.50),
                        x2_ratio=float(item.get("x2_ratio", 0.80) or 0.80),
                        y2_ratio=float(item.get("y2_ratio", 0.50) or 0.50),
                    )
                    for item in (a_raw.get("roof_lines", []) if isinstance(a_raw.get("roof_lines", []), list) else [])
                    if isinstance(item, dict)
                ],
            ),
        )


def save_project_cfg(path: Path, cfg: ProjectCfg) -> None:
    path.write_text(json.dumps(cfg.to_json_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def load_project_cfg(path: Path) -> ProjectCfg:
    if not path.exists():
        return ProjectCfg()
    d = json.loads(path.read_text(encoding="utf-8"))
    cfg = ProjectCfg.from_json_dict(d)
    if int(d.get("cfg_version", 1) or 1) < PROJECT_SCHEMA_VERSION:
        save_project_cfg(path, cfg)
    return cfg
