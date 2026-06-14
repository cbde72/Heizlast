import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
from collections import defaultdict

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QListWidgetItem, QTableWidgetItem

from ..configs.project_config import ProjectCfg
from ..core.anchors import parse_meta
from ..core.config import VentilationCfg
from ..core.din_status import assess_din_status
from ..domain.models import ElementModel, RoomModel


class MainWindowComfortMixin:
    def _setup_comfort_features(self) -> None:
        self._dirty = False
        self._comfort_ready = False
        self._undo_snapshots: list[dict] = []
        self._redo_snapshots: list[dict] = []
        self._last_snapshot = self._comfort_snapshot()
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(120_000)
        self._autosave_timer.timeout.connect(self._autosave_if_dirty)
        self._autosave_timer.start()
        self._refresh_comfort_ui()

    def _comfort_snapshot(self) -> dict:
        return {
            "rooms": [asdict(r) for r in self.rooms.values()],
            "elements": [asdict(e) for e in self.elements],
            "project_cfg": self.project_cfg.to_json_dict(),
            "selected_room_id": getattr(self, "_selected_room_id", None),
        }

    def _restore_comfort_snapshot(self, snapshot: dict) -> None:
        self.rooms = {str(item["id"]): RoomModel(**item) for item in snapshot.get("rooms", [])}
        self.elements = [ElementModel(**item) for item in snapshot.get("elements", [])]
        self.project_cfg = ProjectCfg.from_json_dict(snapshot.get("project_cfg", {}))
        self.t_out_c = float(self.project_cfg.t_out_c)
        try:
            self.metrics.bind(self.rooms, self.elements)
        except Exception:
            pass
        self._selected_room_id = snapshot.get("selected_room_id")
        self._rebuild_all_graphics()
        self._populate_room_form()
        self._populate_room_elements_list()
        self._recompute_and_redraw()
        self._refresh_attic_preview()

    def _mark_dirty(self, reason: str = "", *, refresh_ui: bool = True) -> None:
        if not getattr(self, "_comfort_ready", False):
            return
        current = self._comfort_snapshot()
        if current != getattr(self, "_last_snapshot", None):
            self._undo_snapshots.append(self._last_snapshot)
            self._undo_snapshots = self._undo_snapshots[-40:]
            self._redo_snapshots.clear()
            self._last_snapshot = current
        self._dirty = True
        if refresh_ui:
            self._refresh_comfort_ui()

    def _mark_clean(self) -> None:
        self._dirty = False
        self._last_snapshot = self._comfort_snapshot()
        self._comfort_ready = True
        self._refresh_comfort_ui()

    def _comfort_undo(self) -> None:
        if not self._undo_snapshots:
            return
        self._redo_snapshots.append(self._comfort_snapshot())
        snap = self._undo_snapshots.pop()
        self._comfort_ready = False
        self._restore_comfort_snapshot(snap)
        self._comfort_ready = True
        self._dirty = True
        self._last_snapshot = self._comfort_snapshot()
        self._refresh_comfort_ui()

    def _comfort_redo(self) -> None:
        if not self._redo_snapshots:
            return
        self._undo_snapshots.append(self._comfort_snapshot())
        snap = self._redo_snapshots.pop()
        self._comfort_ready = False
        self._restore_comfort_snapshot(snap)
        self._comfort_ready = True
        self._dirty = True
        self._last_snapshot = self._comfort_snapshot()
        self._refresh_comfort_ui()

    def _refresh_comfort_ui(self) -> None:
        title = getattr(self, "windowTitle", lambda: "Heizlast Tool")()
        base = title.rstrip(" *")
        try:
            self.setWindowTitle(base + (" *" if getattr(self, "_dirty", False) else ""))
        except Exception:
            pass
        for attr, enabled in (("act_comfort_undo", bool(getattr(self, "_undo_snapshots", []))), ("act_comfort_redo", bool(getattr(self, "_redo_snapshots", [])))):
            act = getattr(self, attr, None)
            if act is not None:
                act.setEnabled(enabled)
        self._refresh_plausibility_panel()
        try:
            self._update_statusbar_summary()
        except Exception:
            pass

    def _refresh_project_dashboard(self) -> None:
        if not hasattr(self, "list_dashboard_checks"):
            return
        dock = getattr(self, "dock_dashboard", None)
        if dock is not None and not dock.isVisible():
            return
        project_path = str(getattr(self, "_project_rooms_path", None) or "—")
        dirty = "ungespeichert" if getattr(self, "_dirty", False) else "gespeichert"
        rooms = list(getattr(self, "rooms", {}).values())
        elements = list(getattr(self, "elements", []) or [])
        floors = sorted({str(getattr(r, "floor", "") or "?") for r in rooms})
        self.lbl_dashboard_project.setText(f"Projekt: {project_path}")
        self.lbl_dashboard_counts.setText(
            f"Räume: {len(rooms)} · Bauteile: {len(elements)} · Geschosse: {', '.join(floors) if floors else '—'}"
        )
        self.lbl_dashboard_saved.setText(f"Status: {dirty}")
        din_status = getattr(self, "_last_din_status", None)
        if isinstance(din_status, tuple) and len(din_status) >= 2:
            label = {"✓": "Grün", "△": "Gelb", "✗": "Rot"}.get(str(din_status[0]), "—")
            self.lbl_dashboard_din.setText(f"DIN: {label} · {din_status[1]}")
        else:
            self.lbl_dashboard_din.setText("DIN: noch nicht berechnet")

        self.list_dashboard_checks.clear()
        try:
            status = assess_din_status(
                results=getattr(self, "_last_heatload_results", None) or {},
                project_cfg=getattr(self, "project_cfg", None),
                vent_cfg=getattr(self, "vent_cfg", None) or VentilationCfg(),
                elements=elements,
                rooms=rooms,
            )
            self._refresh_dashboard_workflow(status, rooms, elements)
            self._refresh_room_norm_matrix(rooms, elements)
            self._refresh_heatload_audit(getattr(self, "_last_heatload_results", None) or {}, rooms, elements)
            rows = [
                row for row in status.validation_rows[1:]
                if len(row) >= 3 and str(row[1]).strip() in {"✗", "△"}
            ]
            for row in rows[:12]:
                self.list_dashboard_checks.addItem(f"{row[1]} {row[0]}: {row[2]}")
            if not rows:
                self.list_dashboard_checks.addItem("✓ Keine offenen Dashboard-Prüfpunkte.")
        except Exception as exc:
            self.list_dashboard_checks.addItem(f"✗ Dashboard-Prüfung nicht berechenbar: {exc}")
            self._refresh_dashboard_workflow(None, rooms, elements)
            self._refresh_room_norm_matrix(rooms, elements)
            self._refresh_heatload_audit(getattr(self, "_last_heatload_results", None) or {}, rooms, elements)

    def _validation_status_map(self, status) -> dict[str, str]:
        if status is None:
            return {}
        return {
            str(row[0]): str(row[1]).strip()
            for row in getattr(status, "validation_rows", [])[1:]
            if len(row) >= 2
        }

    def _add_dashboard_workflow_item(self, text: str, status: str, target: str) -> None:
        item = QListWidgetItem(f"{status} {text}")
        item.setData(Qt.UserRole, target)
        self.list_dashboard_workflow.addItem(item)

    def _refresh_dashboard_workflow(self, status, rooms: list[RoomModel], elements: list[ElementModel]) -> None:
        lst = getattr(self, "list_dashboard_workflow", None)
        if lst is None:
            return
        lst.clear()
        status_by_name = self._validation_status_map(status)
        parameter_states = [
            status_by_name.get("Norm-/Quellenbezug", "✗"),
            status_by_name.get("U-Wert-Quellen", "✗"),
            status_by_name.get("DIN/TS-Faktoren unbeheizt", "△"),
        ]
        room_state = status_by_name.get("Raumdaten", "✗")
        element_states = [
            status_by_name.get("Bauteildaten", "✗"),
            status_by_name.get("Transmissions-Buckets", "✗"),
            status_by_name.get("Decken / Nachbarzonen", "△"),
        ]
        report_states = [
            getattr(status, "overall_status", "✗") if status is not None else "✗",
            "✓" if rooms and elements else "✗",
        ]
        self._add_dashboard_workflow_item(
            "Projektparameter vollständig",
            self._worst_dashboard_status(parameter_states),
            "project_norm",
        )
        self._add_dashboard_workflow_item(
            "Räume geprüft",
            room_state,
            "room_matrix",
        )
        self._add_dashboard_workflow_item(
            "Bauteile plausibel",
            self._worst_dashboard_status(element_states),
            "u_values",
        )
        self._add_dashboard_workflow_item(
            "DIN-Report bereit",
            self._worst_dashboard_status(report_states),
            "export",
        )

    def _worst_dashboard_status(self, states: list[str]) -> str:
        rank = {"✓": 0, "△": 1, "✗": 2}
        worst = max((rank.get(str(s).strip(), 2) for s in states), default=2)
        return "✓" if worst == 0 else "△" if worst == 1 else "✗"

    def _on_dashboard_workflow_item_clicked(self, item: QListWidgetItem) -> None:
        target = str(item.data(Qt.UserRole) or "")
        if target == "project_norm" and hasattr(self, "_on_project_settings_norm"):
            self._on_project_settings_norm()
        elif target == "u_values" and hasattr(self, "_on_project_settings_u_values"):
            self._on_project_settings_u_values()
        elif target == "export" and hasattr(self, "_on_export_floorplans_csv"):
            self._on_export_floorplans_csv()
        elif target == "room_matrix":
            table = getattr(self, "tbl_room_norm_matrix", None)
            if table is not None and table.rowCount() > 0:
                table.setFocus()
                table.selectRow(0)

    def _room_elements_for_matrix(self, room_id: str, elements: list[ElementModel]) -> list[ElementModel]:
        return [e for e in elements if str(getattr(e, "room_id", "") or "") == str(room_id)]

    def _element_kind_text(self, element: ElementModel) -> str:
        return str(getattr(element, "element_type", "") or "").strip().lower()

    def _has_kind(self, elements: list[ElementModel], needles: tuple[str, ...]) -> bool:
        return any(any(needle in self._element_kind_text(e) for needle in needles) for e in elements)

    def _has_valid_kind(self, elements: list[ElementModel], needles: tuple[str, ...]) -> bool:
        return self._valid_kind_source_status(elements, needles)[0]

    def _valid_kind_source_status(self, elements: list[ElementModel], needles: tuple[str, ...]) -> tuple[bool, bool]:
        has_valid = False
        has_documented_source = False
        for element in elements:
            if not any(needle in self._element_kind_text(element) for needle in needles):
                continue
            area = float(getattr(element, "area_m2", 0.0) or 0.0)
            u_value = float(getattr(element, "u_w_m2k", 0.0) or 0.0)
            if area > 0.0 and u_value > 0.0:
                has_valid = True
                meta = parse_meta(getattr(element, "meta", "") or "")
                source_status = str(meta.get("source_status", "") or "").strip().lower()
                source_note = str(meta.get("source_note", "") or "").strip()
                if source_status and source_status != "geschätzt" and (source_note or source_status in {"projektwert", "din/normtabelle"}):
                    has_documented_source = True
        return has_valid, has_documented_source

    def _room_matrix_status(self, room: RoomModel, elements: list[ElementModel], key: str) -> tuple[str, str]:
        if key == "outside_wall":
            return self._status_for_element_group(elements, ("außenwand", "aussenwand", "fassade"))
        if key == "window":
            return self._status_for_element_group(elements, ("fenster",))
        if key == "roof":
            if str(getattr(room, "floor", "") or "").upper() != "DG":
                return "—", "für Geschoss nicht relevant"
            return self._status_for_element_group(elements, ("dach", "gaube"))
        if key == "deck":
            return self._status_for_element_group(elements, ("decke", "geschossdecke", "speicherdecke", "kellerdecke"))
        if key == "ground":
            if str(getattr(room, "floor", "") or "").upper() not in {"KG", "EG"}:
                return "—", "für Geschoss nicht relevant"
            return self._status_for_element_group(elements, ("boden", "bodenplatte", "erdreich"))
        if key == "thermal_bridge":
            tb = getattr(getattr(self, "project_cfg", None), "tb", None)
            mode = str(getattr(tb, "mode", "none") or "none")
            source = str(getattr(getattr(self, "project_cfg", None), "thermal_bridge_source", "") or "").strip()
            if mode == "none":
                return "△", "Wärmebrückenansatz nicht aktiv"
            return ("✓", "Wärmebrückenansatz mit Quelle") if source else ("△", "Wärmebrückenansatz ohne Quelle")
        if key == "ventilation":
            n_val = float(getattr(room, "air_change_1ph", 0.0) or 0.0)
            volume = float(getattr(room, "volume_m3", 0.0) or 0.0)
            if n_val < 0.0 or volume <= 0.0:
                return "✗", "Luftwechsel oder Volumen fehlt"
            return ("✓", "Lüftung raumweise angesetzt") if n_val > 0.0 else ("△", "Luftwechsel ist 0")
        if key == "temperature":
            temp = float(getattr(room, "t_inside_c", 0.0) or 0.0)
            usage = str(getattr(room, "usage_type", "") or "").strip()
            if not (5.0 <= temp <= 35.0):
                return "✗", "Solltemperatur prüfen"
            return ("✓", "Temperatur und Nutzung gesetzt") if usage else ("△", "Nutzung fehlt")
        if key == "neighbor":
            has_neighbor = any(
                float(getattr(e, "factor", 1.0) or 1.0) < 0.999
                or "boundary=" in str(getattr(e, "meta", "") or "")
                or "adj_floor=" in str(getattr(e, "meta", "") or "")
                or any(token in self._element_kind_text(e) for token in ("decke", "boden", "erdreich"))
                for e in elements
            )
            return ("✓", "Nachbarzone/Randbedingung erkennbar") if has_neighbor else ("△", "Nachbarzone nicht explizit erkennbar")
        return "△", "nicht bewertet"

    def _status_for_element_group(self, elements: list[ElementModel], needles: tuple[str, ...]) -> tuple[str, str]:
        has_valid, has_source = self._valid_kind_source_status(elements, needles)
        if has_valid and has_source:
            return "✓", "Fläche, U-Wert und Quelle vorhanden"
        if has_valid:
            return "△", "Fläche und U-Wert vorhanden, Quelle/Annahme fehlt"
        if self._has_kind(elements, needles):
            return "✗", "Element vorhanden, Fläche oder U-Wert fehlt"
        return "△", "nicht angelegt oder nicht relevant"

    def _refresh_room_norm_matrix(self, rooms: list[RoomModel], elements: list[ElementModel]) -> None:
        table = getattr(self, "tbl_room_norm_matrix", None)
        if table is None:
            return
        columns = [
            ("outside_wall", "AW"),
            ("window", "Fen."),
            ("roof", "Dach"),
            ("deck", "Decke"),
            ("ground", "Boden"),
            ("thermal_bridge", "WB"),
            ("ventilation", "Luft"),
            ("temperature", "Temp."),
            ("neighbor", "Nachbar"),
        ]
        by_room: dict[str, list[ElementModel]] = defaultdict(list)
        for e in elements:
            by_room[str(getattr(e, "room_id", "") or "")].append(e)
        table.setUpdatesEnabled(False)
        table.setRowCount(len(rooms))
        try:
            for row_index, room in enumerate(sorted(rooms, key=lambda r: (str(r.floor), str(r.name), str(r.id)))):
                room_id = str(room.id)
                room_elements = by_room.get(room_id, [])
                room_item = QTableWidgetItem(f"{room.name or room.id}")
                room_item.setData(Qt.UserRole, room_id)
                room_item.setToolTip(room_id)
                table.setItem(row_index, 0, room_item)
                for col_index, (key, _label) in enumerate(columns, start=1):
                    mark, tip = self._room_matrix_status(room, room_elements, key)
                    item = QTableWidgetItem(mark)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setData(Qt.UserRole, room_id)
                    item.setToolTip(tip)
                    table.setItem(row_index, col_index, item)
            table.resizeColumnsToContents()
        finally:
            table.setUpdatesEnabled(True)

    def _on_room_norm_matrix_cell_clicked(self, row: int, _column: int) -> None:
        table = getattr(self, "tbl_room_norm_matrix", None)
        if table is None:
            return
        item = table.item(row, 0)
        rid = str(item.data(Qt.UserRole) or "") if item is not None else ""
        if rid and rid in getattr(self, "rooms", {}):
            self._selected_room_id = rid
            if hasattr(self, "_populate_room_form"):
                self._populate_room_form()
            dock = getattr(self, "dock_properties", None)
            if dock is not None:
                dock.show()
                dock.raise_()

    def _room_result_items(self, results: dict) -> list[tuple[str, dict]]:
        return [
            (str(room_id), rr)
            for room_id, rr in (results or {}).items()
            if isinstance(rr, dict) and "Q_sum_W" in rr
        ]

    def _add_heat_audit_item(self, text: str, room_id: str | None = None) -> None:
        item = QListWidgetItem(text)
        if room_id:
            item.setData(Qt.UserRole, room_id)
        self.list_dashboard_heat_audit.addItem(item)

    def _fmt_kw(self, watts: float) -> str:
        return f"{float(watts) / 1000.0:.1f} kW"

    def _refresh_heatload_audit(self, results: dict, rooms: list[RoomModel], elements: list[ElementModel]) -> None:
        lst = getattr(self, "list_dashboard_heat_audit", None)
        if lst is None:
            return
        lst.clear()
        room_results = self._room_result_items(results)
        if not room_results:
            self._add_heat_audit_item("△ Noch keine Heizlastberechnung für Audit vorhanden.")
            return

        total_q = sum(float(rr.get("Q_sum_W", 0.0) or 0.0) for _rid, rr in room_results)
        total_trans = sum(float(rr.get("Q_trans_W", 0.0) or 0.0) for _rid, rr in room_results)
        total_vent = sum(float(rr.get("Q_vent_W", 0.0) or 0.0) for _rid, rr in room_results)
        total_tb = sum(float(rr.get("Q_tb_W", 0.0) or 0.0) for _rid, rr in room_results)
        self._add_heat_audit_item(
            f"Σ {self._fmt_kw(total_q)} · Transmission {self._fmt_kw(total_trans)} · Lüftung {self._fmt_kw(total_vent)} · WB {self._fmt_kw(total_tb)}"
        )

        for rid, rr in sorted(room_results, key=lambda kv: float(kv[1].get("Q_sum_W", 0.0) or 0.0), reverse=True)[:5]:
            area = float(rr.get("A_ref_m2", 0.0) or 0.0)
            wpm2 = float(rr.get("Q_W_per_m2", 0.0) or 0.0)
            marker = "✗" if wpm2 >= 100.0 else "△" if wpm2 >= 70.0 else "•"
            name = str(rr.get("name") or rid)
            self._add_heat_audit_item(
                f"{marker} Raum {name}: {self._fmt_kw(float(rr.get('Q_sum_W', 0.0) or 0.0))}, {wpm2:.0f} W/m², A {area:.1f} m²",
                rid,
            )

        by_type: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        roof_by_room: dict[str, float] = defaultdict(float)
        gable_by_room: dict[str, float] = defaultdict(float)
        roof_signature_counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
        element_by_uid = {
            str(getattr(e, "uid", "") or ""): e
            for e in elements
            if str(getattr(e, "uid", "") or "")
        }
        for rid, rr in room_results:
            for line in rr.get("lines", []) or []:
                if line.get("line_type") != "TRANSMISSION":
                    continue
                et = str(line.get("element_type") or "Bauteil")
                q_w = float(line.get("Q_W", 0.0) or 0.0)
                area = float(line.get("A_eff_m2", line.get("A_m2", 0.0)) or 0.0)
                by_type[et][0] += q_w
                by_type[et][1] += area
                et_l = et.lower()
                if "dach" in et_l and "decke" not in et_l:
                    roof_by_room[rid] += area
                if "giebel" in et_l:
                    gable_by_room[rid] += area
                uid = str(line.get("uid") or "")
                source_uid = ""
                meta = ""
                match = element_by_uid.get(uid)
                if match is not None:
                    meta = str(getattr(match, "meta", "") or "")
                    source_uid = str(parse_meta(meta).get("source_uid", "") or "")
                roof_signature_counts[(rid, et, source_uid or uid, f"{area:.3f}")] += 1

        for et, (q_w, area) in sorted(by_type.items(), key=lambda kv: kv[1][0], reverse=True)[:5]:
            self._add_heat_audit_item(f"• {et}: {self._fmt_kw(q_w)} bei {area:.1f} m²")

        room_by_id = {str(getattr(room, "id", "") or ""): room for room in rooms}
        for rid, roof_area in sorted(roof_by_room.items(), key=lambda kv: kv[1], reverse=True)[:6]:
            room = room_by_id.get(rid)
            room_area = float(room.area_m2()) if room is not None else float(next((rr.get("A_ref_m2", 0.0) for rrid, rr in room_results if rrid == rid), 0.0) or 0.0)
            ratio = roof_area / room_area if room_area > 0.0 else 0.0
            if ratio >= 2.0 or roof_area >= 60.0:
                self._add_heat_audit_item(f"✗ DG-Dachfläche {rid}: {roof_area:.1f} m² Dach bei {room_area:.1f} m² Raum prüfen", rid)
            elif ratio >= 1.4:
                self._add_heat_audit_item(f"△ DG-Dachfläche {rid}: Verhältnis {ratio:.1f} prüfen", rid)

        for rid, gable_area in sorted(gable_by_room.items(), key=lambda kv: kv[1], reverse=True)[:4]:
            room = room_by_id.get(rid)
            wall_ref = float(getattr(room, "perimeter_m", lambda: 0.0)() * getattr(room, "height_m", 0.0)) if room is not None else 0.0
            if wall_ref > 0.0 and gable_area > wall_ref * 0.8:
                self._add_heat_audit_item(f"△ DG-Giebelfläche {rid}: {gable_area:.1f} m² nahe Wandreferenz {wall_ref:.1f} m²", rid)

        duplicates = [
            (rid, et, key, area, count)
            for (rid, et, key, area), count in roof_signature_counts.items()
            if count > 1 and ("dach" in et.lower() or "giebel" in et.lower())
        ]
        for rid, et, key, area, count in duplicates[:6]:
            self._add_heat_audit_item(f"✗ Mögliche Doppelung {rid}: {count}x {et} {area} m² ({key})", rid)

    def _on_heat_audit_item_clicked(self, item: QListWidgetItem) -> None:
        rid = str(item.data(Qt.UserRole) or "")
        if rid and rid in getattr(self, "rooms", {}):
            self._selected_room_id = rid
            if hasattr(self, "_populate_room_form"):
                self._populate_room_form()
            dock = getattr(self, "dock_properties", None)
            if dock is not None:
                dock.show()
                dock.raise_()

    def _autosave_if_dirty(self) -> None:
        if not getattr(self, "_dirty", False):
            return
        base = self._project_rooms_path or Path.cwd() / "heizlast_autosave_rooms.csv"
        path = Path(str(base) + ".autosave.json")
        try:
            path.write_text(json.dumps(self._comfort_snapshot(), indent=2, ensure_ascii=False), encoding="utf-8")
            self.statusBar().showMessage(f"Autosave geschrieben: {path.name}", 2500)
        except Exception:
            pass

    def _duplicate_selected_room(self) -> None:
        rid = getattr(self, "_selected_room_id", None)
        room = self.rooms.get(rid) if rid else None
        if room is None:
            return
        data = asdict(room)
        data["id"] = f"{room.id}_copy_{uuid4().hex[:4]}"
        data["name"] = f"{room.name} Kopie"
        data["x_m"] = float(room.x_m) + 0.4
        data["y_m"] = float(room.y_m) + 0.4
        clone = RoomModel(**data)
        self.rooms[clone.id] = clone
        self._selected_room_id = clone.id
        self._rebuild_all_graphics()
        self._recompute_and_redraw()
        self._populate_room_form()

    def _filter_room_elements_list(self, text: str) -> None:
        needle = str(text or "").strip().lower()
        for i in range(self.list_room_elements.count()):
            item = self.list_room_elements.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _refresh_plausibility_panel(self) -> None:
        lst = getattr(self, "list_plausibility", None)
        if lst is None:
            return
        lst.clear()
        issues: list[tuple[str, str]] = []
        if not self.rooms:
            issues.append(("Hinweis", "Noch keine Räume angelegt."))
        for room in self.rooms.values():
            if float(getattr(room, "w_m", 0.0) or 0.0) <= 0 or float(getattr(room, "h_m", 0.0) or 0.0) <= 0:
                issues.append(("Fehler", f"Raum {room.id}: Breite/Höhe prüfen."))
        attic = getattr(self.project_cfg, "attic", None)
        if attic is not None and bool(getattr(attic, "enabled", False)):
            if abs(float(getattr(attic, "ridge_offset_ratio", 0.0) or 0.0)) > 1e-9 and getattr(attic, "ridge_height_m", None) is None:
                issues.append(("Hinweis", "DG-Dach: Firstversatz ohne explizite Firsthöhe."))
            if str(getattr(attic, "roof_boundary", "outside") or "outside") == "unheated_attic":
                issues.append(("Hinweis", "DG-Dach: Faktor für Dachboden/Abseite prüfen."))
        if not issues:
            issues.append(("OK", "Keine offensichtlichen Plausibilitätsprobleme."))
        for kind, text in issues:
            item = QListWidgetItem(f"{kind}: {text}")
            lst.addItem(item)
