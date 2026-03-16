from pathlib import Path

from heizlast.configs.project_config import AtticCfgDTO, ProjectCfg
from heizlast.core.attic_auto import derive_auto_attic_elements
from heizlast.core.config import VentilationCfg
from heizlast.core.heatload import calc_heatloads, ensure_auto_decks
from heizlast.domain.models import RoomModel
from heizlast.infrastructure.reporting import export_heatload_report_pdf


def _make_attic_project() -> tuple[ProjectCfg, list[RoomModel], list]:
    room = RoomModel(
        id='DG1', floor='DG', name='Dachgeschoss',
        x_m=0.0, y_m=0.0, w_m=8.0, h_m=10.0, height_m=2.5,
    )
    cfg = ProjectCfg()
    cfg.attic = AtticCfgDTO(
        enabled=True,
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        u_roof_w_m2k=0.18,
        u_gable_w_m2k=0.24,
    )
    elements = derive_auto_attic_elements([room], cfg.attic)
    ensure_auto_decks(
        [room],
        elements,
        u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
        u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
        u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
    )
    return cfg, [room], elements


def test_heatload_calculation_includes_auto_attic_elements_and_deck():
    cfg, rooms, elements = _make_attic_project()

    results = calc_heatloads(
        rooms,
        elements,
        t_out_c=float(cfg.t_out_c),
        vent_cfg=VentilationCfg(),
        thickness_mode=cfg.thickness_mode,
        area_shrink_factor=float(cfg.area_shrink_factor),
        floor_area_mode=cfg.floor_area_mode,
    )
    rr = results['DG1']
    type_sums = rr['type_sums']

    assert 'Dach' in type_sums
    assert 'Giebelwand' in type_sums
    assert 'Speicherdecke' in type_sums
    assert rr['Q_sum_W'] > rr['Q_trans_W'] > 0.0
    assert abs(type_sums['Dach']['A_brutto_m2'] - 97.66196710091648) < 1e-6
    assert abs(type_sums['Giebelwand']['A_brutto_m2'] - 38.40664122271071) < 1e-6
    assert abs(type_sums['Speicherdecke']['A_brutto_m2'] - 80.0) < 1e-9


def test_reporting_pdf_builds_with_auto_attic_elements(tmp_path: Path):
    cfg, rooms, elements = _make_attic_project()
    results = calc_heatloads(
        rooms,
        elements,
        t_out_c=float(cfg.t_out_c),
        vent_cfg=VentilationCfg(),
        thickness_mode=cfg.thickness_mode,
        area_shrink_factor=float(cfg.area_shrink_factor),
        floor_area_mode=cfg.floor_area_mode,
    )

    pdf_path = tmp_path / 'heatload_report.pdf'
    export_heatload_report_pdf(
        str(pdf_path),
        rooms=rooms,
        elements=elements,
        results=results,
        t_out_c=float(cfg.t_out_c),
        project_cfg=cfg,
        vent_cfg=VentilationCfg(),
    )

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 5000
