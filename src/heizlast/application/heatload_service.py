from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ..core.heatload import calc_heatloads, ensure_auto_decks
from ..core.config import VentilationCfg
from ..core.ground_model import GroundModelCfg
from ..core.heatload_types import ThermalBridgeCfg
from ..domain.house_state import HouseState


@dataclass
class HeatloadComputationService:
    """Application service for idempotent deck sync + heatload computation."""

    def compute(self, state: HouseState, vent_cfg: Optional[VentilationCfg] = None) -> Dict:
        cfg = state.project_cfg
        vent_cfg = vent_cfg or VentilationCfg()

        try:
            ensure_auto_decks(
                state.rooms.values(),
                state.elements,
                u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
                u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
                u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
            )
        except Exception:
            pass

        return calc_heatloads(
            list(state.rooms.values()),
            state.elements,
            t_out_c=float(cfg.t_out_c),
            vent_cfg=vent_cfg,
            thickness_mode=cfg.thickness_mode,
            area_shrink_factor=float(cfg.area_shrink_factor),
            floor_area_mode=cfg.floor_area_mode,
            tb_cfg=ThermalBridgeCfg(**cfg.tb.__dict__),
            ground_cfg=GroundModelCfg(**cfg.ground.__dict__),
            u_aussenwand_w_m2k=float(getattr(cfg, "u_aussenwand_w_m2k", 0.45)),
            u_fenster_w_m2k=float(getattr(cfg, "u_fenster_w_m2k", 2.80)),
            u_tuer_w_m2k=float(getattr(cfg, "u_tuer_w_m2k", 1.80)),
            reheat_power_w_m2=(float(cfg.reheat_power_w_m2) if bool(getattr(cfg, "reheat_enabled", False)) else 0.0),
            reheat_duration_h=(float(cfg.reheat_duration_h) if bool(getattr(cfg, "reheat_enabled", False)) else 0.0),
            reheat_temp_drop_k=(float(cfg.reheat_temp_drop_k) if bool(getattr(cfg, "reheat_enabled", False)) else 0.0),
            reheat_capacity_wh_m2k=float(getattr(cfg, "reheat_capacity_wh_m2k", 20.0)),
            u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
            u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
            u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
            u_bodenplatte_w_m2k=float(getattr(cfg, "u_bodenplatte_w_m2k", 0.40)),
            u_erdberuehrte_wand_w_m2k=float(getattr(cfg, "u_erdberuehrte_wand_w_m2k", 0.60)),
            ventilation_mode=str(getattr(cfg, "ventilation_mode", "natural")),
            min_air_change_1ph=float(getattr(cfg, "min_air_change_1ph", 0.0)),
            infiltration_air_change_1ph=float(getattr(cfg, "infiltration_air_change_1ph", 0.0)),
            mech_supply_m3h=float(getattr(cfg, "mech_supply_m3h", 0.0)),
            mech_exhaust_m3h=float(getattr(cfg, "mech_exhaust_m3h", 0.0)),
            heat_recovery_efficiency=float(getattr(cfg, "heat_recovery_efficiency", 0.0)),
            sync_auto_decks=False,
        )
