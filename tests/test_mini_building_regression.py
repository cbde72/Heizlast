from __future__ import annotations

import pytest

from heizlast.core.anchors import update_edge_anchor_meta
from heizlast.core.config import VentilationCfg
from heizlast.core.heatload import calc_heatloads
from heizlast.domain.models import ElementModel, RoomModel


def _wall(room_id: str, length_m: float, uid: str) -> ElementModel:
    return ElementModel(
        room_id=room_id,
        floor="EG",
        element_type="Außenwand",
        area_m2=length_m * 2.5,
        u_w_m2k=0.30,
        length_m=length_m,
        height_m=2.5,
        uid=uid,
    )


def test_mini_building_heatload_regression_with_reheat():
    room = RoomModel(
        id="R1",
        floor="EG",
        name="Mini",
        x_m=0.0,
        y_m=0.0,
        w_m=4.0,
        h_m=3.0,
        height_m=2.5,
        t_inside_c=20.0,
        air_change_1ph=0.5,
    )
    elements = [
        _wall("R1", 4.0, "w1"),
        _wall("R1", 3.0, "w2"),
        _wall("R1", 4.0, "w3"),
        _wall("R1", 3.0, "w4"),
    ]

    results = calc_heatloads(
        [room],
        elements,
        t_out_c=-10.0,
        vent_cfg=VentilationCfg(c_air=0.34),
        floor_area_mode="inner",
        reheat_power_w_m2=10.0,
    )
    rr = results["R1"]

    # Transmission: outer walls 315 W + auto basement ceiling 43.2 W = 358.2 W
    assert rr["Q_trans_W"] == pytest.approx(358.2)

    # Ventilation: c_air 0.34 * n 0.5 1/h * V 30 m3 * dT 30 K = 153 W
    assert rr["Q_vent_W"] == pytest.approx(153.0)

    # Reheat: 10 W/m2 * A_ref 12 m2 = 120 W
    assert rr["Q_reheat_W"] == pytest.approx(120.0)
    assert rr["Q_sum_W"] == pytest.approx(631.2)
    assert rr["Q_W_per_m2"] == pytest.approx(52.6)
    assert any(line["line_type"] == "REHEAT" and line["Q_W"] == pytest.approx(120.0) for line in rr["lines"])


def test_outer_wall_uses_project_u_value_when_element_u_is_missing():
    room = RoomModel(
        id="R1",
        floor="EG",
        name="Mini",
        x_m=0.0,
        y_m=0.0,
        w_m=4.0,
        h_m=3.0,
        height_m=2.5,
        t_inside_c=20.0,
        air_change_1ph=0.0,
    )
    wall = ElementModel(
        room_id="R1",
        floor="EG",
        element_type="Außenwand",
        area_m2=10.0,
        u_w_m2k=0.0,
        factor=1.0,
    )

    rr = calc_heatloads(
        [room],
        [wall],
        t_out_c=-10.0,
        u_aussenwand_w_m2k=0.25,
        sync_auto_decks=False,
    )["R1"]

    line = next(line for line in rr["lines"] if line["line_type"] == "TRANSMISSION" and line["element_type"] == "Außenwand")
    assert line["U_W_m2K"] == pytest.approx(0.25)
    assert line["Q_W"] == pytest.approx(75.0)


def test_zero_factor_is_preserved_as_zero_transmission():
    room = RoomModel(
        id="R1",
        floor="DG",
        name="Dachraum",
        x_m=0.0,
        y_m=0.0,
        w_m=4.0,
        h_m=3.0,
        height_m=2.5,
        t_inside_c=20.0,
        air_change_1ph=0.0,
    )
    roof = ElementModel(
        room_id="R1",
        floor="DG",
        element_type="Dach",
        area_m2=12.0,
        u_w_m2k=0.30,
        factor=0.0,
    )

    rr = calc_heatloads([room], [roof], t_out_c=-10.0, sync_auto_decks=False)["R1"]

    line = next(line for line in rr["lines"] if line["line_type"] == "TRANSMISSION" and line["element_type"] == "Dach")
    assert line["factor"] == pytest.approx(0.0)
    assert line["Q_W"] == pytest.approx(0.0)
    assert rr["Q_trans_W"] == pytest.approx(0.0)


