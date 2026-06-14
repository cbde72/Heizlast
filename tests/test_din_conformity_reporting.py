from heizlast.configs.project_config import ProjectCfg
from heizlast.core.config import VentilationCfg
from heizlast.core.din_status import ANNEX_DIN_PROOF_GATE_ROWS, assess_din_status
from heizlast.domain.models import ElementModel, RoomModel


def test_din_project_rows_show_red_ampel_for_missing_norm_modules():
    cfg = ProjectCfg()
    cfg.tb.mode = "none"
    cfg.ground.mode = "simplified"

    status = assess_din_status(
        results={
            "r1": {
                "Q_sum_W": 1200.0,
                "Q_trans_W": 900.0,
                "Q_vent_W": 300.0,
                "A_env_ground_m2": 12.0,
            }
        },
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert status.overall_status == "✗"
    assert "DIN-Ampel: Rot" in status.summary
    assert any(row[0] == "Aufheizzuschlag" and row[-1] == "✗" for row in status.conformity_rows)
    assert any(row[1] == "Mechanische Lüftung / WRG" for row in status.action_rows)
    assert any(row[0] == "Erdreich" and row[1] == "△" for row in status.validation_rows)


def test_din_project_rows_flag_disabled_ground_when_ground_area_exists():
    cfg = ProjectCfg()
    cfg.ground.mode = "none"

    status = assess_din_status(
        results={"r1": {"Q_trans_W": 800.0, "Q_vent_W": 200.0, "A_env_ground_m2": 10.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert any(row[0] == "Erdreich/Boden" and row[-1] == "✗" for row in status.conformity_rows)
    assert any(row[0] == "Erdreich" and row[1] == "✗" for row in status.validation_rows)


def test_din_wording_keeps_conformity_claim_gated():
    assert any("keine offene Rot-Bewertung" in cell for row in ANNEX_DIN_PROOF_GATE_ROWS for cell in row)

    cfg = ProjectCfg()
    status = assess_din_status(
        results={"r1": {"Q_trans_W": 800.0, "Q_vent_W": 200.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert status.overall_status == "✗"
    assert "DIN-orientierter Arbeitsstand" in status.summary
    assert "nicht als vollständiger Normnachweis" in status.summary


def test_din_status_flags_psi_mode_without_values():
    cfg = ProjectCfg()
    cfg.norm_edition = "DIN EN 12831-1:2017-09"
    cfg.t_out_source_detail = "Projektwert"
    cfg.climate_station = "Referenzort"
    cfg.tb.mode = "psi"
    cfg.tb.psi_default_w_mk = 0.0
    cfg.tb.use_element_meta_psi = True

    status = assess_din_status(
        results={"r1": {"Q_trans_W": 800.0, "Q_vent_W": 200.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
        elements=[],
    )

    assert any(row[0] == "Wärmebrücken" and row[-1] == "✗" for row in status.conformity_rows)


def test_din_status_accepts_simplified_reheat_module_as_yellow():
    cfg = ProjectCfg()
    cfg.norm_edition = "DIN EN 12831-1:2017-09"
    cfg.t_out_source_detail = "Projektwert"
    cfg.climate_station = "Referenzort"
    cfg.reheat_enabled = True
    cfg.reheat_power_w_m2 = 10.0
    cfg.reheat_source = "Projektannahme"

    status = assess_din_status(
        results={"r1": {"Q_trans_W": 800.0, "Q_vent_W": 200.0, "Q_reheat_W": 120.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert any(row[0] == "Aufheizzuschlag" and row[-1] == "△" for row in status.conformity_rows)


def test_din_status_describes_mechanical_ventilation_as_active_module():
    cfg = ProjectCfg()
    cfg.norm_edition = "DIN EN 12831-1:2017-09"
    cfg.t_out_source_detail = "Projektwert"
    cfg.climate_station = "Referenzort"
    cfg.ventilation_mode = "mechanical"
    cfg.mech_supply_m3h = 100.0
    cfg.mech_exhaust_m3h = 100.0
    cfg.heat_recovery_efficiency = 0.75
    cfg.ventilation_source = "Anlagenplanung"

    status = assess_din_status(
        results={"r1": {"Q_trans_W": 800.0, "Q_vent_W": 200.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert any(
        row[0] == "Mechanische Lüftung" and "Restwärmeverlust aktiv" in row[2] and row[-1] == "△"
        for row in status.conformity_rows
    )


def test_din_status_flags_missing_u_value_source():
    cfg = ProjectCfg()
    cfg.norm_edition = "DIN EN 12831-1:2017-09"
    cfg.t_out_source_detail = "Projektwert"
    cfg.climate_station = "Referenzort"
    cfg.u_value_source = ""

    status = assess_din_status(
        results={"r1": {"Q_trans_W": 800.0, "Q_vent_W": 200.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert any(row[0] == "U-Werte / Bauteilnachweis" and row[-1] == "✗" for row in status.conformity_rows)


def test_din_status_accepts_documented_u_value_source_as_yellow():
    cfg = ProjectCfg()
    cfg.norm_edition = "DIN EN 12831-1:2017-09"
    cfg.t_out_source_detail = "Projektwert"
    cfg.climate_station = "Referenzort"
    cfg.u_value_source = "Bauteilkatalog"

    status = assess_din_status(
        results={"r1": {"Q_trans_W": 800.0, "Q_vent_W": 200.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert any(row[0] == "U-Werte / Bauteilnachweis" and row[-1] == "△" for row in status.conformity_rows)


def test_din_status_flags_invalid_room_data_for_norm_traceability():
    cfg = ProjectCfg()
    room = RoomModel(id="R1", floor="EG", name="Bad", x_m=0.0, y_m=0.0, w_m=2.0, h_m=2.0, height_m=0.0)

    status = assess_din_status(
        results={"R1": {"Q_trans_W": 100.0, "Q_vent_W": 20.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
        rooms=[room],
        elements=[],
    )

    assert any(row[0] == "Raumdaten" and row[-1] == "✗" for row in status.conformity_rows)
    assert any(row[1] == "Raumdaten" and row[2] == "✗" for row in status.action_rows)


def test_din_status_flags_invalid_transmission_element_data():
    cfg = ProjectCfg()
    room = RoomModel(id="R1", floor="EG", name="Wohnen", x_m=0.0, y_m=0.0, w_m=4.0, h_m=4.0, usage_type="Wohnen")
    wall = ElementModel(room_id="R1", element_type="Außenwand", area_m2=0.0, u_w_m2k=0.45, uid="wall_bad")

    status = assess_din_status(
        results={"R1": {"Q_trans_W": 100.0, "Q_vent_W": 20.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
        rooms=[room],
        elements=[wall],
    )

    assert any(row[0] == "Bauteildaten" and row[-1] == "✗" for row in status.conformity_rows)
    assert any(row[1] == "Bauteildaten" and row[2] == "✗" for row in status.action_rows)


def test_din_status_accepts_traceable_transmission_detail_rows():
    cfg = ProjectCfg()
    room = RoomModel(id="R1", floor="EG", name="Wohnen", x_m=0.0, y_m=0.0, w_m=4.0, h_m=4.0, usage_type="Wohnen")
    wall = ElementModel(
        room_id="R1",
        element_type="Außenwand",
        area_m2=10.0,
        u_w_m2k=0.45,
        length_m=4.0,
        height_m=2.5,
        uid="wall_ok",
    )

    status = assess_din_status(
        results={
            "R1": {
                "Q_trans_W": 100.0,
                "Q_vent_W": 20.0,
                "transmission_details": [
                    {
                        "element_uid": "wall_ok",
                        "boundary_bucket": "outside",
                        "boundary_label": "Außenluft",
                        "surface_role": "wall_outside",
                    }
                ],
            }
        },
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
        rooms=[room],
        elements=[wall],
    )

    assert any(row[0] == "Raumdaten" and row[-1] == "✓" for row in status.conformity_rows)
    assert any(row[0] == "Bauteildaten" and row[-1] == "✓" for row in status.conformity_rows)
    assert any(row[0] == "Transmissionsdetails" and row[-1] == "✓" for row in status.conformity_rows)


def test_din_status_requires_element_level_sources_for_green_u_gate():
    cfg = ProjectCfg()
    cfg.u_value_source = "Projekt-U-Wert-Tabelle"
    room = RoomModel(id="R1", floor="EG", name="Wohnen", x_m=0.0, y_m=0.0, w_m=4.0, h_m=4.0, usage_type="Wohnen")
    wall = ElementModel(
        room_id="R1",
        element_type="Außenwand",
        area_m2=10.0,
        u_w_m2k=0.45,
        length_m=4.0,
        height_m=2.5,
        uid="wall_src",
        meta="u_source=Bauteilkatalog|area_source=Planaufmaß|boundary=external",
    )

    status = assess_din_status(
        results={"R1": {"Q_trans_W": 100.0, "Q_vent_W": 20.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
        rooms=[room],
        elements=[wall],
    )

    assert any(row[0] == "U-Werte / Bauteilnachweis" and row[-1] == "✓" for row in status.conformity_rows)


def test_din_status_flags_din_ts_ground_without_intermediate_values():
    cfg = ProjectCfg()
    cfg.ground.mode = "din_ts"
    cfg.ground.din_ts_source = "DIN/TS Tabelle"
    cfg.ground_norm_inputs = ""

    status = assess_din_status(
        results={"R1": {"Q_trans_W": 100.0, "Q_vent_W": 20.0, "A_env_ground_m2": 5.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert any(row[0] == "Erdreich/Boden" and row[-1] == "△" and "Zwischenwerte" in row[2] for row in status.conformity_rows)


def test_din_status_accepts_reheat_only_with_norm_basis():
    cfg = ProjectCfg()
    cfg.reheat_enabled = True
    cfg.reheat_power_w_m2 = 12.0
    cfg.reheat_source = "DIN/TS Projekttabelle"
    cfg.reheat_norm_basis = "Nutzung Wohnen, mittelschwere Bauart, Wiederaufheizzeit 2 h"

    status = assess_din_status(
        results={"R1": {"Q_trans_W": 100.0, "Q_vent_W": 20.0, "Q_reheat_W": 80.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert any(row[0] == "Aufheizzuschlag" and row[-1] == "✓" for row in status.conformity_rows)


def test_din_status_marks_proof_export_as_blocked_until_all_gates_green():
    cfg = ProjectCfg()
    cfg.proof_export_enabled = True

    status = assess_din_status(
        results={"R1": {"Q_trans_W": 100.0, "Q_vent_W": 20.0}},
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert "Prüffassung: gesperrt" in status.summary
    assert any(row[1] == "Änderungsprotokoll" for row in status.action_rows)
