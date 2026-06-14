import json
from pathlib import Path
from ..core.config import VentilationCfg
from ..core.ground_model import GroundModelCfg
from ..core.heatload import calc_heatloads
from ..core.heatload import ensure_auto_decks
from ..core.din_status import assess_din_status
from ..core.heatload_types import ThermalBridgeCfg

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QLabel, QMessageBox, QVBoxLayout

from ..core.config import CSV_DELIMITER
from ..infrastructure.reporting import (
    FloorplanExportCfg,
    ReportContentCfg,
    ReportPDFCfg,
    ReportPDFLayoutCfg,
    export_floorplans,
    export_din_12831_report_pdf,
    export_heatload_report_pdf,
    write_heatload_details_csv,
    write_heatload_results_csv,
)

class MainWindowExportMixin:
    def _show_export_options_dialog(self, *, rooms: list, element_count: int, attic_note: str) -> dict | None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Export-Vorschau")
        lay = QVBoxLayout(dlg)
        summary = QLabel(
            f"Räume: {len(rooms)}\n"
            f"Elemente: {element_count}\n"
            f"{attic_note}\n\n"
            "Exportumfang wählen:"
        )
        summary.setWordWrap(True)
        lay.addWidget(summary)
        chk_report = QCheckBox("PDF-Report mit DIN-Prüfstatus")
        chk_din = QCheckBox("DIN-12831-Formbericht")
        chk_csv = QCheckBox("Heatload-CSV und Detail-CSV")
        chk_floorplans = QCheckBox("Grundrisse PNG/PDF mit Heatmap")
        for chk in (chk_report, chk_din, chk_csv, chk_floorplans):
            chk.setChecked(True)
            lay.addWidget(chk)
        if getattr(self, "_dirty", False):
            dirty = QLabel("Hinweis: Das Projekt enthält ungespeicherte Änderungen. Vor dem Export wird ein Backup geschrieben.")
            dirty.setWordWrap(True)
            lay.addWidget(dirty)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay.addWidget(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return None
        return {
            "report": bool(chk_report.isChecked()),
            "din": bool(chk_din.isChecked()),
            "csv": bool(chk_csv.isChecked()),
            "floorplans": bool(chk_floorplans.isChecked()),
        }

    def _confirm_export_din_preflight(self, *, results: dict, rooms: list, cfg, vent_cfg: VentilationCfg) -> bool:
        """Warns before report export when the DIN status still contains red checkpoints."""
        try:
            din_status = assess_din_status(
                results=results,
                project_cfg=cfg,
                vent_cfg=vent_cfg,
                elements=self.elements,
                rooms=rooms,
            )
        except Exception as exc:
            return QMessageBox.question(
                self,
                "DIN-Vorprüfung",
                "Die DIN-Vorprüfung konnte vor dem Export nicht berechnet werden.\n\n"
                f"Details: {exc}\n\n"
                "Export trotzdem starten?",
            ) == QMessageBox.Yes

        self._last_din_status = (din_status.overall_status, din_status.summary)
        if din_status.overall_status != "✗":
            return True

        red_rows = [
            row
            for row in din_status.validation_rows[1:]
            if len(row) >= 3 and str(row[1]).strip() == "✗"
        ]
        red_text = "\n".join(f"- {row[0]}: {row[2]}" for row in red_rows[:6])
        if not red_text:
            red_text = "- Offene rote DIN-Prüfpunkte im Maßnahmenplan."
        msg = (
            "Die DIN-Ampel ist rot. Der Report kann als Arbeitsstand exportiert werden, "
            "ist aber noch nicht als vollständiger Normnachweis geeignet.\n\n"
            f"{red_text}\n\n"
            "Tipp: Projekt > Normprüfung öffnet die fehlenden Nachweise direkt.\n\n"
            "Export trotzdem starten?"
        )
        return QMessageBox.question(self, "DIN-Vorprüfung", msg) == QMessageBox.Yes

    def _on_export_floorplans_csv(self):
        """Exportiert Grundrisse und CSV-Ergebnisse."""
        outdir = QFileDialog.getExistingDirectory(self, "Exportordner wählen", str(Path.cwd()))
        if not outdir:
            return

        rooms = list(self.rooms.values())
        vent_cfg = getattr(self, "vent_cfg", None) or VentilationCfg()
        cfg = self.project_cfg
        area_mode = cfg.floor_area_mode

        with self._busy_cursor("Export wird vorbereitet..."):
            # Automatische Decken ergänzen
            try:
                ensure_auto_decks(
                    self.rooms.values(),
                    self.elements,
                    u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
                    u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
                    u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
                    t_keller_c=float(cfg.t_keller_c),
                    t_oben_c=float(cfg.t_oben_c),
                    u_value_source=str(getattr(cfg, "u_value_source", "")),
                    boundary_source=str(getattr(cfg, "auto_deck_boundary_source", "")),
                    auto_deck_assumptions_confirmed=bool(getattr(cfg, "auto_deck_assumptions_confirmed", False)),
                    create_eg_kellerdecke=bool(getattr(cfg, "auto_deck_create_eg_kellerdecke", True)),
                    create_eg_geschossdecke=bool(getattr(cfg, "auto_deck_create_eg_geschossdecke", True)),
                    create_dg_speicherdecke=bool(getattr(cfg, "auto_deck_create_dg_speicherdecke", True)),
                )
            except Exception:
                pass

            results = calc_heatloads(
                rooms, self.elements, t_out_c=float(cfg.t_out_c),
                vent_cfg=vent_cfg,
                thickness_mode=cfg.thickness_mode,
                area_shrink_factor=float(cfg.area_shrink_factor),
                floor_area_mode=area_mode,
                tb_cfg=ThermalBridgeCfg(**cfg.tb.__dict__),
                ground_cfg=GroundModelCfg(**cfg.ground.__dict__),
                u_aussenwand_w_m2k=float(getattr(cfg, "u_aussenwand_w_m2k", 0.45)),
                u_fenster_w_m2k=float(getattr(cfg, "u_fenster_w_m2k", 2.80)),
                u_tuer_w_m2k=float(getattr(cfg, "u_tuer_w_m2k", 1.80)),
                reheat_power_w_m2=(float(cfg.reheat_power_w_m2) if bool(getattr(cfg, "reheat_enabled", False)) else 0.0),
                reheat_duration_h=(float(cfg.reheat_duration_h) if bool(getattr(cfg, "reheat_enabled", False)) else 0.0),
                reheat_temp_drop_k=(float(cfg.reheat_temp_drop_k) if bool(getattr(cfg, "reheat_enabled", False)) else 0.0),
                reheat_capacity_wh_m2k=float(getattr(cfg, "reheat_capacity_wh_m2k", 20.0)),
                u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
                u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
                u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
                u_value_source=str(getattr(cfg, "u_value_source", "")),
                auto_deck_assumptions_confirmed=bool(getattr(cfg, "auto_deck_assumptions_confirmed", False)),
                auto_deck_boundary_source=str(getattr(cfg, "auto_deck_boundary_source", "")),
                auto_deck_create_eg_kellerdecke=bool(getattr(cfg, "auto_deck_create_eg_kellerdecke", True)),
                auto_deck_create_eg_geschossdecke=bool(getattr(cfg, "auto_deck_create_eg_geschossdecke", True)),
                auto_deck_create_dg_speicherdecke=bool(getattr(cfg, "auto_deck_create_dg_speicherdecke", True)),
                u_bodenplatte_w_m2k=float(getattr(cfg, "u_bodenplatte_w_m2k", 0.40)),
                u_erdberuehrte_wand_w_m2k=float(getattr(cfg, "u_erdberuehrte_wand_w_m2k", 0.60)),
                ventilation_mode=str(getattr(cfg, "ventilation_mode", "natural")),
                min_air_change_1ph=float(getattr(cfg, "min_air_change_1ph", 0.0)),
                infiltration_air_change_1ph=float(getattr(cfg, "infiltration_air_change_1ph", 0.0)),
                mech_supply_m3h=float(getattr(cfg, "mech_supply_m3h", 0.0)),
                mech_exhaust_m3h=float(getattr(cfg, "mech_exhaust_m3h", 0.0)),
                heat_recovery_efficiency=float(getattr(cfg, "heat_recovery_efficiency", 0.0)),
                sync_auto_decks=False,
            )

        if not self._confirm_export_din_preflight(results=results, rooms=rooms, cfg=cfg, vent_cfg=vent_cfg):
            return

        attic = getattr(cfg, "attic", None)
        attic_note = "DG-Dachprofil: aus"
        if attic is not None and bool(getattr(attic, "enabled", False)):
            attic_note = (
                f"DG-Dachprofil: an, Dachfenster {int(getattr(attic, 'roof_window_count', 0) or 0)}, "
                f"Gauben {len(list(getattr(attic, 'dormers', []) or []))}, "
                f"Abgrenzung {str(getattr(attic, 'roof_boundary', 'outside') or 'outside')}"
            )
        export_options = self._show_export_options_dialog(rooms=rooms, element_count=len(self.elements), attic_note=attic_note)
        if not export_options or not any(export_options.values()):
            return

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
                # DIN-Raumblatt: 15-spaltige Bauteiltabelle
                din_room_table_rotate_headers=True,
                din_room_table_header_font_size=8,
                din_room_table_body_font_size=8,
                din_room_table_header_min_height_mm=36.0,
                din_room_table_header_align="CENTER",
                din_room_table_code_align="CENTER",
                din_room_table_numeric_align="CENTER",
                din_room_table_boundary_align="CENTER",
            ),
        )

        pdf_path = str(Path(outdir) / "heatload_report.pdf")
        with self._busy_cursor("Export wird geschrieben..."):
            if hasattr(self, "_write_project_backup"):
                self._write_project_backup("before_export")
            if export_options.get("report", True):
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

            din_pdf_path = str(Path(outdir) / "din_12831_heizlastnachweis.pdf")
            if export_options.get("din", True):
                export_din_12831_report_pdf(
                    din_pdf_path,
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
            if export_options.get("csv", True):
                try:
                    write_heatload_results_csv(out_csv, rooms, results, delimiter=CSV_DELIMITER)
                except Exception as e:
                    QMessageBox.critical(self, "Export error", f"CSV-Export fehlgeschlagen: {e}")
                    return

            # Detail-CSV
            out_detail_csv = str(Path(outdir) / "heatload_details.csv")
            if export_options.get("csv", True):
                try:
                    write_heatload_details_csv(out_detail_csv, rooms, self.elements, results,
                                               t_out_c=self.t_out_c, delimiter=CSV_DELIMITER)
                except Exception as e:
                    QMessageBox.critical(self, "Export error", f"Detail-Report fehlgeschlagen:\n{e}")
                    return

            # Grundrisse
            if export_options.get("floorplans", True):
                try:
                    try:
                        self._export_attic_svg_to(Path(outdir) / "attic_profile.svg")
                    except Exception:
                        pass

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

        created = []
        if export_options.get("csv", True):
            created.extend([out_csv, out_detail_csv])
        if export_options.get("report", True):
            created.append(pdf_path)
        if export_options.get("din", True):
            created.append(din_pdf_path)
        if export_options.get("floorplans", True):
            created.append(f"PNG/PDF im Ordner: {outdir}")
        QMessageBox.information(self, "Export", "Fertig.\n\n" + "\n".join(created))

    # ---------------- Toggles ----------------
