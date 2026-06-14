from __future__ import annotations

from pathlib import Path

import pytest

from heizlast.core.heatload import calc_heatloads, is_unheated_room
from heizlast.domain.models import ElementModel, RoomModel


ROOT = Path(__file__).resolve().parents[1]


def _wall(room_id: str, uid: str = "w1") -> ElementModel:
    return ElementModel(
        room_id=room_id,
        floor="KG",
        element_type="Außenwand",
        area_m2=10.0,
        u_w_m2k=0.5,
        x0_m=0.0,
        y0_m=0.0,
        x1_m=4.0,
        y1_m=0.0,
        length_m=4.0,
        height_m=2.5,
        uid=uid,
    )


def test_unheated_room_is_excluded_from_heatload_balance():
    room = RoomModel(
        id="KG1",
        floor="KG",
        name="Unbeheizter Keller",
        x_m=0.0,
        y_m=0.0,
        w_m=4.0,
        h_m=3.0,
        t_inside_c=12.0,
        air_change_1ph=0.3,
        usage_type="KELLER",
    )

    assert is_unheated_room(room)

    rr = calc_heatloads([room], [_wall("KG1")], t_out_c=-10.0, sync_auto_decks=False)["KG1"]

    assert rr["is_heated_zone"] is False
    assert rr["excluded_from_heatload"] is True
    assert rr["Q_trans_W"] == pytest.approx(0.0)
    assert rr["Q_vent_W"] == pytest.approx(0.0)
    assert rr["Q_reheat_W"] == pytest.approx(0.0)
    assert rr["Q_sum_W"] == pytest.approx(0.0)
    assert rr["Q_W_per_m2"] == pytest.approx(0.0)
    assert rr["A_env_out_m2"] == pytest.approx(0.0)
    assert all(float(line.get("Q_W", 0.0) or 0.0) == pytest.approx(0.0) for line in rr["lines"])
    assert any(float(line.get("Q_W_raw_excluded", 0.0) or 0.0) > 0.0 for line in rr["lines"])


def test_unheated_room_does_not_receive_mechanical_ventilation_share():
    heated = RoomModel(
        id="EG1",
        floor="EG",
        name="Wohnzimmer",
        x_m=0.0,
        y_m=0.0,
        w_m=5.0,
        h_m=4.0,
        t_inside_c=20.0,
        air_change_1ph=0.5,
        usage_type="WOHNEN",
    )
    unheated = RoomModel(
        id="KG1",
        floor="KG",
        name="Keller",
        x_m=0.0,
        y_m=0.0,
        w_m=5.0,
        h_m=4.0,
        t_inside_c=12.0,
        air_change_1ph=0.3,
        usage_type="UNBEHEIZT",
    )

    results = calc_heatloads(
        [heated, unheated],
        [_wall("EG1", "w_eg"), _wall("KG1", "w_kg")],
        t_out_c=-10.0,
        ventilation_mode="mechanical",
        mech_supply_m3h=100.0,
        heat_recovery_efficiency=0.0,
        min_air_change_1ph=0.0,
        infiltration_air_change_1ph=0.0,
        sync_auto_decks=False,
    )

    assert results["KG1"]["Q_sum_W"] == pytest.approx(0.0)
    assert results["KG1"]["ventilation_vdot_mech_room_m3h"] == pytest.approx(0.0)
    assert results["EG1"]["ventilation_vdot_mech_room_m3h"] == pytest.approx(100.0)
    assert results["EG1"]["Q_sum_W"] > 0.0


def test_gui_hides_heat_values_for_excluded_rooms():
    graphics_src = (ROOT / "src" / "heizlast" / "ui" / "graphics.py").read_text(encoding="utf-8")
    redraw_src = (ROOT / "src" / "heizlast" / "ui" / "redraw_mixin.py").read_text(encoding="utf-8")
    presenter_src = (ROOT / "src" / "heizlast" / "presentation" / "plan_presenter.py").read_text(encoding="utf-8")
    comfort_src = (ROOT / "src" / "heizlast" / "ui" / "comfort_mixin.py").read_text(encoding="utf-8")

    assert "def set_heat_excluded" in graphics_src
    assert "unbeheizt" in graphics_src
    assert 'res.get("excluded_from_heatload", False)' in redraw_src
    assert 'res.get("excluded_from_heatload", False)' in presenter_src
    assert 'not bool(rr.get("excluded_from_heatload", False))' in comfort_src
