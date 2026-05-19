from typing import List, Optional
import json
from uuid import uuid4
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDoubleSpinBox,
    QTextEdit,
    QLabel,
    QPushButton,
    QDialogButtonBox,
    QMessageBox,
)


from ..core.anchors import dump_meta, parse_edge_anchor, parse_line_token, parse_meta, update_edge_anchor_meta
from ..core.element_access import get_room_elements
from ..core.geometry import classify_floor_edge_spans, nearest_edge_span_for_point
from ..domain.models import ElementModel
from ..core.polygon_ops import snap_m

class MainWindowElementEditMixin:
    def _project_u_default_for_element(self, element_type: str) -> float:
        cfg = getattr(self, "project_cfg", None)
        et = str(element_type or "").lower()
        if "fenster" in et:
            return float(getattr(cfg, "u_fenster_w_m2k", 1.30) or 1.30)
        if "tür" in et or "tuer" in et:
            return float(getattr(cfg, "u_tuer_w_m2k", 1.80) or 1.80)
        if "bodenplatte" in et or "boden" in et:
            return float(getattr(cfg, "u_bodenplatte_w_m2k", 0.35) or 0.35)
        if "erd" in et:
            return float(getattr(cfg, "u_erdberuehrte_wand_w_m2k", 0.45) or 0.45)
        if "innenwand" in et or "innen" in et:
            return 0.0
        if "kellerdecke" in et:
            return float(getattr(cfg, "u_kellerdecke_w_m2k", 0.60) or 0.60)
        if "geschossdecke" in et:
            return float(getattr(cfg, "u_eg_geschossdecke_w_m2k", 0.40) or 0.40)
        if "speicherdecke" in et:
            return float(getattr(cfg, "u_dg_geschossdecke_w_m2k", 0.20) or 0.20)
        if "dach" in et:
            attic = getattr(cfg, "attic", None)
            return float(getattr(attic, "u_roof_w_m2k", 0.20) or 0.20)
        return float(getattr(cfg, "u_aussenwand_w_m2k", 0.35) or 0.35)

    def _on_element_assistant(self) -> None:
        rid = getattr(self, "_selected_room_id", None)
        room = self.rooms.get(rid) if rid else None
        if room is None:
            QMessageBox.information(self, "Bauteil-Assistent", "Bitte zuerst einen Raum auswählen.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Bauteil-Assistent")
        lay = QVBoxLayout(dlg)
        hint = QLabel("Geführte Eingabe für normnahe Bauteildaten. Das Bauteil wird dem selektierten Raum zugeordnet.")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        form = QFormLayout()
        lay.addLayout(form)

        cb_type = QComboBox()
        cb_type.addItems(["Außenwand", "Innenwand", "Fenster", "Tür", "Dach", "Kellerdecke", "Geschossdecke", "Speicherdecke", "Bodenplatte", "Erdberührte Wand"])
        form.addRow("Bauteiltyp", cb_type)

        cb_boundary = QComboBox()
        cb_boundary.addItems(["Außenluft", "Erdreich", "unbeheizter Keller", "unbeheizter Dachraum", "Nachbarzone/Interzone"])
        form.addRow("Randbedingung", cb_boundary)

        sp_area = QDoubleSpinBox()
        sp_area.setRange(0.0, 10000.0)
        sp_area.setDecimals(3)
        sp_area.setSingleStep(0.5)
        sp_area.setValue(max(0.0, float(room.area_m2() if "Boden" in cb_type.currentText() else room.perimeter_m() * room.height_m)))
        form.addRow("Fläche A [m²]", sp_area)

        sp_u = QDoubleSpinBox()
        sp_u.setRange(0.0, 20.0)
        sp_u.setDecimals(3)
        sp_u.setSingleStep(0.05)
        sp_u.setValue(self._project_u_default_for_element(cb_type.currentText()))
        form.addRow("U [W/m²K]", sp_u)

        sp_factor = QDoubleSpinBox()
        sp_factor.setRange(0.0, 5.0)
        sp_factor.setDecimals(3)
        sp_factor.setSingleStep(0.05)
        sp_factor.setValue(1.0)
        form.addRow("Temperaturfaktor f", sp_factor)

        cb_source = QComboBox()
        cb_source.addItems(["Projektwert", "DIN/Normtabelle", "Hersteller-/Bauteilnachweis", "geschätzt", "manuell"])
        form.addRow("Quelle/Status", cb_source)

        ed_source = QLineEdit()
        ed_source.setPlaceholderText("z.B. Projekt-U-Wert, Datenblatt, Bestand, Annahme")
        form.addRow("Quellenhinweis", ed_source)

        def _type_changed(label: str) -> None:
            sp_u.setValue(self._project_u_default_for_element(label))
            label_l = label.lower()
            if "innenwand" in label_l:
                cb_boundary.setCurrentText("Nachbarzone/Interzone")
                sp_factor.setValue(0.0)
                sp_area.setValue(max(0.0, float(room.perimeter_m() * room.height_m * 0.5)))
            elif any(token in label_l for token in ("boden", "decke")):
                sp_area.setValue(max(0.0, float(room.area_m2())))
            elif "fenster" in label_l or "tür" in label_l or "tuer" in label_l:
                sp_area.setValue(1.5 if "fenster" in label_l else 2.0)
            else:
                if "außenwand" in label_l or "aussenwand" in label_l:
                    cb_boundary.setCurrentText("Außenluft")
                    sp_factor.setValue(1.0)
                sp_area.setValue(max(0.0, float(room.perimeter_m() * room.height_m)))

        cb_type.currentTextChanged.connect(_type_changed)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay.addWidget(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return

        boundary_map = {
            "Außenluft": "outside",
            "Erdreich": "ground",
            "unbeheizter Keller": "basement",
            "unbeheizter Dachraum": "attic_unheated",
            "Nachbarzone/Interzone": "interzone",
        }
        source_status = cb_source.currentText()
        meta = dump_meta({
            "manual_assistant": "1",
            "boundary": boundary_map.get(cb_boundary.currentText(), "outside"),
            "source_status": source_status,
            "source_note": ed_source.text().strip(),
        })
        element = ElementModel(
            room_id=str(room.id),
            element_type=cb_type.currentText(),
            area_m2=float(sp_area.value()),
            u_w_m2k=float(sp_u.value()),
            factor=float(sp_factor.value()),
            floor=str(getattr(room, "floor", "") or ""),
            uid=f"manual_{uuid4().hex[:10]}",
            meta=meta,
        )
        self.elements.append(element)
        try:
            self.metrics.bind(self.rooms, self.elements)
        except Exception:
            pass
        self._populate_room_elements_list()
        self._recompute_and_redraw()
        self._mark_dirty("element_assistant")

    def _edit_element_dialog(self, e) -> bool:
        """Öffnet einen Dialog zum Bearbeiten eines Elements."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Element bearbeiten")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        lay.addLayout(form)

        def ro_line(val: object) -> QLineEdit:
            w = QLineEdit(str(val) if val is not None else "")
            w.setReadOnly(True)
            return w

        # Info-Felder
        form.addRow("UID", ro_line(getattr(e, "uid", "")))
        form.addRow("Raum-ID", ro_line(getattr(e, "room_id", "")))
        form.addRow("Geschoss", ro_line(getattr(e, "floor", "")))

        # Editierbare Felder
        ed_type = QLineEdit((getattr(e, "element_type", "") or "").strip())
        ed_type.setPlaceholderText("z.B. Außenwand, Fenster, Kellerdecke, Geschossdecke ...")
        form.addRow("Typ", ed_type)

        sp_u = QDoubleSpinBox()
        sp_u.setRange(0.0, 20.0)
        sp_u.setDecimals(3)
        sp_u.setSingleStep(0.05)
        sp_u.setValue(float(getattr(e, "u_w_m2k", 0.0) or 0.0))
        form.addRow("U [W/m²K]", sp_u)

        sp_f = QDoubleSpinBox()
        sp_f.setRange(0.0, 5.0)
        sp_f.setDecimals(3)
        sp_f.setSingleStep(0.05)
        sp_f.setValue(float(getattr(e, "factor", 1.0) or 1.0))
        form.addRow("Faktor f [-]", sp_f)

        sp_a = QDoubleSpinBox()
        sp_a.setRange(0.0, 10000.0)
        sp_a.setDecimals(3)
        sp_a.setSingleStep(0.1)
        sp_a.setValue(float(getattr(e, "area_m2", 0.0) or 0.0))
        form.addRow("Fläche A [m²]", sp_a)

        sp_h = QDoubleSpinBox()
        sp_h.setRange(0.0, 20.0)
        sp_h.setDecimals(3)
        sp_h.setSingleStep(0.05)
        sp_h.setValue(float(getattr(e, "height_m", 0.0) or 0.0))
        form.addRow("Höhe [m]", sp_h)

        sp_L = QDoubleSpinBox()
        sp_L.setRange(0.0, 2000.0)
        sp_L.setDecimals(3)
        sp_L.setSingleStep(0.1)
        sp_L.setValue(float(getattr(e, "length_m", 0.0) or 0.0))
        form.addRow("Länge [m]", sp_L)

        # Meta (JSON)
        meta_raw = getattr(e, "meta", "") or ""
        meta_dict, meta_fmt = self._meta_parse_any(meta_raw)

        cb_source = QComboBox()
        cb_source.addItems(["Projektwert", "DIN/Normtabelle", "Hersteller-/Bauteilnachweis", "geschätzt", "manuell"])
        source_status = str(meta_dict.get("source_status", "") or "")
        idx = cb_source.findText(source_status)
        cb_source.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow("Quelle/Status", cb_source)

        ed_source = QLineEdit(str(meta_dict.get("source_note", "") or ""))
        ed_source.setPlaceholderText("Quellenhinweis oder Annahme")
        form.addRow("Quellenhinweis", ed_source)

        te_meta = QTextEdit()
        te_meta.setMinimumHeight(110)
        try:
            te_meta.setPlainText(json.dumps(meta_dict, indent=2, ensure_ascii=False))
        except Exception:
            te_meta.setPlainText("{}")
        lay.addWidget(QLabel("Meta (JSON):"))
        lay.addWidget(te_meta)

        # Buttons
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        lay.addWidget(bb)

        def _on_save():
            new_type = ed_type.text().strip()
            meta_txt = te_meta.toPlainText().strip()
            new_meta_dict = {}
            if meta_txt:
                try:
                    new_meta_dict = json.loads(meta_txt)
                    if not isinstance(new_meta_dict, dict):
                        raise ValueError("Meta muss ein JSON-Objekt sein ({}).")
                except Exception as ex:
                    QMessageBox.warning(dlg, "Meta JSON", f"Meta ist kein gültiges JSON:\n{ex}\n\nSpeichern abgebrochen.")
                    return

            # Meta zurück in ursprüngliches Format serialisieren (JSON bleibt JSON)
            new_meta_dict["source_status"] = cb_source.currentText()
            new_meta_dict["source_note"] = ed_source.text().strip()
            new_meta_str = self._meta_dump_any(new_meta_dict, meta_fmt)

            # Zurückschreiben
            e.element_type = new_type
            e.u_w_m2k = float(sp_u.value())
            e.factor = float(sp_f.value())
            e.area_m2 = float(sp_a.value())
            e.height_m = float(sp_h.value())
            #print(f"[DEBUG][dialog] uid={e.uid} manual_length={sp_L.value()}")
            e.length_m = float(sp_L.value())
            e.meta = new_meta_str

            # >>> Persistiere Overrides in meta (ov_*) damit Auto-Rebuild & CSV-Roundtrip die Werte behalten
            self._meta_set_overrides(
                e,
                ov_u=f"{float(e.u_w_m2k):.6g}",
                ov_f=f"{float(e.factor):.6g}",
                ov_h=f"{float(e.height_m):.6g}",
                ov_a=f"{float(e.area_m2):.6g}",
                ov_type=str(e.element_type or ""),
            )

            dlg.accept()

        bb.accepted.connect(_on_save)
        bb.rejected.connect(dlg.reject)

        return dlg.exec() == QDialog.Accepted

    # ---------------- Element-Hervorhebung ----------------


    def _reanchor_windows_for_room(self, room_id: str) -> None:
        room = self.rooms.get(room_id)
        if room is None:
            return
        floor = getattr(room, 'floor', None)
        rooms_on_floor = [r for r in self.rooms.values() if getattr(r, 'floor', None) == floor]
        spans = [s for s in classify_floor_edge_spans(rooms_on_floor) if room_id in s.room_ids and s.element_type == 'Aussenwand']
        if not spans:
            return
        spans_by_uid = {s.uid: s for s in spans}

        for win in self.elements:
            if getattr(win, 'room_id', None) != room_id:
                continue
            if str(getattr(win, 'element_type', '')) != 'Fenster':
                continue
            if not win.has_geometry():
                continue

            anchor = parse_edge_anchor(getattr(win, 'meta', '') or '')
            parent = anchor.get('parent')
            span = spans_by_uid.get(parent) if parent else None
            if span is None:
                cx = (float(win.x0_m) + float(win.x1_m)) * 0.5
                cy = (float(win.y0_m) + float(win.y1_m)) * 0.5
                span = nearest_edge_span_for_point(rooms_on_floor, floor, cx, cy, prefer_outer=True, room_id=room_id)
                if span is None:
                    continue

            (x0, y0), (x1, y1) = span.endpoints()
            dx, dy = (x1 - x0), (y1 - y0)
            L = (dx * dx + dy * dy) ** 0.5
            if L <= 1e-9:
                continue
            ux, uy = dx / L, dy / L

            w_len = float(anchor.get('w') or 0.0)
            if w_len <= 1e-9:
                wx0, wy0 = float(win.x0_m), float(win.y0_m)
                wx1, wy1 = float(win.x1_m), float(win.y1_m)
                w_len = ((wx1 - wx0) ** 2 + (wy1 - wy0) ** 2) ** 0.5

            s = float(anchor.get('s') or 0.0)
            if s <= 0.0:
                cx = (float(win.x0_m) + float(win.x1_m)) * 0.5
                cy = (float(win.y0_m) + float(win.y1_m)) * 0.5
                s = (cx - x0) * ux + (cy - y0) * uy

            half = 0.5 * w_len
            if L <= w_len:
                s = 0.5 * L
            else:
                s = max(half, min(s, L - half))

            cx = x0 + ux * s
            cy = y0 + uy * s
            ax = cx - ux * half
            ay = cy - uy * half
            bx = cx + ux * half
            by = cy + uy * half
            win.x0_m, win.y0_m, win.x1_m, win.y1_m = ax, ay, bx, by

            orient = 'H' if abs(dy) <= 1e-6 and abs(dx) > 1e-6 else 'V'
            axis_c = y0 if orient == 'H' else x0
            axis_a0 = min(x0, x1) if orient == 'H' else min(y0, y1)
            axis_a1 = max(x0, x1) if orient == 'H' else max(y0, y1)
            win.meta = update_edge_anchor_meta(
                getattr(win, 'meta', '') or '',
                parent=span.uid,
                orient=orient,
                c=axis_c,
                a0=axis_a0,
                a1=axis_a1,
                s=s,
                w=w_len,
                rooms=getattr(span, 'room_ids', None),
            )

    #

    def _apply_room_wh_to_autocontour(self, e: ElementModel) -> None:
        """Setzt length_m für auto_contour Außenwände explizit aus Raum w/h (H->w, V->h)."""
        try:
            meta = str(getattr(e, "meta", "") or "")
            if "auto_contour" not in meta:
                return

            rid = str(getattr(e, "room_id", "") or "")
            r = self.rooms.get(rid)
            if r is None:
                return

            # orient aus meta "line=H:..." oder "line=V:..."
            orient = None
            d_meta = parse_meta(meta)
            orient, _ = parse_line_token(d_meta.get("line"))
            if not orient:
                orient = str(d_meta.get("orient", "") or "").strip().upper()[:1] or None

            if orient == "H":
                #print(f"[DEBUG][main-ui-roomWH] uid={e.uid} set_length_from_room_w={r.w_m}")
                L = float(r.w_m)
            elif orient == "V":
                #print(f"[DEBUG][main-ui-roomWH] uid={e.uid} set_length_from_room_w={r.h_m}")
                L = float(r.h_m)
            else:
                return

            if L <= 1e-9:
                return

            #print(f"[DEBUG][main-ui-roomWH] uid={e.uid} set_length_from_room_w={L}")
            e.length_m = L

            # Höhe sicherstellen (falls nicht gesetzt)
            H = float(getattr(e, "height_m", 0.0) or 0.0)
            if H <= 1e-9:
                H = float(getattr(r, "height_m", 0.0) or 0.0)
            if H > 1e-9:
                e.height_m = H
                e.area_m2 = float(L) * float(H)
        except Exception:
            pass

    def _is_wall_element(self, e) -> bool:
        et = str(getattr(e, "element_type", "") or "")
        uid = str(getattr(e, "uid", "") or "")
        if et in ("Aussenwand", "Außenwand", "Innenwand"):
            return True
        # auto walls
        if et.startswith("auto_Aussenwand") or et.startswith("auto_Innenwand"):
            return True
        if uid.startswith("auto_Aussenwand") or uid.startswith("auto_Innenwand"):
            return True
        return False

    def _room_elements(self, rid: str) -> List[ElementModel]:
        """Zentrale Sicht: alle Elemente, die zu rid gehören (owner + shared via meta rooms=...)."""
        return get_room_elements(self.elements, rid)


    def _propose_element_move(self, e, new_x0_m: float, new_y0_m: float) -> Optional[tuple]:
        """
        Wird während des Ziehens eines Elements aufgerufen.
        Gibt gesnappte Koordinaten zurück oder blockiert die Bewegung.
        """
        if e is None or not getattr(e, "has_geometry", lambda: False)():
            return None

        x0, y0, x1, y1 = float(e.x0_m), float(e.y0_m), float(e.x1_m), float(e.y1_m)
        dx = x1 - x0
        dy = y1 - y0
        is_h = abs(dy) < 1e-9 and abs(dx) > 1e-9
        is_v = abs(dx) < 1e-9 and abs(dy) > 1e-9
        if not (is_h or is_v):
            return (x0, y0)

        SNAP_AXIS = 0.08
        SNAP_END = 0.10

        # Andere Wände sammeln
        others = []
        for o in self.elements:
            if o is e:
                continue
            if not getattr(o, "has_geometry", lambda: False)():
                continue
            if str(getattr(o, "element_type", "") or "").lower().startswith("fenster"):
                continue
            uid = str(getattr(o, "uid", "") or "")
            if uid.startswith("deck_"):
                continue
            ox0, oy0, ox1, oy1 = float(o.x0_m), float(o.y0_m), float(o.x1_m), float(o.y1_m)
            odx = ox1 - ox0
            ody = oy1 - oy0
            oh = abs(ody) < 1e-9 and abs(odx) > 1e-9
            ov = abs(odx) < 1e-9 and abs(ody) > 1e-9
            if not (oh or ov):
                continue
            others.append((o, ox0, oy0, ox1, oy1, oh, ov))

        sx = snap_m(new_x0_m)
        sy = snap_m(new_y0_m)
        nx0, ny0 = sx, sy
        nx1, ny1 = sx + dx, sy + dy

        # Achsen-Snapping
        if is_h:
            target_y = None
            best = SNAP_AXIS
            for o, ox0, oy0, ox1, oy1, oh, ov in others:
                if not oh:
                    continue
                d = abs(oy0 - ny0)
                if d < best:
                    best = d
                    target_y = oy0
            if target_y is not None:
                ny0 = target_y
                ny1 = target_y
        else:
            target_x = None
            best = SNAP_AXIS
            for o, ox0, oy0, ox1, oy1, oh, ov in others:
                if not ov:
                    continue
                d = abs(ox0 - nx0)
                if d < best:
                    best = d
                    target_x = ox0
            if target_x is not None:
                nx0 = target_x
                nx1 = target_x

        # Endpunkt-Snapping
        if is_h:
            cands = []
            for o, ox0, oy0, ox1, oy1, oh, ov in others:
                if not oh:
                    continue
                cands.extend([ox0, ox1])
            if cands:
                best = min(cands, key=lambda c: abs(nx0 - c))
                if abs(nx0 - best) < SNAP_END:
                    nx0 = best
                    nx1 = nx0 + dx
                else:
                    best = min(cands, key=lambda c: abs(nx1 - c))
                    if abs(nx1 - best) < SNAP_END:
                        nx1 = best
                        nx0 = nx1 - dx
        else:
            cands = []
            for o, ox0, oy0, ox1, oy1, oh, ov in others:
                if not ov:
                    continue
                cands.extend([oy0, oy1])
            if cands:
                best = min(cands, key=lambda c: abs(ny0 - c))
                if abs(ny0 - best) < SNAP_END:
                    ny0 = best
                    ny1 = ny0 + dy
                else:
                    best = min(cands, key=lambda c: abs(ny1 - c))
                    if abs(ny1 - best) < SNAP_END:
                        ny1 = best
                        ny0 = ny1 - dy

        # T-Stoß-Snapping
        def _between(v, a, b):
            lo, hi = (a, b) if a <= b else (b, a)
            return lo + 1e-6 < v < hi - 1e-6

        if is_h:
            for ex, ey in [(nx0, ny0), (nx1, ny1)]:
                for o, ox0, oy0, ox1, oy1, oh, ov in others:
                    if not ov:
                        continue
                    x_const = ox0
                    y_min = min(oy0, oy1)
                    y_max = max(oy0, oy1)
                    if abs(ex - x_const) < SNAP_END and (y_min - 1e-6) <= ey <= (y_max + 1e-6):
                        if ex == nx0:
                            nx0 = x_const
                            nx1 = nx0 + dx
                        else:
                            nx1 = x_const
                            nx0 = nx1 - dx
                        break
        else:
            for ex, ey in [(nx0, ny0), (nx1, ny1)]:
                for o, ox0, oy0, ox1, oy1, oh, ov in others:
                    if not oh:
                        continue
                    y_const = oy0
                    x_min = min(ox0, ox1)
                    x_max = max(ox0, ox1)
                    if abs(ey - y_const) < SNAP_END and (x_min - 1e-6) <= ex <= (x_max + 1e-6):
                        if ey == ny0:
                            ny0 = y_const
                            ny1 = ny0 + dy
                        else:
                            ny1 = y_const
                            ny0 = ny1 - dy
                        break

        # Kollisionsprüfung
        if is_h:
            hx0, hx1 = (nx0, nx1) if nx0 <= nx1 else (nx1, nx0)
            hy = ny0
        else:
            vy0, vy1 = (ny0, ny1) if ny0 <= ny1 else (ny1, ny0)
            vx = nx0

        for o, ox0, oy0, ox1, oy1, oh, ov in others:
            if is_h and oh and abs(oy0 - hy) < 1e-9:
                ax0, ax1 = (ox0, ox1) if ox0 <= ox1 else (ox1, ox0)
                overlap = min(hx1, ax1) - max(hx0, ax0)
                if overlap > 1e-6:
                    if not (abs(hx1 - ax0) < 1e-6 or abs(ax1 - hx0) < 1e-6):
                        return (x0, y0)
            if is_v and ov and abs(ox0 - vx) < 1e-9:
                ay0, ay1 = (oy0, oy1) if oy0 <= oy1 else (oy1, oy0)
                overlap = min(vy1, ay1) - max(vy0, ay0)
                if overlap > 1e-6:
                    if not (abs(vy1 - ay0) < 1e-6 or abs(ay1 - vy0) < 1e-6):
                        return (x0, y0)

            if is_h and ov:
                x_const = ox0
                y_const = hy
                y_min = min(oy0, oy1)
                y_max = max(oy0, oy1)
                if _between(x_const, hx0, hx1) and _between(y_const, y_min, y_max):
                    return (x0, y0)
            if is_v and oh:
                y_const = oy0
                x_min = min(ox0, ox1)
                x_max = max(ox0, ox1)
                if _between(vx, x_min, x_max) and _between(y_const, vy0, vy1):
                    return (x0, y0)

        return (nx0, ny0)

    # ---------------- Fenster einfügen ----------------

    def _meta_get_overrides(self, meta: str | None) -> dict:
        if not meta:
            return {}
        try:
            d = parse_meta(meta)
            raw = d.get("overrides", "")
            if not raw:
                return {}
            if isinstance(raw, dict):
                return raw
            return json.loads(raw)
        except Exception:
            return {}

    def _meta_set_overrides(self, target, overrides: dict | None = None, **kwargs):
        """
        Unterstützt zwei Aufrufformen:
        1) _meta_set_overrides(meta_str, {..}) -> neuer meta-String
        2) _meta_set_overrides(element_obj, ov_u="...", ov_f="...", ...) -> schreibt direkt in element.meta
        """
        merged = {}
        if isinstance(overrides, dict):
            merged.update(overrides)
        merged.update({k: v for k, v in kwargs.items() if v is not None})

        # Direkter Element-Aufruf
        if hasattr(target, "meta") and not isinstance(target, str):
            parts = parse_meta(getattr(target, "meta", "") or "")
            for k, v in merged.items():
                if v in (None, ""):
                    parts.pop(k, None)
                else:
                    parts[str(k)] = str(v)
            target.meta = dump_meta(parts)
            return target.meta

        # String-in/String-out für bestehende Call-Sites
        d = parse_meta(target or "")
        if merged:
            d["overrides"] = json.dumps(merged, ensure_ascii=False, sort_keys=True)
        else:
            d.pop("overrides", None)
        return dump_meta(d)

    def _snapshot_user_overrides_for_autowalls(self) -> dict:
        """
        Sichert benutzerdefinierte Overrides existierender Auto-Wände,
        damit sie nach einem Rebuild wieder auf die neuen Auto-Wände
        übertragen werden können.
        """
        snap: dict = {}

        for e in getattr(self, "elements", []):
            try:
                if not self._is_auto_wall(e):
                    continue

                # bevorzugt persistierte ov_* lesen; Fallback auf JSON-overrides
                parts = parse_meta(getattr(e, "meta", "") or "")
                ov = {k: v for k, v in parts.items() if str(k).startswith("ov_") and v not in (None, "")}
                if not ov:
                    ov = self._meta_get_overrides(getattr(e, "meta", ""))
                if not ov:
                    continue

                key = (
                    getattr(e, "room_id", ""),
                    getattr(e, "floor", ""),
                    round(float(getattr(e, "x0_m", 0.0)), 6),
                    round(float(getattr(e, "y0_m", 0.0)), 6),
                    round(float(getattr(e, "x1_m", 0.0)), 6),
                    round(float(getattr(e, "y1_m", 0.0)), 6),
                    getattr(e, "element_type", ""),
                )
                snap[key] = ov
            except Exception:
                pass

        return snap

    def _apply_user_overrides_to_autowalls(self, autos: list, snap: dict) -> None:
        if not snap:
            return

        for e in autos:
            try:
                if not self._is_auto_wall(e):
                    continue

                key = (
                    getattr(e, "room_id", ""),
                    getattr(e, "floor", ""),
                    round(float(getattr(e, "x0_m", 0.0)), 6),
                    round(float(getattr(e, "y0_m", 0.0)), 6),
                    round(float(getattr(e, "x1_m", 0.0)), 6),
                    round(float(getattr(e, "y1_m", 0.0)), 6),
                    getattr(e, "element_type", ""),
                )

                ov = snap.get(key)
                if not ov:
                    continue

                e.meta = self._meta_set_overrides(getattr(e, "meta", ""), ov)
            except Exception:
                pass
