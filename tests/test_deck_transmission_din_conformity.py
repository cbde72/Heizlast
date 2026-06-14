import pytest

from heizlast.configs.project_config import ProjectCfg
from heizlast.core.config import VentilationCfg
from heizlast.core.heatload import calc_heatloads, ensure_auto_decks
from heizlast.core.ground_model import GroundModelCfg
from heizlast.domain.house_state import HouseState
from heizlast.domain.models import ElementModel, RoomModel
from heizlast.application.heatload_service import HeatloadComputationService
from heizlast.core.din_status import assess_din_status


def _line(rr, element_type):
    return next(line for line in rr["lines"] if line["line_type"] == "TRANSMISSION" and line["element_type"] == element_type)


def _lines(rr, element_type):
    return [line for line in rr["lines"] if line["line_type"] == "TRANSMISSION" and line["element_type"] == element_type]


def test_deck_transmission_uses_din_buckets_and_project_u_values():
    eg = RoomModel("EG1", "EG", "EG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)
    dg = RoomModel("DG1", "DG", "DG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)

    results = calc_heatloads(
        [eg, dg],
        [],
        t_out_c=-10.0,
        t_keller_c=14.0,
        t_oben_c=12.0,
        u_kellerdecke_w_m2k=0.60,
        u_eg_geschossdecke_w_m2k=0.40,
        u_dg_geschossdecke_w_m2k=0.20,
    )

    eg_rr = results["EG1"]
    kd = _line(eg_rr, "Kellerdecke")
    gd = _line(eg_rr, "Geschossdecke")
    assert kd["boundary_bucket"] == "basement"
    assert kd["surface_role"] == "deck_basement"
    assert kd["boundary_label"] == "unbeheizter Keller"
    assert kd["U_W_m2K"] == pytest.approx(0.60)
    assert kd["dT_K"] == pytest.approx(6.0)
    assert kd["A_eff_m2"] == pytest.approx(12.0)
    assert kd["Q_W"] == pytest.approx(43.2)

    assert gd["boundary_bucket"] == "interzone"
    assert gd["surface_role"] == "deck_interzone"
    assert gd["boundary_label"] == "Interzone"
    assert gd["U_W_m2K"] == pytest.approx(0.40)
    assert gd["dT_K"] == pytest.approx(0.0)
    assert gd["Q_W"] == pytest.approx(0.0)
    assert eg_rr["Q_trans_interzone_W"] == pytest.approx(0.0)

    dg_rr = results["DG1"]
    sd = _line(dg_rr, "Speicherdecke")
    assert sd["boundary_bucket"] == "attic"
    assert sd["surface_role"] == "deck_attic"
    assert sd["boundary_label"] == "Dachboden/Abseite unbeheizt"
    assert sd["U_W_m2K"] == pytest.approx(0.20)
    assert sd["dT_K"] == pytest.approx(8.0)
    assert sd["Q_W"] == pytest.approx(19.2)
    assert dg_rr["Q_trans_dachraum_W"] == pytest.approx(19.2)


def test_roof_transmission_is_classified_separately_from_attic_deck():
    room = RoomModel("DG1", "DG", "DG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)
    roof = ElementModel(
        room_id="DG1",
        element_type="Dach",
        area_m2=20.0,
        u_w_m2k=0.20,
        factor=1.0,
        meta="boundary=outside|attic_auto|attic_part=roof_left",
    )

    rr = calc_heatloads([room], [roof], t_out_c=-10.0, sync_auto_decks=False)["DG1"]
    line = _line(rr, "Dach")

    assert line["surface_role"] == "roof"
    assert line["boundary_bucket"] == "external"
    assert line["Q_W"] == pytest.approx(120.0)
    assert rr["Q_trans_out_W"] == pytest.approx(120.0)


def test_heatload_service_does_not_overwrite_project_deck_u_values():
    cfg = ProjectCfg()
    cfg.u_kellerdecke_w_m2k = 0.61
    cfg.u_eg_geschossdecke_w_m2k = 0.41
    cfg.u_dg_geschossdecke_w_m2k = 0.21
    rooms = {
        "EG1": RoomModel("EG1", "EG", "EG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0),
        "DG1": RoomModel("DG1", "DG", "DG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0),
    }
    state = HouseState(rooms=rooms, elements=[], project_cfg=cfg)

    results = HeatloadComputationService().compute(state, VentilationCfg())

    assert _line(results["EG1"], "Kellerdecke")["U_W_m2K"] == pytest.approx(0.61)
    assert _line(results["EG1"], "Geschossdecke")["U_W_m2K"] == pytest.approx(0.41)
    assert _line(results["DG1"], "Speicherdecke")["U_W_m2K"] == pytest.approx(0.21)


def test_explicit_boundary_meta_can_classify_deck_as_unheated_attic():
    room = RoomModel("R1", "EG", "EG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)
    element = ElementModel(
        room_id="R1",
        element_type="Decke",
        area_m2=12.0,
        u_w_m2k=0.30,
        factor=1.0,
        meta="boundary=attic_unheated|t_adj_c=10.0",
    )

    rr = calc_heatloads([room], [element], t_out_c=-10.0)["R1"]
    line = _line(rr, "Decke")

    assert line["boundary_bucket"] == "attic"
    assert line["boundary_label"] == "Dachboden/Abseite unbeheizt"
    assert line["dT_K"] == pytest.approx(10.0)
    assert line["Q_W"] == pytest.approx(36.0)


def test_manual_basement_boundary_uses_unheated_basement_temperature_aliases():
    room = RoomModel("R1", "EG", "EG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)
    element = ElementModel(
        room_id="R1",
        element_type="Decke",
        area_m2=10.0,
        u_w_m2k=0.50,
        factor=1.0,
        meta="boundary=basement",
    )

    rr = calc_heatloads([room], [element], t_out_c=-10.0, t_keller_c=14.0, sync_auto_decks=False)["R1"]
    line = _line(rr, "Decke")

    assert line["boundary_bucket"] == "basement"
    assert line["dT_K"] == pytest.approx(6.0)
    assert line["Q_W"] == pytest.approx(30.0)


def test_inner_wall_without_boundary_is_not_treated_as_outside():
    room = RoomModel("R1", "EG", "EG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)
    element = ElementModel(
        room_id="R1",
        element_type="Innenwand",
        area_m2=10.0,
        u_w_m2k=1.0,
        factor=1.0,
    )

    rr = calc_heatloads([room], [element], t_out_c=-10.0, sync_auto_decks=False)["R1"]
    line = _line(rr, "Innenwand")

    assert line["boundary_bucket"] == "interzone"
    assert line["dT_K"] == pytest.approx(0.0)
    assert rr["Q_trans_out_W"] == pytest.approx(0.0)
    assert rr["Q_trans_interzone_W"] == pytest.approx(0.0)


def test_speicherdecke_uses_room_area_instead_of_manual_bbox_area():
    room = RoomModel("DG1", "DG", "DG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)
    element = ElementModel(
        room_id="DG1",
        element_type="Speicherdecke",
        area_m2=99.0,
        u_w_m2k=0.20,
        factor=1.0,
    )

    rr = calc_heatloads([room], [element], t_out_c=-10.0, t_oben_c=12.0, sync_auto_decks=False)["DG1"]
    line = _line(rr, "Speicherdecke")

    assert line["A_eff_m2"] == pytest.approx(12.0)
    assert line["Q_W"] == pytest.approx(19.2)
    assert rr["A_env_dachraum_m2"] == pytest.approx(12.0)


def test_din_status_contains_deck_neighbor_zone_checkpoint():
    cfg = ProjectCfg()
    element = ElementModel(
        "R1",
        "Speicherdecke",
        12.0,
        0.25,
        meta=(
            "auto_deck=1|deck_kind=speicher|adj_floor=OBEN|boundary=attic_unheated|"
            "t_adj_c=12.0|t_source=project_t_oben_c|u_source=Bauteilkatalog|"
            "area_source=room_floor_area|boundary_source=Projektangabe|assumptions_confirmed=1"
        ),
    )

    status = assess_din_status(
        results={"R1": {"Q_trans_W": 24.0, "Q_trans_dachraum_W": 24.0, "Q_vent_W": 0.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
        elements=[element],
    )

    assert any(row[0] == "Decken / Nachbarzonen" and row[-1] == "✓" for row in status.conformity_rows)
    assert any(row[0] == "Decken / Nachbarzonen" and row[1] == "✓" for row in status.validation_rows)


def test_din_status_marks_interzone_without_adjacent_temperature_yellow():
    cfg = ProjectCfg()
    element = ElementModel(
        "R1",
        "Innenwand",
        10.0,
        0.50,
        factor=1.0,
        meta="boundary=interzone|u_source=Bauteilkatalog|area_source=Plan",
    )

    status = assess_din_status(
        results={"R1": {"Q_trans_W": 0.0, "Q_trans_interzone_W": 0.0, "Q_vent_W": 0.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
        elements=[element],
    )

    assert any(row[0] == "Interzone / Nachbarräume" and row[-1] == "△" for row in status.conformity_rows)
    assert any("ohne t_adj_c" in row[2] for row in status.validation_rows if row[0] == "Interzone / Nachbarräume")


def test_din_status_requires_confirmed_auto_deck_assumptions():
    cfg = ProjectCfg()
    element = ElementModel(
        "R1",
        "Speicherdecke",
        12.0,
        0.25,
        meta=(
            "auto_deck=1|deck_kind=speicher|adj_floor=OBEN|boundary=attic_unheated|"
            "t_adj_c=12.0|t_source=project_t_oben_c|u_source=Bauteilkatalog|"
            "area_source=room_floor_area|boundary_source=Projektangabe|assumptions_confirmed=0"
        ),
    )

    status = assess_din_status(
        results={"R1": {"Q_trans_W": 24.0, "Q_trans_dachraum_W": 24.0, "Q_vent_W": 0.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
        elements=[element],
    )

    assert any(row[0] == "Decken / Nachbarzonen" and row[-1] == "△" for row in status.conformity_rows)
    assert any("Auto-Decken-Annahmen nicht bestätigt" in row[2] for row in status.validation_rows if row[0] == "Decken / Nachbarzonen")


def test_auto_decks_are_idempotent_and_not_counted_twice():
    room = RoomModel("EG1", "EG", "EG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)
    elements = []
    ensure_auto_decks(
        [room],
        elements,
        t_keller_c=14.0,
        t_oben_c=12.0,
        u_value_source="Bauteilkatalog",
        boundary_source="Projektangabe",
        auto_deck_assumptions_confirmed=True,
    )
    ensure_auto_decks(
        [room],
        elements,
        t_keller_c=14.0,
        t_oben_c=12.0,
        u_value_source="Bauteilkatalog",
        boundary_source="Projektangabe",
        auto_deck_assumptions_confirmed=True,
    )

    assert sum(1 for e in elements if e.element_type == "Kellerdecke") == 1
    assert sum(1 for e in elements if e.element_type == "Geschossdecke") == 1
    kd = next(e for e in elements if e.element_type == "Kellerdecke")
    assert "boundary=basement_unheated" in kd.meta
    assert "t_source=project_t_keller_c" in kd.meta
    assert "u_source=Bauteilkatalog" in kd.meta
    assert "assumptions_confirmed=1" in kd.meta

    elements.append(
        ElementModel(
            room_id="EG1",
            element_type="Kellerdecke",
            area_m2=12.0,
            u_w_m2k=0.45,
            uid="deck_duplicate_keller",
            meta="auto_deck=1|deck_kind=keller|adj_floor=KG",
        )
    )

    rr = calc_heatloads([room], elements, t_out_c=-10.0, t_keller_c=14.0)["EG1"]
    assert len(_lines(rr, "Kellerdecke")) == 1
    assert rr["Q_trans_keller_W"] == pytest.approx(32.4)


def test_manual_deck_replaces_equivalent_auto_deck_in_calculation():
    room = RoomModel("EG1", "EG", "EG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)
    manual = ElementModel(
        room_id="EG1",
        element_type="Kellerdecke",
        area_m2=12.0,
        u_w_m2k=0.70,
        uid="manual_kellerdecke",
        meta="deck_kind=keller|adj_floor=KG",
    )

    rr = calc_heatloads([room], [manual], t_out_c=-10.0, t_keller_c=14.0)["EG1"]

    assert len(_lines(rr, "Kellerdecke")) == 1
    line = _line(rr, "Kellerdecke")
    assert line["uid"] == "manual_kellerdecke"
    assert line["U_W_m2K"] == pytest.approx(0.70)
    assert rr["Q_trans_keller_W"] == pytest.approx(50.4)


def test_manual_ground_slab_suppresses_auto_basement_deck_for_same_room():
    room = RoomModel("EG1", "EG", "EG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)
    slab = ElementModel(
        room_id="EG1",
        element_type="Bodenplatte",
        area_m2=12.0,
        u_w_m2k=0.40,
        uid="manual_bodenplatte",
        meta="ground=slab",
    )

    rr = calc_heatloads(
        [room],
        [slab],
        t_out_c=-10.0,
        t_keller_c=14.0,
        ground_cfg=GroundModelCfg(mode="din_ts", din_ts_f_slab=0.50),
    )["EG1"]

    assert not _lines(rr, "Kellerdecke")
    assert len(_lines(rr, "Bodenplatte")) == 1
    assert rr["Q_trans_keller_W"] == pytest.approx(0.0)
    assert rr["Q_trans_ground_W"] == pytest.approx(72.0)


def test_duplicate_manual_ground_slabs_are_counted_once():
    room = RoomModel("EG1", "EG", "EG", 0.0, 0.0, 4.0, 3.0, t_inside_c=20.0)
    slab1 = ElementModel("EG1", "Bodenplatte", 12.0, 0.40, uid="slab_a", meta="ground=slab")
    slab2 = ElementModel("EG1", "Bodenplatte", 12.0, 0.40, uid="slab_b", meta="ground=slab")

    rr = calc_heatloads(
        [room],
        [slab1, slab2],
        t_out_c=-10.0,
        ground_cfg=GroundModelCfg(mode="din_ts", din_ts_f_slab=0.50),
        sync_auto_decks=False,
    )["EG1"]

    assert len(_lines(rr, "Bodenplatte")) == 1
    assert rr["Q_trans_ground_W"] == pytest.approx(72.0)
