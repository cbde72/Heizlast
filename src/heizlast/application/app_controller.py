from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from ..domain.house_state import HouseState
from ..domain.services.house_domain_service import HouseDomainService
from ..domain.services.room_operation_service import RoomOperationRecord, RoomOperationService
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

    def _room_operation_service(self) -> RoomOperationService:
        from ..core.geometry import build_auto_walls_shared_merge
        return RoomOperationService(domain=self.domain, build_auto_walls=build_auto_walls_shared_merge)

    def _run_room_operation(self, op_name: str, *args, **kwargs) -> Optional[RoomOperationRecord]:
        service = self._room_operation_service()
        op = getattr(service, op_name, None)
        if op is None:
            return None
        return op(self.state, *args, **kwargs)

    def load_project(self, rooms_csv_path: Path) -> Tuple[Path, Path]:
        rooms, elements, cfg, elements_csv_path = self.repo.load(rooms_csv_path)

        for r in rooms:
            try:
                r.ensure_polygon()
                self.domain.normalize_room_geometry(r)
            except Exception:
                pass
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

        r.ensure_polygon()
        r.name = name or r.id
        r.floor = floor
        if getattr(r, "is_axis_aligned_rect_polygon", lambda: False)():
            r.resize_rect_polygon_from_bbox(x_m, y_m, w_m, h_m)
        else:
            r.move_to(x_m, y_m)
        r.height_m = height_m
        r.t_inside_c = t_inside_c
        r.air_change_1ph = air_change_1ph

        self.domain.normalize_room_geometry(r)

        if autowalls_enabled:
            from ..core.geometry import build_auto_walls_shared_merge

            self.domain.rebuild_autowalls_all(self.state, build_auto_walls=build_auto_walls_shared_merge)

    def rebuild_autowalls(self) -> None:
        from ..core.geometry import build_auto_walls_shared_merge
        self.domain.rebuild_autowalls_all(self.state, build_auto_walls=build_auto_walls_shared_merge)


    def merge_rooms(self, room_ids: list[str]) -> Optional[RoomOperationRecord]:
        return self._run_room_operation('merge_rooms', room_ids)

    def subtract_rooms(self, base_room_id: str, cutter_room_ids: list[str]) -> Optional[RoomOperationRecord]:
        return self._run_room_operation('subtract_rooms', base_room_id, cutter_room_ids)

    def split_room(self, room_id: str, *, orientation: str, coord: float) -> Optional[RoomOperationRecord]:
        return self._run_room_operation('split_room', room_id, orientation=orientation, coord=coord)

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