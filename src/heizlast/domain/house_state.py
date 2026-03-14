from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..configs.project_config import ProjectCfg
from .models import ElementModel, RoomModel


@dataclass
class HouseState:
    """Single Source of Truth for the project data (Domain state, Qt-free)."""

    rooms: Dict[str, RoomModel]
    elements: List[ElementModel]
    project_cfg: ProjectCfg
