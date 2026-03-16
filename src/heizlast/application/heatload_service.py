from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ..core.heatload import calc_heatloads, ensure_auto_decks
from ..core.config import VentilationCfg
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
        )
