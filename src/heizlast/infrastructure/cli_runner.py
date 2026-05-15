from __future__ import annotations

import argparse
from pathlib import Path

from ..core.config import CSV_DELIMITER, VentilationCfg
from ..core.csv_io import load_rooms, load_elements
from ..configs.project_config import ProjectCfg, load_project_cfg
from ..core.heatload import calc_heatloads, ensure_auto_decks
from .reporting import (
    export_floorplans,
    export_heatload_report_pdf,
    write_heatload_results_csv,
    write_heatload_details_csv,
    FloorplanExportCfg,
)


def _derive_elements_path(rooms_path: Path) -> Path:
    name = rooms_path.name
    stem = rooms_path.stem
    if name.lower() == "rooms.csv":
        return rooms_path.with_name("elements.csv")
    if stem.lower().endswith("_rooms"):
        return rooms_path.with_name(stem[:-6] + "_elements.csv")
    return rooms_path.with_name(stem + "_elements.csv")


def _project_cfg_path(rooms_path: Path) -> Path:
    # Must match GUI logic: <rooms_stem>.project.json next to rooms csv
    return rooms_path.with_name(f"{rooms_path.stem}.project.json")


def run_export(
    rooms_csv: Path,
    outdir: Path,
    *,
    elements_csv: Path | None = None,
    t_out_c: float | None = None,
    thickness_mode: str | None = None,
    area_shrink_factor: float | None = None,
    floor_area_mode: str | None = None,
    label_outer_walls: bool | None = None,
    label_inner_walls: bool | None = None,
    label_windows: bool | None = None,
    no_pdf: bool = False,
    no_floorplans: bool = False,
    no_csv: bool = False,
    no_detail_csv: bool = False,
) -> None:
    rooms_csv = Path(rooms_csv)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    elements_csv = Path(elements_csv) if elements_csv else _derive_elements_path(rooms_csv)
    rooms = load_rooms(str(rooms_csv), delimiter=CSV_DELIMITER)
    elements = load_elements(str(elements_csv), delimiter=CSV_DELIMITER) if elements_csv.exists() else []

    # Project cfg (optional)
    cfg = ProjectCfg()
    cfg_path = _project_cfg_path(rooms_csv)
    if cfg_path.exists():
        try:
            cfg = load_project_cfg(cfg_path)
        except Exception:
            cfg = ProjectCfg()

    # Override cfg from CLI if provided
    if t_out_c is not None:
        cfg.t_out_c = float(t_out_c)
    if thickness_mode is not None:
        cfg.thickness_mode = str(thickness_mode)
    if area_shrink_factor is not None:
        cfg.area_shrink_factor = float(area_shrink_factor)
    if floor_area_mode is not None:
        cfg.floor_area_mode = str(floor_area_mode)

    # Ensure decks (idempotent)
    try:
        ensure_auto_decks(
            rooms,
            elements,
            u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
            u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
            u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
        )
    except Exception:
        pass

    results = calc_heatloads(
        rooms,
        elements,
        t_out_c=float(cfg.t_out_c),
        vent_cfg=VentilationCfg(),
        thickness_mode=cfg.thickness_mode,
        area_shrink_factor=float(cfg.area_shrink_factor),
        floor_area_mode=cfg.floor_area_mode,
    )

    if not no_pdf:
        export_heatload_report_pdf(
            str(outdir / "heatload_report.pdf"),
            rooms=rooms,
            elements=elements,
            results=results,
            t_out_c=float(cfg.t_out_c),
        )

    if not no_csv:
        write_heatload_results_csv(str(outdir / "heatload_results.csv"), rooms, results, delimiter=CSV_DELIMITER)

    if not no_detail_csv:
        write_heatload_details_csv(
            str(outdir / "heatload_details.csv"),
            rooms,
            elements,
            results,
            t_out_c=float(cfg.t_out_c),
            delimiter=CSV_DELIMITER,
        )

    if not no_floorplans:
        cfg_kwargs = dict(heatmap_enabled=True, draw_elements=True, element_label=True)
        fields = getattr(FloorplanExportCfg, "__dataclass_fields__", {}) or {}
        if "label_outer_walls" in fields and label_outer_walls is not None:
            cfg_kwargs["label_outer_walls"] = bool(label_outer_walls)
        if "label_inner_walls" in fields and label_inner_walls is not None:
            cfg_kwargs["label_inner_walls"] = bool(label_inner_walls)
        if "label_windows" in fields and label_windows is not None:
            cfg_kwargs["label_windows"] = bool(label_windows)

        export_cfg = FloorplanExportCfg(**cfg_kwargs)
        export_floorplans(str(outdir), rooms=rooms, elements=elements, export_cfg=export_cfg)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="heizlast-export", description="Heizlast Export CLI Runner")
    ap.add_argument("--rooms", required=True, type=Path, help="Path to rooms.csv")
    ap.add_argument("--outdir", required=True, type=Path, help="Output directory")
    ap.add_argument("--elements", default=None, type=Path, help="Path to elements.csv (optional)")

    ap.add_argument("--t_out", default=None, type=float, help="Outside temperature in °C (override)")
    ap.add_argument("--thickness_mode", default=None, type=str, help="Thickness mode override")
    ap.add_argument("--area_shrink_factor", default=None, type=float, help="Area shrink factor override")
    ap.add_argument("--floor_area_mode", default=None, type=str, help="floor area reference: inner|outer override")

    ap.add_argument("--label_outer_walls", action="store_true", help="Label outer walls on floorplans")
    ap.add_argument("--label_inner_walls", action="store_true", help="Label inner walls on floorplans")
    ap.add_argument("--label_windows", action="store_true", help="Label windows on floorplans")

    ap.add_argument("--no_pdf", action="store_true")
    ap.add_argument("--no_floorplans", action="store_true")
    ap.add_argument("--no_csv", action="store_true")
    ap.add_argument("--no_detail_csv", action="store_true")

    args = ap.parse_args(argv)

    run_export(
        args.rooms,
        args.outdir,
        elements_csv=args.elements,
        t_out_c=args.t_out,
        thickness_mode=args.thickness_mode,
        area_shrink_factor=args.area_shrink_factor,
        floor_area_mode=args.floor_area_mode,
        label_outer_walls=args.label_outer_walls,
        label_inner_walls=args.label_inner_walls,
        label_windows=args.label_windows,
        no_pdf=args.no_pdf,
        no_floorplans=args.no_floorplans,
        no_csv=args.no_csv,
        no_detail_csv=args.no_detail_csv,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())