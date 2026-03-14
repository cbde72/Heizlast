from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from ..domain.house_state import HouseState
from ..domain.services.house_domain_service import HouseDomainService
from ..core.heatload import calc_heatloads, ensure_auto_decks
from ..core.config import VentilationCfg


@dataclass
class AppController:
    """Application layer: orchestrates use-cases around the domain state.
    No Qt Widgets / QGraphics. May use infrastructure ports for IO/settings.
    """

    state: HouseState
    domain: HouseDomainService
    repo: object  # ProjectRepository-like
    settings: Optional[object] = None

    def load_project(self, rooms_csv_path: Path) -> Tuple[Path, Path]:
        rooms, elements, cfg, elements_csv_path = self.repo.load(rooms_csv_path)

        self.state.rooms = {r.id: r for r in rooms}
        self.state.elements = list(elements)
        self.state.project_cfg = cfg

        # Ensure decks exist according to cfg (idempotent)
        try:
            ensure_auto_decks(
                self.state.rooms.values(),
                self.state.elements,
                u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
                u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
                u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
            )
        except Exception:
            pass

        return rooms_csv_path, elements_csv_path

    def save_project(self, rooms_csv_path: Path, elements_csv_path: Path) -> None:
        self.repo.save(
            rooms_csv_path,
            elements_csv_path,
            rooms=list(self.state.rooms.values()),
            elements=self.state.elements,
            cfg=self.state.project_cfg,
        )

    def apply_room_changes(
        self,
        rid: str,
        *,
        name: str,
        floor: str,
        x_m: float,
        y_m: float,
        w_m: float,
        h_m: float,
        height_m: float,
        t_inside_c: float,
        air_change_1ph: float,
        autowalls_enabled: bool,
    ) -> None:
        r = self.state.rooms.get(rid)
        if r is None:
            return

        r.name = name or r.id
        r.floor = floor
        r.x_m = x_m
        r.y_m = y_m
        r.w_m = w_m
        r.h_m = h_m
        r.height_m = height_m
        r.t_inside_c = t_inside_c
        r.air_change_1ph = air_change_1ph

        self.domain.normalize_room_geometry(r)

        if autowalls_enabled:
            from ..core.geometry import build_auto_walls_shared_merge

            self.domain.rebuild_autowalls_all(self.state, build_auto_walls=build_auto_walls_shared_merge)

    def rebuild_autowalls(self) -> None:

        self.domain.rebuild_autowalls_all(self.state, build_auto_walls=build_auto_walls_shared_merge)

    def compute_heatloads(self, vent_cfg: Optional[VentilationCfg] = None) -> Dict:
        cfg = self.state.project_cfg
        vent_cfg = vent_cfg or VentilationCfg()

        # Ensure decks (again idempotent; keeps app consistent)
        try:
            ensure_auto_decks(
                self.state.rooms.values(),
                self.state.elements,
                u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
                u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
                u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
            )
        except Exception:
            pass

        return calc_heatloads(
            list(self.state.rooms.values()),
            self.state.elements,
            t_out_c=float(cfg.t_out_c),
            vent_cfg=vent_cfg,
            thickness_mode=cfg.thickness_mode,
            area_shrink_factor=float(cfg.area_shrink_factor),
            floor_area_mode=cfg.floor_area_mode,
        )