from __future__ import annotations

from xml.sax.saxutils import escape

from ..core.attic_geometry import AtticGeometry


class AtticSvgRenderer:
    def __init__(self, width_px: int = 1000, height_px: int = 640, margin_px: int = 48):
        self.width_px = int(width_px)
        self.height_px = int(height_px)
        self.margin_px = int(margin_px)

    def render(self, geom: AtticGeometry, title: str = "Dachgeschoss – Dach + Giebel") -> str:
        w = self.width_px
        h = self.height_px
        m = self.margin_px
        panel_w = 260
        draw_w = w - 2 * m - panel_w
        draw_h = h - 2 * m
        sx = draw_w / max(geom.cross_span_m, 1e-9)
        sy = draw_h / max(geom.total_height_m, 1e-9)
        s = min(sx, sy)
        base_x = m + (draw_w - geom.cross_span_m * s) / 2.0
        base_y = h - m

        def px_x(x_m: float) -> float:
            return base_x + x_m * s

        def px_y(y_m: float) -> float:
            return base_y - y_m * s

        left = 0.0
        right = geom.cross_span_m
        knee = geom.knee_wall_height_m
        ridge_y = geom.total_height_m

        pts = [(px_x(x), px_y(y)) for x, y in geom.cross_section_points()]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

        def dim_vertical(x: float, y0: float, y1: float, label: str) -> str:
            mid = (y0 + y1) / 2.0
            return f"""
            <line x1=\"{x:.1f}\" y1=\"{y0:.1f}\" x2=\"{x:.1f}\" y2=\"{y1:.1f}\" class=\"dim\" />
            <line x1=\"{x-8:.1f}\" y1=\"{y0:.1f}\" x2=\"{x+8:.1f}\" y2=\"{y0:.1f}\" class=\"dim\" />
            <line x1=\"{x-8:.1f}\" y1=\"{y1:.1f}\" x2=\"{x+8:.1f}\" y2=\"{y1:.1f}\" class=\"dim\" />
            <text x=\"{x+12:.1f}\" y=\"{mid:.1f}\" class=\"label\">{escape(label)}</text>
            """

        def dim_horizontal(x0: float, x1: float, y: float, label: str) -> str:
            mid = (x0 + x1) / 2.0
            return f"""
            <line x1=\"{x0:.1f}\" y1=\"{y:.1f}\" x2=\"{x1:.1f}\" y2=\"{y:.1f}\" class=\"dim\" />
            <line x1=\"{x0:.1f}\" y1=\"{y-8:.1f}\" x2=\"{x0:.1f}\" y2=\"{y+8:.1f}\" class=\"dim\" />
            <line x1=\"{x1:.1f}\" y1=\"{y-8:.1f}\" x2=\"{x1:.1f}\" y2=\"{y+8:.1f}\" class=\"dim\" />
            <text x=\"{mid:.1f}\" y=\"{y-10:.1f}\" text-anchor=\"middle\" class=\"label\">{escape(label)}</text>
            """

        guides = []
        for hh, cls, label in ((1.0, "guide1", "1.0 m"), (2.0, "guide2", "2.0 m")):
            if hh >= geom.total_height_m:
                continue
            xoff = geom.slope_offset_x_m(hh)
            x0 = px_x(xoff)
            x1 = px_x(geom.cross_span_m - xoff)
            y = px_y(hh)
            guides.append(
                f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" class="{cls}" />'
                f'<text x="{x1+8:.1f}" y="{y+4:.1f}" class="small">{label}</text>'
            )

        note_x = w - m - panel_w + 18
        note_y = m + 24
        rows = [
            ("Breite B", f"{geom.building_width_m:.2f} m"),
            ("Länge L", f"{geom.building_length_m:.2f} m"),
            ("Kniestock", f"{geom.knee_wall_height_m:.2f} m"),
            ("Dachneigung", f"{geom.roof_pitch_deg:.1f} °"),
            ("Firstrichtung", "quer" if str(getattr(geom, "ridge_orientation", "length") or "length").strip().lower() == "width" else "längs"),
            ("Dachüberstand", f"{float(getattr(geom, "roof_overhang_m", 0.0) or 0.0):.2f} m"),
            ("Firsthöhe", f"{geom.total_height_m:.2f} m"),
            ("Dachfläche", f"{geom.roof_area_total_m2:.2f} m²"),
            ("Giebel je Stirnseite", f"{geom.gable_area_total_m2:.2f} m²"),
            ("Gew. DG-Fläche", f"{geom.weighted_floor_area_m2():.2f} m²"),
        ]
        body_rows = "".join(
            f'<text x="{note_x}" y="{note_y + 34 + i * 24}" class="small">{escape(k)}: {escape(v)}</text>'
            for i, (k, v) in enumerate(rows)
        )

        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <style>
      .outline {{ fill: #fff9f1; stroke: #1f2937; stroke-width: 2.0; }}
      .roof {{ stroke: #b45309; stroke-width: 3.0; fill: none; }}
      .wall {{ stroke: #2563eb; stroke-width: 3.0; fill: none; }}
      .base {{ stroke: #111827; stroke-width: 2.5; fill: none; }}
      .dim {{ stroke: #6b7280; stroke-width: 1.4; fill: none; }}
      .guide1 {{ stroke: #9ca3af; stroke-width: 1.2; stroke-dasharray: 7 5; }}
      .guide2 {{ stroke: #6b7280; stroke-width: 1.2; stroke-dasharray: 4 4; }}
      .title {{ font: 700 22px DejaVu Sans, Arial, sans-serif; fill: #111827; }}
      .label {{ font: 14px DejaVu Sans, Arial, sans-serif; fill: #111827; }}
      .small {{ font: 13px DejaVu Sans, Arial, sans-serif; fill: #374151; }}
      .panel {{ fill: #f9fafb; stroke: #d1d5db; stroke-width: 1.2; rx: 14; }}
    </style>
  </defs>
  <rect x="0" y="0" width="{w}" height="{h}" fill="#ffffff"/>
  <text x="{m}" y="{m-12}" class="title">{escape(title)}</text>
  <polygon points="{poly}" class="outline"/>
  <line x1="{pts[0][0]:.1f}" y1="{pts[0][1]:.1f}" x2="{pts[1][0]:.1f}" y2="{pts[1][1]:.1f}" class="wall"/>
  <line x1="{pts[-1][0]:.1f}" y1="{pts[-1][1]:.1f}" x2="{pts[-2][0]:.1f}" y2="{pts[-2][1]:.1f}" class="wall"/>
  {''.join(f'<polyline points="{a[0]:.1f},{a[1]:.1f} {b[0]:.1f},{b[1]:.1f}" class="roof"/>' for a, b in zip(pts[1:-1], pts[2:]))}
  <line x1="{px_x(left):.1f}" y1="{px_y(0.0):.1f}" x2="{px_x(right):.1f}" y2="{px_y(0.0):.1f}" class="base"/>
  {''.join(guides)}
  {dim_horizontal(px_x(left), px_x(right), px_y(0.0) + 34, f'Querschnitt = {geom.cross_span_m:.2f} m')}
  {dim_vertical(px_x(left) - 28, px_y(0.0), px_y(knee), f'Kniestock = {geom.knee_wall_height_m:.2f} m')}
  {dim_vertical(px_x(right) + 28, px_y(0.0), px_y(ridge_y), f'Firsthöhe = {geom.total_height_m:.2f} m')}
  <rect x="{w - m - panel_w}" y="{m}" width="{panel_w}" height="250" class="panel"/>
  <text x="{note_x}" y="{note_y}" class="label">Kennwerte</text>
  {body_rows}
</svg>
'''
