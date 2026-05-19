from __future__ import annotations

import pytest

from heizlast.core.ground_model import GroundModelCfg
from heizlast.core.heatload import calc_heatloads
from heizlast.domain.models import ElementModel, RoomModel


def test_din_ts_ground_mode_uses_separate_reduction_factor():
    room = RoomModel(id="R1", floor="EG", name="Mini", x_m=0.0, y_m=0.0, w_m=4.0, h_m=3.0)
    slab = ElementModel(
        room_id="R1",
        floor="EG",
        element_type="Bodenplatte",
        area_m2=12.0,
        u_w_m2k=0.40,
        meta="ground=slab",
    )

    rr = calc_heatloads(
        [room],
        [slab],
        t_out_c=-10.0,
        ground_cfg=GroundModelCfg(mode="din_ts", din_ts_f_slab=0.50, din_ts_f_wall=0.50),
    )["R1"]

    # Tg = -10 + 0.50 * (20 - -10) = 5 °C, dT = 15 K, Q = 0.40 * 12 * 15 = 72 W.
    assert rr["Q_trans_ground_W"] == pytest.approx(72.0)
    assert rr["ground_mode"] == "din_ts"
    assert rr["ground_din_ts_f_slab"] == pytest.approx(0.50)
    slab_line = next(line for line in rr["lines"] if line["line_type"] == "TRANSMISSION" and line["element_type"] == "Bodenplatte")
    assert slab_line["surface_role"] == "floor_ground"
    assert slab_line["perimeter_m"] == pytest.approx(14.0)
    assert slab_line["B_prime_m"] == pytest.approx(12.0 / 7.0)
    assert "ground_method=din_ts" in slab_line["notes"]


def test_ground_elements_use_project_u_value_when_element_u_is_missing():
    room = RoomModel(id="R1", floor="EG", name="Mini", x_m=0.0, y_m=0.0, w_m=4.0, h_m=3.0)
    slab = ElementModel(
        room_id="R1",
        floor="EG",
        element_type="Bodenplatte",
        area_m2=12.0,
        u_w_m2k=0.0,
        meta="ground=slab",
    )

    rr = calc_heatloads(
        [room],
        [slab],
        t_out_c=-10.0,
        ground_cfg=GroundModelCfg(mode="din_ts", din_ts_f_slab=0.50),
        u_bodenplatte_w_m2k=0.32,
    )["R1"]

    line = next(line for line in rr["lines"] if line["line_type"] == "TRANSMISSION" and line["element_type"] == "Bodenplatte")
    assert line["U_W_m2K"] == pytest.approx(0.32)
    assert line["Q_W"] == pytest.approx(57.6)
