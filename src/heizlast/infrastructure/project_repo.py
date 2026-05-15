from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
from ..domain.models import ElementModel

from ..core.csv_io import load_rooms, load_elements, save_rooms, save_elements
from ..domain.models import RoomModel
from ..configs.project_config import ProjectCfg, load_project_cfg, save_project_cfg


@dataclass
class ProjectData:
    rooms: List[RoomModel]
    elements: List[ElementModel]
    cfg: ProjectCfg
    rooms_path: Path
    elements_path: Path


class ProjectRepository:
    """Persistenz-Schicht: lädt/speichert rooms.csv, *_elements.csv und Projekt-JSON.
    MainWindow bleibt UI-Orchestrator.
    """

    def __init__(self, delimiter: str = ";"):
        self.delimiter = delimiter

    def derive_elements_path(self, rooms_path: Path) -> Path:
        return rooms_path.with_name(rooms_path.stem + "_elements.csv")

    def json_path_for_rooms(self, rooms_path: Path) -> Path:
        return rooms_path.with_suffix(".json")

    def load(self, rooms_path: Path) -> ProjectData:
        elements_path = self.derive_elements_path(rooms_path)
        rooms = load_rooms(str(rooms_path), delimiter=self.delimiter)
        elements = load_elements(str(elements_path), delimiter=self.delimiter) if elements_path.exists() else []

        cfg_path = self.json_path_for_rooms(rooms_path)
        if cfg_path.exists():
            try:
                cfg = load_project_cfg(cfg_path)
            except Exception:
                cfg = ProjectCfg()
        else:
            cfg = ProjectCfg()

        return ProjectData(
            rooms=rooms,
            elements=elements,
            cfg=cfg,
            rooms_path=rooms_path,
            elements_path=elements_path,
        )

    def save(self, rooms_path: Path, rooms: List[RoomModel], elements: List[ElementModel], cfg: ProjectCfg) -> None:
        elements_path = self.derive_elements_path(rooms_path)

        save_rooms(str(rooms_path), rooms, delimiter=self.delimiter)
        save_elements(str(elements_path), elements, delimiter=self.delimiter)

        cfg_path = self.json_path_for_rooms(rooms_path)
        try:
            save_project_cfg(cfg_path, cfg)
        except Exception:
            # ProjectCfg ist nice-to-have; CSVs sind die harte Persistenz.
            pass