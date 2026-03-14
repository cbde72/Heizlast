from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
from ..domain.models import ElementModel
from ..domain.models import RoomModel

from ..models import RoomModel, ElementModel
from ..house_state import HouseState


BuildAutoWallsFn = Callable[[List[RoomModel]], List[ElementModel]]


@dataclass
class HouseDomainService:
    """Domain services: geometry normalization + auto-element rebuild + meta overrides.
    Qt-free. No QGraphics, no dialogs, no settings, no IO.
    """

    def normalize_room_geometry(self, r: RoomModel) -> None:
        """Single Source of Truth for room geometry (x/y/w/h/height)."""
        if r is None:
            return

        MIN_SIZE = 0.20
        # snap_m is a domain-ish helper but lives in graphics.py today; import locally to avoid cycles.
        from ...ui.graphics import snap_m  # type: ignore

        try:
            r.x_m = snap_m(float(r.x_m or 0.0))
            r.y_m = snap_m(float(r.y_m or 0.0))

            r.w_m = max(MIN_SIZE, snap_m(abs(float(r.w_m or MIN_SIZE))))
            r.h_m = max(MIN_SIZE, snap_m(abs(float(r.h_m or MIN_SIZE))))

            if float(getattr(r, "height_m", 0.0) or 0.0) <= 1e-6:
                r.height_m = 2.50

            r.recompute_volume()
        except Exception:
            pass

    # ---------------- meta overrides ----------------
    def meta_parse(self, meta: str) -> Dict[str, str]:
        d: Dict[str, str] = {}
        for part in (meta or "").split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k:
                    d[k] = v
        return d

    def meta_dump(self, d: Dict[str, object]) -> str:
        parts: List[str] = []
        for k, v in d.items():
            if v is None:
                continue
            ks = str(k).strip().replace("|", "/").replace("\n", " ").replace("\r", " ")
            vs = str(v).strip().replace("|", "/").replace("\n", " ").replace("\r", " ")
            if ks:
                parts.append(f"{ks}={vs}")
        return "|".join(parts)

    def meta_set_overrides(self, e: ElementModel, **ov) -> None:
        d = self.meta_parse(getattr(e, "meta", "") or "")
        for k, v in ov.items():
            if v is None:
                d.pop(k, None)
            else:
                d[k] = str(v)
        e.meta = self.meta_dump(d)

    def meta_get_overrides(self, e: ElementModel) -> Dict[str, object]:
        d = self.meta_parse(getattr(e, "meta", "") or "")
        out: Dict[str, object] = {}
        for k in ("ov_u", "ov_f", "ov_h", "ov_a"):
            if k in d:
                try:
                    out[k] = float(d[k])
                except Exception:
                    pass
        if "ov_type" in d:
            out["ov_type"] = str(d["ov_type"])
        return out

    def snapshot_user_overrides_for_autowalls(self, elements: List[ElementModel]) -> Dict[str, Dict]:
        snap: Dict[str, Dict] = {}
        for e in elements:
            meta = str(getattr(e, "meta", "") or "")
            uid = str(getattr(e, "uid", "") or "")
            if not uid:
                continue
            if ("auto_contour" in meta) or ("auto_shared" in meta) or uid.startswith("auto_"):
                snap[uid] = {
                    "u_w_m2k": getattr(e, "u_w_m2k", None),
                    "psi_w_mk": getattr(e, "psi_w_mk", None),
                    "factor": getattr(e, "factor", None),
                    "area_m2": getattr(e, "area_m2", None),
                    "height_m": getattr(e, "height_m", None),
                    "element_type": getattr(e, "element_type", None),
                    "name": getattr(e, "name", None),
                    "notes": getattr(e, "notes", None),
                    "material": getattr(e, "material", None),
                    "meta_ov": self.meta_get_overrides(e),
                }
        return snap

    def apply_user_overrides_to_autowalls(self, new_elements: List[ElementModel], snap: Dict[str, Dict]) -> None:
        for e in new_elements:
            uid = str(getattr(e, "uid", "") or "")
            if not uid or uid not in snap:
                continue
            d = snap.get(uid) or {}

            if d.get("u_w_m2k") is not None:
                e.u_w_m2k = float(d["u_w_m2k"])
            if d.get("psi_w_mk") is not None:
                e.psi_w_mk = float(d["psi_w_mk"])
            if d.get("factor") is not None:
                e.factor = float(d["factor"])
            if d.get("area_m2") is not None:
                e.area_m2 = float(d["area_m2"])
            if d.get("height_m") is not None:
                e.height_m = float(d["height_m"])
            if d.get("element_type") is not None:
                e.element_type = str(d["element_type"])
            if d.get("name") is not None:
                e.name = d["name"]
            if d.get("notes") is not None:
                e.notes = d["notes"]
            if d.get("material") is not None:
                e.material = d["material"]

            meta_ov = d.get("meta_ov") or {}
            ov_u = meta_ov.get("ov_u", getattr(e, "u_w_m2k", None))
            ov_f = meta_ov.get("ov_f", getattr(e, "factor", None))
            ov_h = meta_ov.get("ov_h", getattr(e, "height_m", None))
            ov_a = meta_ov.get("ov_a", getattr(e, "area_m2", None))
            ov_type = meta_ov.get("ov_type", getattr(e, "element_type", None))

            self.meta_set_overrides(
                e,
                ov_u=f"{float(ov_u):.6g}" if ov_u is not None else None,
                ov_f=f"{float(ov_f):.6g}" if ov_f is not None else None,
                ov_h=f"{float(ov_h):.6g}" if ov_h is not None else None,
                ov_a=f"{float(ov_a):.6g}" if ov_a is not None else None,
                ov_type=str(ov_type) if ov_type is not None else None,
            )

    # ---------------- auto walls rebuild ----------------
    def rebuild_autowalls_all(
        self,
        state: HouseState,
        build_auto_walls: BuildAutoWallsFn,
        floors: Tuple[str, ...] = ("EG", "DG"),
    ) -> None:
        """Rebuilds auto walls in-place (state.elements). Qt-free.
        Requires a build_auto_walls(rooms)->elements function injected from application layer.
        """

        def _is_auto_wall(e: ElementModel) -> bool:
            uid = str(getattr(e, "uid", "") or "")
            meta = str(getattr(e, "meta", "") or "")
            return (
                uid.startswith("auto_")
                or meta.startswith("auto_")
                or ("auto_contour" in meta)
                or ("auto_shared" in meta)
            )

        snap = self.snapshot_user_overrides_for_autowalls(state.elements)

        # remove old autos
        state.elements = [e for e in state.elements if not _is_auto_wall(e)]

        # build new autos
        autos: List[ElementModel] = []
        for floor in floors:
            rooms = [r for r in state.rooms.values() if r.floor == floor]
            autos.extend(build_auto_walls(rooms))

        # apply overrides
        self.apply_user_overrides_to_autowalls(autos, snap)

        # clean + de-dup
        seen = set()
        clean: List[ElementModel] = []
        for e in autos:
            if not getattr(e, "has_geometry", lambda: False)():
                continue
            try:
                x0 = float(e.x0_m); y0 = float(e.y0_m); x1 = float(e.x1_m); y1 = float(e.y1_m)
            except Exception:
                continue

            dx = x1 - x0
            dy = y1 - y0
            if abs(dx) <= 1e-6 and abs(dy) <= 1e-6:
                continue

            if abs(dy) <= 1e-6 and abs(dx) > 1e-6:
                orient = "H"
                c = round(y0, 6)
                a0, a1 = sorted([round(x0, 6), round(x1, 6)])
            elif abs(dx) <= 1e-6 and abs(dy) > 1e-6:
                orient = "V"
                c = round(x0, 6)
                a0, a1 = sorted([round(y0, 6), round(y1, 6)])
            else:
                orient = "S"
                c = 0.0
                a0, a1 = 0.0, 0.0

            key = (e.floor, orient, c, a0, a1, (e.element_type or "").strip().lower())
            if key in seen:
                continue
            seen.add(key)
            clean.append(e)

        state.elements.extend(clean)