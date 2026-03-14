from pathlib import Path
from ..core.config import VentilationCfg
from ..core import calc_heatloads
from ..core import ensure_auto_decks

from PySide6.QtWidgets import QFileDialog, QMessageBox

from ..core.config import CSV_DELIMITER
from ..infrastructure.reporting import (
    FloorplanExportCfg,
    ReportContentCfg,
    ReportPDFCfg,
    ReportPDFLayoutCfg,
    export_floorplans,
    export_heatload_report_pdf,
    write_heatload_details_csv,
    write_heatload_results_csv,
)

class MainWindowExportMixin:
    def _on_export_floorplans_csv(self):
        """Exportiert Grundrisse und CSV-Ergebnisse."""
        outdir = QFileDialog.getExistingDirectory(self, "Exportordner wählen", str(Path.cwd()))
        if not outdir:
            return

        rooms = list(self.rooms.values())
        vent_cfg = getattr(self, "vent_cfg", None) or VentilationCfg()
        cfg = self.project_cfg
        area_mode = cfg.floor_area_mode

        # Automatische Decken ergänzen
        try:
            ensure_auto_decks(
                self.rooms.values(),
                self.elements,
                u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
                u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
                u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
            )
        except Exception:
            pass

        results = calc_heatloads(
            rooms, self.elements, t_out_c=float(cfg.t_out_c),
            vent_cfg=vent_cfg,
            thickness_mode=cfg.thickness_mode,
            area_shrink_factor=float(cfg.area_shrink_factor),
            floor_area_mode=area_mode
        )

        # PDF-Report
        # Report-Konfiguration (Inhalt + Layout) – steuert neue Abschnitte (TB/Lüftung/Interzone/Heatmap)
        report_cfg = ReportPDFCfg(
            content=ReportContentCfg(
                include_thermal_bridge_block=True,
                include_ventilation_parameters_block=True,
                include_interzone_matrix=True,
                include_floorplan_heatmap=True,
            ),
            layout=ReportPDFLayoutCfg(
                # GUI nutzt oft viele Tabellen → kleiner, aber noch lesbar
                font_size_body=9,
                table_body_font_size=6,
            ),
        )

        pdf_path = str(Path(outdir) / "heatload_report.pdf")
        export_heatload_report_pdf(
            pdf_path,
            rooms=list(self.rooms.values()),
            elements=self.elements,
            results=results,
            t_out_c=float(cfg.t_out_c),
            project_cfg=cfg,
            vent_cfg=vent_cfg,
            report_cfg=report_cfg,
        )

        # Ergebnisse CSV
        out_csv = str(Path(outdir) / "heatload_results.csv")
        try:
            write_heatload_results_csv(out_csv, rooms, results, delimiter=CSV_DELIMITER)
        except Exception as e:
            QMessageBox.critical(self, "Export error", f"CSV-Export fehlgeschlagen: {e}")
            return

        # Detail-CSV
        out_detail_csv = str(Path(outdir) / "heatload_details.csv")
        try:
            write_heatload_details_csv(out_detail_csv, rooms, self.elements, results,
                                       t_out_c=self.t_out_c, delimiter=CSV_DELIMITER)
        except Exception as e:
            QMessageBox.critical(self, "Export error", f"Detail-Report fehlgeschlagen:\n{e}")
            return

        # Grundrisse
        try:
            cfg_kwargs = dict(heatmap_enabled=True, draw_elements=True, element_label=True)
            fields = getattr(FloorplanExportCfg, "__dataclass_fields__", {}) or {}
            if "label_outer_walls" in fields:
                cfg_kwargs["label_outer_walls"] = bool(self.show_outerwall_labels)
            if "label_inner_walls" in fields:
                cfg_kwargs["label_inner_walls"] = bool(self.show_innerwall_labels)
            if "label_windows" in fields:
                cfg_kwargs["label_windows"] = bool(self.show_window_labels)

            export_cfg = FloorplanExportCfg(**cfg_kwargs)

            # Export-Metadaten speichern
            try:
                export_cfg_path = Path(outdir) / "export_cfg.json"
                export_meta = {
                    "t_out_c": float(cfg.t_out_c),
                    "thickness_mode": cfg.thickness_mode,
                    "area_shrink_factor": float(cfg.area_shrink_factor),
                    "floor_area_mode": area_mode,
                    "debug_overlay": bool(getattr(self, "show_debug_overlay", False)),
                    "labels": {
                        "outer_walls": bool(self.show_outerwall_labels),
                        "inner_walls": bool(self.show_innerwall_labels),
                        "windows": bool(self.show_window_labels),
                    },
                    "floorplan_cfg": cfg_kwargs,
                }
                export_cfg_path.write_text(json.dumps(export_meta, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

            export_floorplans(rooms, self.elements, results, outdir=str(outdir),
                              base_name="floorplan", cfg=export_cfg, export_pdf=True)
        except Exception as e:
            QMessageBox.critical(self, "Export error", f"Floorplan-Export fehlgeschlagen: {e}")
            return

        QMessageBox.information(self, "Export", f"Fertig.\n\nCSV: {out_csv}\nDetail: {out_detail_csv}\nPDF: {pdf_path}\nPNG/PDF im Ordner: {outdir}")

    # ---------------- Toggles ----------------