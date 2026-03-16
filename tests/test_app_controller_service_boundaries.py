from heizlast.application.app_controller import AppController
from heizlast.application.heatload_service import HeatloadComputationService
from heizlast.application.room_ops_service import RoomOperationsApplicationService
from heizlast.configs.project_config import ProjectCfg
from heizlast.domain.house_state import HouseState
from heizlast.domain.services.house_domain_service import HouseDomainService


class _DummyRepo:
    def load(self, rooms_csv_path):
        raise NotImplementedError

    def save(self, *args, **kwargs):
        return None


class _SpyHeatloads(HeatloadComputationService):
    def __init__(self):
        self.calls = []

    def compute(self, state, vent_cfg=None):
        self.calls.append((state, vent_cfg))
        return {'ok': True}


class _SpyRoomOps(RoomOperationsApplicationService):
    def __init__(self):
        self.calls = []

    def run(self, state, op_name, *args, **kwargs):
        self.calls.append((state, op_name, args, kwargs))
        return 'room-op-record'


def test_app_controller_delegates_to_application_services():
    state = HouseState(rooms={}, elements=[], project_cfg=ProjectCfg())
    domain = HouseDomainService()
    heatloads = _SpyHeatloads()
    room_ops = _SpyRoomOps()
    ctrl = AppController(state=state, domain=domain, repo=_DummyRepo(), heatloads=heatloads, room_ops=room_ops)

    assert ctrl.compute_heatloads() == {'ok': True}
    assert heatloads.calls and heatloads.calls[0][0] is state

    rec = ctrl.merge_rooms(['r1', 'r2'])
    assert rec == 'room-op-record'
    assert room_ops.calls == [(state, 'merge_rooms', (['r1', 'r2'],), {})]