def test_window_and_door_use_project_u_value_when_missing():
    room = RoomModel(
        id="R1",
        floor="EG",
        name="Mini",
        x_m=0.0,
        y_m=0.0,
        w_m=4.0,
        h_m=3.0,
        height_m=2.5,
        t_inside_c=20.0,
        air_change_1ph=0.0,
    )
    window = ElementModel("R1", "Fenster", 2.0, 0.0, factor=1.0)
    door = ElementModel("R1", "Tür", 2.5, 0.0, factor=1.0)
    front_door = ElementModel("R1", "Haustür", 0.0, 0.0, factor=1.0, x0_m=0.0, y0_m=0.0, x1_m=1.0, y1_m=0.0, height_m=2.10)
    terrace_door = ElementModel("R1", "Terrassentür", 0.0, 0.0, factor=1.0, x0_m=0.0, y0_m=3.0, x1_m=1.5, y1_m=3.0)

    rr = calc_heatloads(
        [room],
        [window, door, front_door, terrace_door],
        t_out_c=-10.0,
        u_fenster_w_m2k=1.10,
        u_tuer_w_m2k=1.50,
        sync_auto_decks=False,
    )["R1"]

    lines = {line["element_type"]: line for line in rr["lines"] if line["line_type"] == "TRANSMISSION"}
    assert lines["Fenster"]["U_W_m2K"] == pytest.approx(1.10)
    assert lines["Tür"]["U_W_m2K"] == pytest.approx(1.50)
    assert lines["Haustür"]["U_W_m2K"] == pytest.approx(1.50)
    assert lines["Haustür"]["A_eff_m2"] == pytest.approx(2.10)
    assert lines["Terrassentür"]["U_W_m2K"] == pytest.approx(1.50)
    assert lines["Terrassentür"]["A_eff_m2"] == pytest.approx(1.5 * 2.01)
    assert rr["Q_trans_W"] == pytest.approx((1.10 * 2.0 + 1.50 * 2.5 + 1.50 * 2.10 + 1.50 * 1.5 * 2.01) * 30.0)


def test_window_and_door_are_subtracted_from_wall_by_anchor_without_line_geometry():
    room = RoomModel(
        id="R1",
        floor="EG",
        name="Mini",
        x_m=0.0,
        y_m=0.0,
        w_m=4.0,
        h_m=3.0,
        height_m=2.5,
        t_inside_c=20.0,
        air_change_1ph=0.0,
    )
    wall = ElementModel(
        room_id="R1",
        floor="EG",
        element_type="Außenwand",
        area_m2=10.0,
        u_w_m2k=0.30,
        factor=1.0,
        x0_m=0.0,
        y0_m=0.0,
        x1_m=4.0,
        y1_m=0.0,
        length_m=4.0,
        height_m=2.5,
        uid="wall_front",
    )
    window = ElementModel(
        room_id="R1",
        floor="EG",
        element_type="Fenster",
        area_m2=1.2,
        u_w_m2k=1.10,
        factor=1.0,
        length_m=1.0,
        height_m=1.2,
        uid="win_anchor",
        meta=update_edge_anchor_meta("", parent="wall_front", orient="H", c=0.0, a0=0.0, a1=4.0, s=1.0, w=1.0, rooms=("R1",)),
    )
    door = ElementModel(
        room_id="R1",
        floor="EG",
        element_type="Terrassentür",
        area_m2=0.0,
        u_w_m2k=1.50,
        factor=1.0,
        length_m=1.0,
        height_m=2.01,
        uid="door_anchor",
        meta=update_edge_anchor_meta("", parent="wall_front", orient="H", c=0.0, a0=0.0, a1=4.0, s=2.6, w=1.0, rooms=("R1",)),
    )

    rr = calc_heatloads([room], [wall, window, door], t_out_c=-10.0, sync_auto_decks=False)["R1"]

    lines = {line["element_type"]: line for line in rr["lines"] if line["line_type"] == "TRANSMISSION"}
    assert lines["Außenwand"]["A_open_m2"] == pytest.approx(1.2 + 2.01)
    assert lines["Außenwand"]["A_eff_m2"] == pytest.approx(10.0 - 3.21)
    assert lines["Terrassentür"]["A_eff_m2"] == pytest.approx(2.01)
    assert rr["A_openings_m2"] == pytest.approx(3.21)
    assert rr["Q_trans_W"] == pytest.approx((0.30 * (10.0 - 3.21) + 1.10 * 1.2 + 1.50 * 2.01) * 30.0)


