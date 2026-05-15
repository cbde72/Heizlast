from __future__ import annotations
from pathlib import Path
from typing import List, Protocol, Tuple
from ..domain.models import ElementModel

from ..domain.models import RoomModel
from ..configs.project_config import ProjectCfg


class ProjectRepository(Protocol):
    """IO port: load/save project data (rooms/elements + project cfg)."""

    def load(self, rooms_csv_path: Path) -> Tuple[List[RoomModel], List[ElementModel], ProjectCfg, Path]:
        """Returns (rooms, elements, project_cfg, elements_csv_path)."""
        ...

    def save(
        self,
        rooms_csv_path: Path,
        elements_csv_path: Path,
        rooms: List[RoomModel],
        elements: List[ElementModel],
        cfg: ProjectCfg,
    ) -> None:
        ...


class SettingsStore(Protocol):
    """Persistence port for small UI/app settings."""

    def get_bool(self, key: str, default: bool = False) -> bool: ...
    def set_bool(self, key: str, value: bool) -> None: ...


class ReportExporter(Protocol):
    """Export port (PDF/PNGs/CSVs). Kept minimal for Step 2."""

    def export_heatload_pdf(
        self,
        pdf_path: Path,
        rooms: List[RoomModel],
        elements: List[ElementModel],
        results: dict,
        t_out_c: float,
    ) -> None:
        ...