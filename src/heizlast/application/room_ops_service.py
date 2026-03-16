from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ..domain.house_state import HouseState
from ..domain.services.house_domain_service import HouseDomainService
from ..domain.services.room_operation_service import RoomOperationRecord, RoomOperationService


@dataclass
class RoomOperationsApplicationService:
    """Application-facing façade for split/merge/subtract room operations."""

    domain: HouseDomainService
    build_auto_walls: Optional[Callable] = field(default=None)

    def __post_init__(self) -> None:
        if self.build_auto_walls is None:
            from ..core.geometry import build_auto_walls_shared_merge
            self.build_auto_walls = build_auto_walls_shared_merge

    def _service(self) -> RoomOperationService:
        return RoomOperationService(domain=self.domain, build_auto_walls=self.build_auto_walls)

    def run(self, state: HouseState, op_name: str, *args, **kwargs) -> Optional[RoomOperationRecord]:
        op = getattr(self._service(), op_name, None)
        if op is None:
            return None
        return op(state, *args, **kwargs)