def test_mini_building_mechanical_ventilation_with_heat_recovery():
    room = RoomModel(
        id="R1",
        floor="EG",
        name="Mini",
        x_m=0.0,
        y_m=0.0,
        w_m=4.0,
        h_m=3.0,
        height_m=2.5,
        t_inside_c=20.0,
        air_change_1ph=0.5,
    )

    rr = calc_heatloads(
        [room],
        [],
        t_out_c=-10.0,
        vent_cfg=VentilationCfg(c_air=0.34),
        ventilation_mode="mechanical",
        mech_supply_m3h=60.0,
        mech_exhaust_m3h=60.0,
        heat_recovery_efficiency=0.80,
    )["R1"]

    assert rr["Q_vent_natural_ref_W"] == pytest.approx(153.0)
    assert rr["Q_vent_mech_W"] == pytest.approx(122.4)
    assert rr["Q_vent_W"] == pytest.approx(122.4)
    assert any("eta_WRG=0.800" in line["notes"] for line in rr["lines"] if line["line_type"] == "VENTILATION")


def test_mechanical_ventilation_balances_infiltration_minimum_and_wrg_residual():
    room = RoomModel(
        id="R1",
        floor="EG",
        name="Mini",
        x_m=0.0,
        y_m=0.0,
        w_m=4.0,
        h_m=3.0,
        height_m=2.5,
        t_inside_c=20.0,
        air_change_1ph=0.5,
    )

    rr = calc_heatloads(
        [room],
        [],
        t_out_c=-10.0,
        vent_cfg=VentilationCfg(c_air=0.34),
        ventilation_mode="mechanical",
        min_air_change_1ph=0.5,
        infiltration_air_change_1ph=0.1,
        mech_supply_m3h=9.0,
        mech_exhaust_m3h=9.0,
        heat_recovery_efficiency=0.80,
    )["R1"]

    # V=30 m3, V_min=15, V_inf=3, mechanical room flow=9.
    # Effective outdoor flow = 3 + (15-9) + 9*(1-0.8) = 10.8 m3/h.
    assert rr["ventilation_vdot_effective_m3h"] == pytest.approx(10.8)
    assert rr["Q_vent_W"] == pytest.approx(110.16)
    assert any("Vdot_min_uncovered=6.000" in line["notes"] for line in rr["lines"] if line["line_type"] == "VENTILATION")


def test_mini_building_reheat_can_be_derived_from_duration_and_drop():
    room = RoomModel(id="R1", floor="EG", name="Mini", x_m=0.0, y_m=0.0, w_m=4.0, h_m=3.0)

    rr = calc_heatloads(
        [room],
        [],
        t_out_c=-10.0,
        reheat_power_w_m2=0.0,
        reheat_duration_h=2.0,
        reheat_temp_drop_k=4.0,
        reheat_capacity_wh_m2k=20.0,
    )["R1"]

    assert rr["q_reheat_W_m2"] == pytest.approx(40.0)
    assert rr["Q_reheat_W"] == pytest.approx(480.0)
