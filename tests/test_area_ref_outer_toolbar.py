from __future__ import annotations

from pathlib import Path

from heizlast.core.heatload import calc_heatloads
from heizlast.domain.models import ElementModel, RoomModel


ROOT = Path(__file__).resolve().parents[1]
BUILD_MIXIN = ROOT / 'src' / 'heizlast' / 'ui' / 'build_mixin.py'
OVERLAY_MIXIN = ROOT / 'src' / 'heizlast' / 'ui' / 'overlay_mixin.py'


def _outer_wall(room_id: str, x0: float, y0: float, x1: float, y1: float, uid: str) -> ElementModel:
    length = abs(x1 - x0) + abs(y1 - y0)
    return ElementModel(
        room_id=room_id,
        floor='EG',
        element_type='Außenwand',
        area_m2=length * 2.5,
        u_w_m2k=0.3,
        x0_m=x0,
        y0_m=y0,
        x1_m=x1,
        y1_m=y1,
        length_m=length,
        height_m=2.5,
        uid=uid,
    )


def test_toolbar_contains_autowalls_window_and_area_ref_actions():
    src = BUILD_MIXIN.read_text(encoding='utf-8')
    assert 'self.act_autowalls_enabled,' in src
    assert 'self.act_add_window,' in src
    assert 'self.act_area_ref_outer,' in src


def test_area_ref_checkbox_uses_shared_toggle_handler():
    src = BUILD_MIXIN.read_text(encoding='utf-8')
    assert 'self.cb_area_ref_outer.toggled.connect(self._on_toggle_area_ref_outer_action)' in src

    overlay_src = OVERLAY_MIXIN.read_text(encoding='utf-8')
    assert 'self.project_cfg.floor_area_mode = "outer" if checked else "inner"' in overlay_src
    assert 'self.act_area_ref_outer.setChecked(checked)' in overlay_src


def test_calc_heatloads_uses_outer_or_inner_reference_area_for_wpm2():
    room = RoomModel(id='R1', floor='EG', name='R1', x_m=0.0, y_m=0.0, w_m=4.0, h_m=3.0)
    elements = [
        _outer_wall('R1', 0.0, 0.0, 4.0, 0.0, 'w_top'),
        _outer_wall('R1', 4.0, 0.0, 4.0, 3.0, 'w_right'),
        _outer_wall('R1', 4.0, 3.0, 0.0, 3.0, 'w_bottom'),
        _outer_wall('R1', 0.0, 3.0, 0.0, 0.0, 'w_left'),
    ]

    res_inner = calc_heatloads([room], list(elements), t_out_c=-10.0, floor_area_mode='inner')['R1']
    res_outer = calc_heatloads([room], list(elements), t_out_c=-10.0, floor_area_mode='outer')['R1']

    assert res_inner['floor_area_mode'] == 'inner'
    assert res_outer['floor_area_mode'] == 'outer'
    assert res_inner['A_ref_m2'] == res_inner['A_in_m2']
    assert res_outer['A_ref_m2'] == res_outer['A_out_m2']
    assert res_outer['A_out_m2'] > res_inner['A_in_m2']
    assert abs(res_inner['Q_W_per_m2'] - (res_inner['Q_sum_W'] / res_inner['A_ref_m2'])) < 1e-9
    assert abs(res_outer['Q_W_per_m2'] - (res_outer['Q_sum_W'] / res_outer['A_ref_m2'])) < 1e-9


def test_toolbar_werkzeuge_group_contains_autowalls():
    src = BUILD_MIXIN.read_text(encoding='utf-8')
    assert '("Werkzeuge", [' in src
    assert 'self.act_autowalls_enabled,' in src


def test_autowalls_toolbar_button_is_latched_toggle_action():
    src = BUILD_MIXIN.read_text(encoding='utf-8')
    assert '"Auto-Wände aktiv"' in src
    assert 'checkable=True' in src
    assert 'icon=self._toolbar_icon("auto_walls")' in src
