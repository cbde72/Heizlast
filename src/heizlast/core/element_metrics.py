from __future__ import annotations

from typing import Dict, List
from ..domain.models import ElementModel

from ..domain.models import RoomModel
from .element_access import element_belongs_to_room, element_axis_length_from_geometry


class ElementMetricsService:
    """Domain-Service: konsolidiert Element-Metriken (length/height/area) unabhängig von der UI.

    Wichtige Regeln:
    - Nicht-auto_contour: length_m ist *immer* Geometrie (wie die alte MainWindow._ensure_element_metrics).
    - auto_contour:
        * Wenn das Element nicht die volle Raumseite abdeckt (Teilsegment), bleibt length_m = Segmentlänge.
        * Nur wenn Segmentlänge ~ volle Raumseite ist, darf auf room.w_m / room.h_m gesetzt werden.
      Damit ist bei Teilüberlappung automatisch: Außenwandlänge = Gesamt - Innenanteil.
    """

    def __init__(self, rooms: Dict[str, RoomModel], elements: List[ElementModel]):
        self.rooms = rooms
        self.elements = elements

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def ensure_metrics(self, e: ElementModel) -> None:
        if e is None or not getattr(e, "has_geometry", lambda: False)():
            return

        # Apply persisted user overrides first (ov_* keys in meta)
        self._apply_meta_overrides(e)
        
        meta = str(getattr(e, "meta", "") or "")
        et = (getattr(e, "element_type", "") or "").strip().lower()

        has_ov_L = ("ov_L=" in meta)
        has_ov_h = ("ov_h=" in meta)
        has_ov_a = ("ov_a=" in meta)

        # 1) Länge
        if "auto_contour" in meta:
            self.apply_autocontour_length_rule(e)
        else:
            # exakt wie die alte _ensure_element_metrics(): immer aus Geometrie
            self._set_length_from_dxdy(e)

        # 2) Höhe
        self._fill_height_from_room_if_missing(e)

        # 3) Fläche (nur wenn fehlt)
        self._fill_area_if_missing(e, et)
    
    
    
    
    def bind(self, rooms, elements):
        """Muss aufgerufen werden, wenn MainWindow self.rooms/self.elements ersetzt."""
        self.rooms = rooms
        self.elements = elements
    # Backwards-compat alias (falls irgendwo noch so aufgerufen wird)
    def apply_autocontour_display_length(self, e: ElementModel) -> None:
        self.apply_autocontour_length_rule(e)

    def apply_autocontour_length_rule(self, e: ElementModel) -> None:
        """auto_contour-Regel:

        - Bestimme Segmentlänge seg_L aus Geometrie.
        - Bestimme erwartete volle Seitenlänge side_L (H->room.w_m, V->room.h_m).
        - Wenn seg_L deutlich kleiner als side_L ist, ist es ein Teilsegment -> length_m = seg_L.
        - Sonst (volle Seite) -> length_m = side_L.

        (Zusätzlich: wenn Seite anhand anderer Outer-Segmente segmentiert erscheint, bleibt Segmentlänge.)
        """
        if e is None or not getattr(e, "has_geometry", lambda: False)():
            return

        meta = str(getattr(e, "meta", "") or "")
        if "auto_contour" not in meta:
            return

        rid = str(getattr(e, "room_id", "") or "")
        r = self.rooms.get(rid)
        if r is None:
            return

        seg_L = element_axis_length_from_geometry(e)
        if seg_L is None:
            return
        seg_L = float(seg_L)

        orient = self._orient_from_geometry(e)
        if orient is None:
            #print(f"[DEBUG][metrics-auto] uid={getattr(e,'uid',None)} segment_length={seg_L}")
            e.length_m = seg_L
            return

        side_L = float(r.w_m) if orient == "H" else float(r.h_m)

        # Heuristik 1: Teilsegment? -> nie auf volle Seitenlänge aufblasen
        # Toleranz relativ + absolut
        if abs(seg_L - side_L) > max(1e-3, 0.01 * max(side_L, 1.0)):
            #print(f"[DEBUG][metrics-auto] uid={getattr(e,'uid',None)} segment_length={seg_L}")
            e.length_m = seg_L
        else:
            # Heuristik 2: auch wenn seg_L ~ side_L, aber die Seite ist segmentiert (>=2 outer segmente), bleib bei seg_L
            if self._outer_segments_on_same_side(r, orient, e) >= 2:
                #print(f"[DEBUG][metrics-auto] uid={getattr(e,'uid',None)} segment_length={seg_L}")
                e.length_m = seg_L
            else:
                #print(f"[DEBUG][metrics-auto] uid={getattr(e,'uid',None)} side_length={side_L}")
                e.length_m = side_L

        # Höhe/Fläche nachziehen, falls möglich
        self._fill_height_from_room_if_missing(e)
        H = float(getattr(e, "height_m", 0.0) or 0.0)
        if H > 1e-6 and float(getattr(e, "area_m2", 0.0) or 0.0) <= 1e-6:
            e.area_m2 = float(getattr(e, "length_m", 0.0) or 0.0) * H
    
    
    def _apply_meta_overrides(self, e: ElementModel) -> None:
        """Apply persisted user overrides from e.meta (ov_*) to the element.

        Supported keys:
          - ov_u, ov_f, ov_h, ov_a, ov_L (floats)
          - ov_type (string)

        Overrides should *win* over auto-derived defaults, but geometry-derived values
        (like length from dx/dy) are still applied when no override is present.
        """
        meta = str(getattr(e, "meta", "") or "")
        if not meta:
            return

        d = {}
        for part in meta.split("|"):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k:
                d[k] = v

        if "ov_type" in d:
            try:
                e.element_type = str(d["ov_type"])
            except Exception:
                pass

        def _apply_float(attr: str, key: str):
            if key not in d:
                return
            try:
                val = float(d[key])
            except Exception:
                return
            try:
                setattr(e, attr, val)
            except Exception:
                pass

        _apply_float("u_w_m2k", "ov_u")
        _apply_float("factor", "ov_f")
        _apply_float("height_m", "ov_h")
        _apply_float("area_m2", "ov_a")
        _apply_float("length_m", "ov_L")
    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _set_length_from_dxdy(self, e: ElementModel) -> None:
        try:
            x0 = float(e.x0_m); y0 = float(e.y0_m)
            x1 = float(e.x1_m); y1 = float(e.y1_m)
        except Exception:
            return

        dx = x1 - x0
        dy = y1 - y0

        if abs(dy) <= 1e-6 and abs(dx) > 1e-6:
            #print(f"[DEBUG][metrics-dxdy] uid={getattr(e,'uid',None)} new_length={abs(dx)}")
            e.length_m = abs(dx)
        elif abs(dx) <= 1e-6 and abs(dy) > 1e-6:
            #print(f"[DEBUG][metrics-dxdy] uid={getattr(e,'uid',None)} new_length={abs(dy)}")
            e.length_m = abs(dy)
        else:
            #print(f"[DEBUG][metrics-dxdy] uid={getattr(e,'uid',None)} new_length={(dx*dx+dy*dy)**0.5}")
            e.length_m = (dx * dx + dy * dy) ** 0.5

    def _fill_height_from_room_if_missing(self, e: ElementModel) -> None:
        H = float(getattr(e, "height_m", 0.0) or 0.0)
        if H > 1e-6:
            return
        rid = str(getattr(e, "room_id", "") or "")
        r = self.rooms.get(rid)
        if r is None:
            return
        Hr = float(getattr(r, "height_m", 0.0) or 0.0)
        if Hr > 1e-6:
            e.height_m = Hr

    def _fill_area_if_missing(self, e: ElementModel, et_lower: str | None = None) -> None:
        A = float(getattr(e, "area_m2", 0.0) or 0.0)
        if A > 1e-6:
            return

        et = et_lower if et_lower is not None else (getattr(e, "element_type", "") or "").strip().lower()
        L = float(getattr(e, "length_m", 0.0) or 0.0)
        H = float(getattr(e, "height_m", 0.0) or 0.0)

        if et == "fenster":
            if L > 1e-6 and H > 1e-6:
                e.area_m2 = L * H
            return

        if "wand" in et:
            if L > 1e-6 and H > 1e-6:
                e.area_m2 = L * H

    def _orient_from_geometry(self, e: ElementModel, tol: float = 1e-6):
        try:
            x0 = float(e.x0_m); y0 = float(e.y0_m)
            x1 = float(e.x1_m); y1 = float(e.y1_m)
        except Exception:
            return None
        if abs(y1 - y0) <= tol and abs(x1 - x0) > tol:
            return "H"
        if abs(x1 - x0) <= tol and abs(y1 - y0) > tol:
            return "V"
        return None

    def _outer_segments_on_same_side(self, r: RoomModel, orient: str, e_ref: ElementModel) -> int:
        """Zählt auto_contour-Außenwand-Segmente derselben Raumseite.
        Wenn >=2 -> Seite ist segmentiert.
        """
        rx0 = float(r.x_m); ry0 = float(r.y_m)
        rx1 = rx0 + float(r.w_m); ry1 = ry0 + float(r.h_m)

        try:
            x0 = float(e_ref.x0_m); y0 = float(e_ref.y0_m)
            x1 = float(e_ref.x1_m); y1 = float(e_ref.y1_m)
        except Exception:
            return 1

        if orient == "H":
            c = y0
            if abs(c - ry0) <= 1e-3:
                side = ("H", ry0)
            elif abs(c - ry1) <= 1e-3:
                side = ("H", ry1)
            else:
                return 1
        else:
            c = x0
            if abs(c - rx0) <= 1e-3:
                side = ("V", rx0)
            elif abs(c - rx1) <= 1e-3:
                side = ("V", rx1)
            else:
                return 1

        cnt = 0
        for e in self.elements:
            et = (getattr(e, "element_type", "") or "").lower()
            if ("aussen" not in et and "außen" not in et):
                continue
            m = str(getattr(e, "meta", "") or "")
            if "auto_contour" not in m:
                continue
            if not element_belongs_to_room(e, r.id):
                continue
            if not getattr(e, "has_geometry", lambda: False)():
                continue

            try:
                xx0 = float(e.x0_m); yy0 = float(e.y0_m)
                xx1 = float(e.x1_m); yy1 = float(e.y1_m)
            except Exception:
                continue

            if side[0] == "H" and abs(yy1 - yy0) <= 1e-6 and abs(yy0 - side[1]) <= 1e-3:
                cnt += 1
            elif side[0] == "V" and abs(xx1 - xx0) <= 1e-6 and abs(xx0 - side[1]) <= 1e-3:
                cnt += 1

        return cnt if cnt > 0 else 1