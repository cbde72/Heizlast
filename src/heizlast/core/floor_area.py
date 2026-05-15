from __future__ import annotations

import os
from typing import Dict, List, Optional

from ..domain.models import RoomModel
from .heatload_types import ThicknessMode, WALL_THICKNESS_OUTER_M

try:
    import matplotlib.pyplot as _plt
except Exception:  # pragma: no cover - optional plotting dependency
    _plt = None


def calc_floor_living_area_by_floor(
    *,
    rooms: List[RoomModel],
    results_by_room: Dict[str, dict],
    thickness_mode: ThicknessMode = "full",
    area_shrink_factor: float = 1.0,
) -> Dict[str, object]:
    """Berechnet Wohnfläche und Volumen je Geschoss."""
    by_floor_A: Dict[str, float] = {}
    by_floor_V: Dict[str, float] = {}
    by_room: List[Dict[str, object]] = []

    for r in rooms:
        fl = str(getattr(r, "floor", "") or "").strip().upper() or "?"
        rr = results_by_room.get(r.id, {}) if isinstance(results_by_room, dict) else {}

        A_in = None
        V_in = None
        try:
            if isinstance(rr, dict):
                if rr.get("A_in_m2") is not None:
                    A_in = float(rr.get("A_in_m2"))
                if rr.get("V_in_m3") is not None:
                    V_in = float(rr.get("V_in_m3"))
        except Exception:
            A_in = None
            V_in = None

        if (A_in is None) or (V_in is None):
            try:
                w = max(0.0, float(getattr(r, "w_m", 0.0) or 0.0))
                h = max(0.0, float(getattr(r, "h_m", 0.0) or 0.0))
                k = 2.0 if str(thickness_mode) == "full" else 1.0
                w_in = max(0.0, w - k * WALL_THICKNESS_OUTER_M)
                h_in = max(0.0, h - k * WALL_THICKNESS_OUTER_M)
                A_fb = (w_in * h_in) * float(area_shrink_factor)
                if A_in is None:
                    A_in = A_fb
                if V_in is None:
                    hh = max(0.0, float(getattr(r, "height_m", 0.0) or 0.0))
                    V_in = A_fb * hh
            except Exception:
                if A_in is None:
                    A_in = 0.0
                if V_in is None:
                    V_in = 0.0

        by_floor_A[fl] = by_floor_A.get(fl, 0.0) + float(A_in)
        by_floor_V[fl] = by_floor_V.get(fl, 0.0) + float(V_in)

        by_room.append({
            "room_id": str(getattr(r, "id", "")),
            "room": str(getattr(r, "name", "")),
            "floor": fl,
            "A_in_m2": float(A_in),
            "V_in_m3": float(V_in),
        })

    def _floor_key(f: str):
        f = (f or "").upper().strip()
        pri = {"KG": 0, "UG": 0, "EG": 1, "OG": 2, "1.OG": 2, "2.OG": 3, "3.OG": 4, "DG": 9, "OBEN": 10}
        return (pri.get(f, 50), f)

    floors_sorted = [fl for fl, _ in sorted(by_floor_A.items(), key=lambda kv: _floor_key(kv[0]))]
    rows = [{"floor": fl, "A_m2": float(by_floor_A.get(fl, 0.0)), "V_m3": float(by_floor_V.get(fl, 0.0))} for fl in floors_sorted]

    return {
        "by_floor": rows,
        "total_m2": float(sum(by_floor_A.values())),
        "total_m3": float(sum(by_floor_V.values())),
        "by_room": by_room,
        "meta": {"thickness_mode": str(thickness_mode), "area_shrink_factor": float(area_shrink_factor)},
    }


def render_floor_living_area_plot_png(
    summary: Dict[str, object],
    png_path: str,
    *,
    title: str = "Wohnfläche & Volumen je Geschoss",
) -> Optional[str]:
    """Erzeugt ein Balkendiagramm (PNG) aus summary['by_floor']."""
    if _plt is None:
        return None
    try:
        rows = (summary or {}).get("by_floor", []) or []
        floors = [str(r.get("floor", "")) for r in rows]
        A = [float(r.get("A_m2", 0.0) or 0.0) for r in rows]
        V = [float(r.get("V_m3", 0.0) or 0.0) for r in rows]
        if not floors:
            return None

        os.makedirs(os.path.dirname(png_path) or ".", exist_ok=True)

        fig = _plt.figure(figsize=(6.4, 3.0), dpi=160)
        ax1 = fig.add_subplot(111)

        import numpy as _np

        x = _np.arange(len(floors), dtype=float)

        has_V = any(abs(v) > 1e-12 for v in V)
        if has_V:
            w = 0.38
            ax1.bar(x - w / 2, A, width=w, label="Wohnfläche [m²]")
            ax2 = ax1.twinx()
            ax2.bar(x + w / 2, V, width=w, label="Volumen [m³]")

            ax1.set_ylabel("m²")
            ax2.set_ylabel("m³")

            for i, v in enumerate(A):
                ax1.text(x[i] - w / 2, v, f"{v:.1f}", ha="center", va="bottom", fontsize=8)
            for i, v in enumerate(V):
                ax2.text(x[i] + w / 2, v, f"{v:.1f}", ha="center", va="bottom", fontsize=8)

            h1, l1 = ax1.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)
        else:
            ax1.bar(x, A)
            ax1.set_ylabel("m²")
            for i, v in enumerate(A):
                ax1.text(x[i], v, f"{v:.1f}", ha="center", va="bottom", fontsize=8)

        ax1.set_xticks(x)
        ax1.set_xticklabels(floors)
        ax1.set_title(title)
        ax1.grid(True, axis="y", linestyle=":", linewidth=0.5)

        fig.tight_layout()
        fig.savefig(png_path)
        _plt.close(fig)
        return png_path
    except Exception:
        try:
            _plt.close("all")
        except Exception:
            pass
        return None
