from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
from ..domain.models import ElementModel

from ..core.csv_io import load_rooms, load_elements, save_rooms, save_elements
from ..configs.project_config import ProjectCfg, load_project_cfg, save_project_cfg
from ..core.config import CSV_DELIMITER
from ..domain.models import RoomModel


class CSVProjectRepository:
    """Concrete IO implementation using the existing CSV/JSON functions."""

    def _derive_elements_path(self, rooms_path: Path) -> Path:
        name = rooms_path.name
        stem = rooms_path.stem
        if name.lower() == "rooms.csv":
            return rooms_path.with_name("elements.csv")
        if stem.lower().endswith("_rooms"):
            return rooms_path.with_name(stem[:-6] + "_elements.csv")
        return rooms_path.with_name(stem + "_elements.csv")

    def _project_json_path_for_rooms(self, rooms_csv_path: Path) -> Path:
        return rooms_csv_path.with_name(f"{rooms_csv_path.stem}.project.json")


    def load(self, rooms_csv_path: Path) -> Tuple[List[RoomModel], List[ElementModel], ProjectCfg, Path]:
        elements_csv_path = self._derive_elements_path(rooms_csv_path)
        rooms = load_rooms(str(rooms_csv_path), delimiter=CSV_DELIMITER)
        elements = load_elements(str(elements_csv_path), delimiter=CSV_DELIMITER) if elements_csv_path.exists() else []

        cfg_path = self._project_json_path_for_rooms(rooms_csv_path)
        if cfg_path.exists():
            try:
                cfg = load_project_cfg(cfg_path)
            except Exception:
                cfg = ProjectCfg()
        else:
            cfg = ProjectCfg()

        return rooms, elements, cfg, elements_csv_path

    def save(
        self,
        rooms_csv_path: Path,
        elements_csv_path: Path,
        rooms: List[RoomModel],
        elements: List[ElementModel],
        cfg: ProjectCfg,
    ) -> None:
        save_rooms(str(rooms_csv_path), rooms, delimiter=CSV_DELIMITER)
        save_elements(str(elements_csv_path), elements, delimiter=CSV_DELIMITER)
        cfg_path = self._project_json_path_for_rooms(rooms_csv_path)
        try:
            save_project_cfg(cfg_path, cfg)
        except Exception:
            pass