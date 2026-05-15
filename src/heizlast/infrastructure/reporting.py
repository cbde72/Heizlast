from __future__ import annotations

import os
import math
import csv
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple
from ..domain.models import ElementModel

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.collections import LineCollection

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, PageBreak, Image,
    BaseDocTemplate, Frame, PageTemplate
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

from ..domain.models import RoomModel
from ..core.config import (
    CSV_DELIMITER, HEATMAP_CAP_W_PER_M2, ELEMENT_STYLES,
    VentilationCfg, ProjectCfg, resolve_t_out_c
)
from ..core.heatload import _opening_area_on_wall_segment, OUTER_WALL_TYPES, WINDOW_TYPES


# ============================================================
# Config: steuert Inhalt + Layout des Reports (einfach erweiterbar)
# ============================================================

@dataclass
class ReportPDFLayoutCfg:
    # Page / margins
    pagesize: tuple = A4
    left_margin_mm: float = 18.0
    right_margin_mm: float = 18.0
    top_margin_mm: float = 14.0
    bottom_margin_mm: float = 14.0

    # Fonts
    font_regular: str = "Helvetica"
    font_bold: str = "Helvetica-Bold"
    font_size_body: int = 9
    font_size_small: int = 7
    font_size_h1: int = 14
    font_size_h2: int = 11
    leading_body: int = 11
    leading_small: int = 10

    # Tables
    table_header_font_size: int = 8
    table_body_font_size: int = 6
    table_grid_width: float = 0.25
    table_header_bg = colors.lightgrey
    table_row_bg = (colors.whitesmoke, colors.white)

    # Element / equation tables (col widths)
    colw_type_table_mm: List[float] = field(default_factory=lambda: [60, 28, 24, 24, 22, 16])
    colw_eq_table_mm: List[float] = field(default_factory=lambda: [10, 35, 35, 85, 18])
    colw_deck_detail_mm: List[float] = field(default_factory=lambda: [26, 14, 12, 24, 12, 16, 10, 6, 16, 40])

    # Envelope tables
    colw_env_sum_mm: List[float] = field(default_factory=lambda: [25, 25, 25, 25, 25, 25])
    colw_env_det_mm: List[float] = field(default_factory=lambda: [20, 20, 32, 28, 20, 20, 20])


@dataclass
class ReportContentCfg:
    # High level toggles
    include_room_pages: bool = True
    include_room_type_table: bool = True
    include_calc_proof_lines: bool = True

    include_total_page: bool = True
    include_room_power_table_at_end: bool = True

    # Zusatz: Wohnfläche je Geschoss (aus heatload.py -> results["floor_area"])
    include_floor_area_section: bool = True

    include_decks_section: bool = True
    include_envelope_section: bool = True

    include_annexes: bool = True
    include_din_matrix: bool = True
    include_factor_table: bool = True
    include_model_text: bool = True

    # Extended sections (refactored extensible blocks)
    include_thermal_bridge_block: bool = False
    include_ventilation_parameters_block: bool = False
    include_interzone_matrix: bool = False
    include_floorplan_heatmap: bool = False

    # Extended section limits / options
    max_tb_rows_per_room: int = 50
    max_interzone_rows: Optional[int] = 400

    # Heatmap options (only used if include_floorplan_heatmap=True)
    heatmap_cap_w_per_m2: float = HEATMAP_CAP_W_PER_M2
    heatmap_export_dpi: int = 260
    heatmap_max_width_mm: float = 190.0
    heatmap_max_height_mm: float = 260.0
    heatmap_include_elements: bool = True


    # Limits
    max_envelope_notes: int = 6
    # If details are huge, you can cap the number of rows
    max_envelope_details_rows: Optional[int] = None


@dataclass
class ReportPDFCfg:
    content: ReportContentCfg = field(default_factory=ReportContentCfg)
    layout: ReportPDFLayoutCfg = field(default_factory=ReportPDFLayoutCfg)

    # Formatting / labeling preferences
    title: str = "Heizlast-Report"
    show_inner_dims: bool = True
    show_transmission_split: bool = True

    # Table wrapping control (columns indices)
    wrap_cols_type_table: set[int] = field(default_factory=lambda: {0})
    wrap_cols_eq_table: set[int] = field(default_factory=lambda: {1, 2, 3})
    wrap_cols_env_tables: set[int] = field(default_factory=lambda: {0, 1, 2, 3})


# ============================================================
# Static Annex content (keep as constants for maintainability)
# ============================================================

ANNEX_MODEL_TEXT = (
    "Anhang A – Rechenmodell & Annahmen (DIN-ähnlich)<br/><br/>"
    "<b>A.1 Heizlastdefinition</b><br/>"
    "Φ_gesamt = Φ_trans + Φ_vent<br/><br/>"
    "<b>A.2 Transmissionswärmeverluste</b><br/>"
    "Φ_trans = Σ ( U · A_eff · ΔT · f )<br/>"
    "mit A_eff = A_Bauteil − A_Öffnungen (z.B. Fenster).<br/><br/>"
    "<b>A.3 Lüftungswärmeverluste</b><br/>"
    "Φ_vent = c_air · n · V · (T_in − T_out)<br/><br/>"
    "<b>A.4 Wärmebrücken</b><br/>"
    "Φ_WB optional als Zuschlag (ΔU, ψ oder %).<br/><br/>"
    "<b>A.5 Spezifische Heizlast</b><br/>"
    "q = Φ_gesamt / A_ref<br/><br/>"
    "<b>A.6 Annahmen</b><br/>"
    "stationär, keine Speicherwirkung, keine Gewinne."
)

ANNEX_DIN_CONFORMITY_ROWS = [
    ["Normbaustein", "DIN-Anforderung (Kurz)", "Tool-Umsetzung", "Konformität"],
    ["Raumweise Heizlast", "Φ_HL,Raum", "raumweise Q_sum_W", "✓"],
    ["Transmission", "Σ(U·A·ΔT·f)", "implementiert", "✓"],
    ["Öffnungsabzug", "A_eff = A_Wand − A_Fenster", "geometrisch", "✓"],
    ["Innen-/Außenmaß", "normativ definierte Maße", "Umschaltung A_trans", "△"],
    ["Lüftung", "Norm-Lüftungswärmeverlust", "n·V·ΔT (sensibel)", "△"],
    ["Mechanische Lüftung", "Volumenströme, WRG", "nicht implementiert", "✗"],
    ["Wärmebrücken", "ψ-Werte / Zuschläge", "optional via tb_cfg (ΔU/ψ/%), separat im Report", "△"],
    ["Erdreich/Boden", "Normverfahren", "vereinfachtes Erdreichmodell (Bodenplatte/Kellerwand, optional perimeter)", "△"],
    ["Aufheizzuschlag", "Φ_hu", "nicht implementiert", "✗"],
    ["Gewinne", "interne/solare Gewinne", "nicht berücksichtigt", "✗"],
]


# ============================================================
# Helpers
# ============================================================

def register_fonts(font_dir: str = "assets/fonts") -> None:
    """Registers DejaVu fonts when available; otherwise falls back silently."""
    try:
        from ..paths import fonts_dir
        cand_dirs = [font_dir, str(fonts_dir())]
    except Exception:
        cand_dirs = [font_dir]

    for d in cand_dirs:
        try:
            reg = os.path.join(d, "DejaVuSans.ttf")
            bold = os.path.join(d, "DejaVuSans-Bold.ttf")
            ita = os.path.join(d, "DejaVuSans-Oblique.ttf")
            boldita = os.path.join(d, "DejaVuSans-BoldOblique.ttf")
            if all(os.path.exists(p) for p in [reg, bold, ita, boldita]):
                pdfmetrics.registerFont(TTFont("DejaVu", reg))
                pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
                pdfmetrics.registerFont(TTFont("DejaVu-Italic", ita))
                pdfmetrics.registerFont(TTFont("DejaVu-BoldItalic", boldita))
                return
        except Exception:
            pass
    return
def _safe_first_result(results: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    for _k, v in (results or {}).items():
        if isinstance(v, dict):
            return v
    return {}


def _meta_get_float(meta: str | None, key: str) -> Optional[float]:
    if not meta:
        return None
    parts = [p.strip() for p in meta.split("|") if "=" in p]
    for p in parts:
        k, v = p.split("=", 1)
        if k.strip() == key:
            try:
                return float(str(v).replace(",", "."))
            except Exception:
                return None
    return None


def _meta_get_str(meta: str | None, key: str) -> Optional[str]:
    if not meta:
        return None
    parts = [p.strip() for p in meta.split("|") if "=" in p]
    for p in parts:
        k, v = p.split("=", 1)
        if k.strip() == key:
            return str(v).strip()
    return None

def _meta_items(meta: str | None) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not meta:
        return out
    for p in [p.strip() for p in meta.split("|") if "=" in p]:
        k, v = p.split("=", 1)
        out[k.strip()] = str(v).strip()
    return out


def _wrap_table_data(
    styles: dict,
    data: list,
    *,
    header_rows: int = 1,
    wrap_cols: Optional[Iterable[int]] = None,
    ps_head: ParagraphStyle,
    ps_body: ParagraphStyle
) -> list:
    """Wraps selected table cells by converting to Paragraphs."""
    out = []
    wrap_cols_set = set(wrap_cols) if wrap_cols is not None else None
    for r_idx, row in enumerate(data):
        new_row = []
        for c_idx, val in enumerate(row):
            do_wrap = (wrap_cols_set is None) or (c_idx in wrap_cols_set) or (r_idx < header_rows)
            if do_wrap:
                st = ps_head if r_idx < header_rows else ps_body
                new_row.append(Paragraph(str(val), st))
            else:
                new_row.append(val)
        out.append(new_row)
    return out


class OutlineTOCDocTemplate(BaseDocTemplate):
    """
    DocTemplate with:
      - Acrobat outline/bookmarks from Heading1/Heading2
      - TableOfContents population via afterFlowable
    """

    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates([PageTemplate(id="main", frames=[frame])])
        self._outline_seq = 0

    def afterFlowable(self, flowable):
        style_name = getattr(getattr(flowable, "style", None), "name", "")
        if style_name not in ("Heading1", "Heading2"):
            return

        level = 0 if style_name == "Heading1" else 1
        try:
            title = flowable.getPlainText()
        except Exception:
            title = style_name

        self._outline_seq += 1
        key = f"bm_{self._outline_seq:05d}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title, key, level=level, closed=False)
        self.notify("TOCEntry", (level, title, self.page))


# ============================================================
# PDF Report Builder (refactored)
# ============================================================

class HeatloadPDFReport:
    """
    Central builder for PDF report. Extend by adding new _append_* sections.
    """

    def __init__(
        self,
        *,
        path: str,
        rooms: List[RoomModel],
        elements: List[ElementModel],
        results: Dict[str, Dict[str, float]],
        t_out_c: float,
        project_cfg: ProjectCfg | None = None,
        vent_cfg: VentilationCfg = VentilationCfg(),
        cfg: ReportPDFCfg = ReportPDFCfg(),
        font_dir: str = "assets/fonts",
    ) -> None:
        self.path = path
        self.rooms = rooms
        self.elements = elements
        self.results = results
        self.project_cfg = project_cfg
        self.vent_cfg = vent_cfg
        self.cfg = cfg

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        register_fonts(font_dir=font_dir)

        # Resolve T_out
        self.t_out_c, self.t_out_src = resolve_t_out_c(t_out_c=t_out_c, project=project_cfg)
        self.t_out_c = float(self.t_out_c)

        # styles
        self.styles = self._build_styles()

        # document
        L = self.cfg.layout
        self.doc = OutlineTOCDocTemplate(
            path,
            pagesize=L.pagesize,
            leftMargin=L.left_margin_mm * mm,
            rightMargin=L.right_margin_mm * mm,
            topMargin=L.top_margin_mm * mm,
            bottomMargin=L.bottom_margin_mm * mm,
            title=self.cfg.title,
        )

        # group elements by room (for quick lookup)
        self.e_by_room: Dict[str, List[ElementModel]] = {}
        for e in elements:
            self.e_by_room.setdefault(e.room_id, []).append(e)

        # totals
        self.totals_by_type: Dict[str, Dict[str, float]] = {}
        self.total_Q_sum: float = 0.0

        # story
        self.story: list = []

    # --------------------
    # Styles & formatting
    # --------------------
    def _build_styles(self) -> dict:
        L = self.cfg.layout
        styles = getSampleStyleSheet()

        # base
        styles["Normal"].fontName = L.font_regular
        styles["Normal"].fontSize = L.font_size_body
        styles["Normal"].leading = L.leading_body

        # headings
        h1 = ParagraphStyle(
            "Heading1",
            parent=styles["Normal"],
            fontName=L.font_bold,
            fontSize=L.font_size_h1,
            leading=L.font_size_h1 + 2,
            spaceAfter=4,
        )
        h2 = ParagraphStyle(
            "Heading2",
            parent=styles["Normal"],
            fontName=L.font_bold,
            fontSize=L.font_size_h2,
            leading=L.font_size_h2 + 2,
            spaceAfter=2,
        )

        body = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontName=L.font_regular,
            fontSize=L.font_size_body,
            leading=L.leading_body,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )
        small = ParagraphStyle(
            "Small",
            parent=styles["Normal"],
            fontName=L.font_regular,
            fontSize=L.font_size_small,
            leading=L.leading_small,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )
        head_cell = ParagraphStyle(
            "TableHead",
            parent=styles["Normal"],
            fontName=L.font_bold,
            fontSize=L.table_header_font_size,
            leading=L.table_header_font_size + 2,
            wordWrap="CJK",
        )
        body_cell = ParagraphStyle(
            "TableBody",
            parent=styles["Normal"],
            fontName=L.font_regular,
            fontSize=max(6, L.table_body_font_size),
            leading=max(8, L.table_body_font_size + 2),
            wordWrap="CJK",
        )

        return {"h1": h1, "h2": h2, "body": body, "small": small, "th": head_cell, "tb": body_cell}

    def fmt(self, x: float, nd: int = 2) -> str:
        try:
            return f"{float(x):.{nd}f}".replace(".", ",")
        except Exception:
            return "—"
    def wrap_table(self, data: list, *, header_rows: int = 1, wrap_cols: Optional[Iterable[int]] = None) -> list:
        """Convenience wrapper for _wrap_table_data using this report's paragraph styles."""
        return _wrap_table_data(
            self.styles,
            data,
            header_rows=header_rows,
            wrap_cols=wrap_cols,
            ps_head=self.styles["th"],
            ps_body=self.styles["tb"],
        )

    def table_style(self, *, header_font: int = 8, body_font: int = 6) -> TableStyle:
        """Default table style consistent with ReportPDFLayoutCfg."""
        L = self.cfg.layout
        return TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), L.font_bold),
            ("FONTSIZE", (0, 0), (-1, 0), header_font),
            ("FONTSIZE", (0, 1), (-1, -1), body_font),
            ("BACKGROUND", (0, 0), (-1, 0), L.table_header_bg),
            ("GRID", (0, 0), (-1, -1), L.table_grid_width, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])


    # --------------------
    # Summary helpers
    # --------------------
    @staticmethod
    def _is_basement_floor(floor: str) -> bool:
        f = str(floor or "").strip().upper()
        return f in {"KG", "UG", "KELLER"}

    @staticmethod
    def _floor_sort_key(floor: str) -> Tuple[int, str]:
        f = str(floor or "").strip().upper()
        pri = {"KG": 0, "UG": 0, "KELLER": 0, "EG": 1, "OG": 2, "1.OG": 2, "2.OG": 3, "3.OG": 4, "DG": 9, "OBEN": 10}
        return (pri.get(f, 50), f)

    def _collect_summary_metrics(self) -> Dict[str, Any]:
        area_by_floor: Dict[str, float] = {}
        vol_by_floor: Dict[str, float] = {}
        q_by_floor: Dict[str, float] = {}

        fa = self.results.get("floor_area") if isinstance(self.results, dict) else None
        if isinstance(fa, dict) and fa.get("by_floor"):
            for row in fa.get("by_floor", []) or []:
                fl = str(row.get("floor", "") or "").strip().upper() or "?"
                area_by_floor[fl] = area_by_floor.get(fl, 0.0) + float(row.get("A_m2", 0.0) or 0.0)

        for r in self.rooms:
            fl = str(getattr(r, "floor", "") or "").strip().upper() or "?"
            rr = self.results.get(r.id, {}) or {}

            if fl not in area_by_floor:
                area_by_floor[fl] = area_by_floor.get(fl, 0.0) + float(rr.get("A_in_m2", 0.0) or 0.0)

            vol_by_floor[fl] = vol_by_floor.get(fl, 0.0) + float(rr.get("V_in_m3", 0.0) or 0.0)
            q_by_floor[fl] = q_by_floor.get(fl, 0.0) + float(rr.get("Q_sum_W", 0.0) or 0.0)

        total_area_wo_keller = sum(v for f, v in area_by_floor.items() if not self._is_basement_floor(f))
        keller_area = sum(v for f, v in area_by_floor.items() if self._is_basement_floor(f))
        total_vol = sum(vol_by_floor.values())
        vol_wo_keller = sum(v for f, v in vol_by_floor.items() if not self._is_basement_floor(f))

        first = _safe_first_result(self.results)
        selected_models = {
            "Transmissionsmaß": str(first.get("floor_area_mode", "—") if isinstance(first, dict) else "—"),
            "Wandabzug": str(first.get("thickness_mode", "—") if isinstance(first, dict) else "—"),
            "Flächenfaktor shrink": self.fmt(first.get("area_shrink_factor", 0.0), 3) if isinstance(first, dict) and first.get("area_shrink_factor") is not None else "—",
            "Wärmebrückenmodell": str(getattr(getattr(self.project_cfg, "tb", None), "mode", "—") or "—"),
            "Lüftungsmodell": "c_air · n · V · ΔT",
            "Transmissionsmodell": "DIN EN 12831 (e/u/j, stationär)",
        }

        design_temps = [
            ("Auslegung außen", f"{self.fmt(self.t_out_c,1)} °C"),
            ("Keller", f"{self.fmt(float(first.get('t_keller_c', 14.0) if isinstance(first, dict) else 14.0),1)} °C"),
            ("Oben / Dachraum", f"{self.fmt(float(first.get('t_oben_c', 12.0) if isinstance(first, dict) else 12.0),1)} °C"),
            ("T_out Quelle", str(self.t_out_src or "—")),
        ]

        return {
            "area_by_floor": dict(sorted(area_by_floor.items(), key=lambda kv: self._floor_sort_key(kv[0]))),
            "vol_by_floor": dict(sorted(vol_by_floor.items(), key=lambda kv: self._floor_sort_key(kv[0]))),
            "q_by_floor": dict(sorted(q_by_floor.items(), key=lambda kv: self._floor_sort_key(kv[0]))),
            "total_area_wo_keller": total_area_wo_keller,
            "keller_area": keller_area,
            "total_vol": total_vol,
            "vol_wo_keller": vol_wo_keller,
            "total_q": sum(q_by_floor.values()),
            "selected_models": selected_models,
            "design_temps": design_temps,
        }

    def _append_summary_page(self) -> None:
        s = self._collect_summary_metrics()

        self.story.append(Paragraph("Zusammenfassung", self.styles["h1"]))
        self.story.append(Spacer(1, 6))

        # Fläche
        self.story.append(Paragraph("Flächen", self.styles["h2"]))
        area_tbl = [["Kennwert", "Wert"]]
        area_tbl.append(["Gesamtfläche ohne Keller [m²]", self.fmt(s["total_area_wo_keller"], 1)])
        area_tbl.append(["Kellerfläche [m²]", self.fmt(s["keller_area"], 1)])
        for fl, val in s["area_by_floor"].items():
            area_tbl.append([f"Fläche {fl} [m²]", self.fmt(val, 1)])
        t1 = Table(self.wrap_table(area_tbl, header_rows=1, wrap_cols={0}), colWidths=[95*mm, 35*mm], hAlign="LEFT")
        t1.setStyle(self.table_style(header_font=8, body_font=7))
        self.story.append(t1)
        self.story.append(Spacer(1, 8))

        # Volumen
        self.story.append(Paragraph("Raumvolumen", self.styles["h2"]))
        vol_tbl = [["Kennwert", "Wert"]]
        vol_tbl.append(["Raumvolumen gesamt [m³]", self.fmt(s["total_vol"], 1)])
        vol_tbl.append(["Raumvolumen ohne Keller [m³]", self.fmt(s["vol_wo_keller"], 1)])
        for fl in ["EG", "DG"]:
            vol_tbl.append([f"Raumvolumen {fl} [m³]", self.fmt(s["vol_by_floor"].get(fl, 0.0), 1)])
        for fl, val in s["vol_by_floor"].items():
            if fl not in {"EG", "DG"}:
                vol_tbl.append([f"Raumvolumen {fl} [m³]", self.fmt(val, 1)])
        t2 = Table(self.wrap_table(vol_tbl, header_rows=1, wrap_cols={0}), colWidths=[95*mm, 35*mm], hAlign="LEFT")
        t2.setStyle(self.table_style(header_font=8, body_font=7))
        self.story.append(t2)
        self.story.append(Spacer(1, 8))

        # Heizleistung
        self.story.append(Paragraph("Heizleistung", self.styles["h2"]))
        q_tbl = [["Kennwert", "Wert"]]
        q_tbl.append(["Heizleistung gesamt [W]", self.fmt(s["total_q"], 1)])
        for fl, val in s["q_by_floor"].items():
            q_tbl.append([f"Heizleistung {fl} [W]", self.fmt(val, 1)])
        t3 = Table(self.wrap_table(q_tbl, header_rows=1, wrap_cols={0}), colWidths=[95*mm, 35*mm], hAlign="LEFT")
        t3.setStyle(self.table_style(header_font=8, body_font=7))
        self.story.append(t3)
        self.story.append(Spacer(1, 8))

        # Temperaturen / Modelle
        self.story.append(Paragraph("Auslegungstemperaturen & gewählte Modelle", self.styles["h2"]))
        model_rows = [["Parameter", "Wert"]]
        model_rows.extend([[k, v] for k, v in s["design_temps"]])
        for k, v in s["selected_models"].items():
            model_rows.append([k, v])
        t4 = Table(self.wrap_table(model_rows, header_rows=1, wrap_cols={0,1}), colWidths=[60*mm, 70*mm], hAlign="LEFT")
        t4.setStyle(self.table_style(header_font=8, body_font=7))
        self.story.append(t4)
        self.story.append(PageBreak())

    # --------------------
    # Build orchestration
    # --------------------
    def build(self) -> None:
        self._append_title_page()
        self._append_toc_page()
        self._append_summary_page()

        if self.cfg.content.include_room_pages:
            for r in self.rooms:
                self._append_room_page(r)
                self.story.append(PageBreak())

        if self.cfg.content.include_total_page:
            self._append_total_page()

        if self.cfg.content.include_room_power_table_at_end:
            self._append_room_power_table()

        if self.cfg.content.include_floor_area_section:
            self._append_floor_area_section()

        if self.cfg.content.include_thermal_bridge_block:
            self._append_thermal_bridge_block()

        if self.cfg.content.include_ventilation_parameters_block:
            self._append_ventilation_parameters_block()

        if self.cfg.content.include_interzone_matrix:
            self._append_interzone_matrix()

        if self.cfg.content.include_floorplan_heatmap:
            self._append_floorplan_heatmaps()

        if self.cfg.content.include_decks_section:
            self._append_decks_section()

        if self.cfg.content.include_envelope_section:
            self._append_envelope_section()

        if self.cfg.content.include_annexes:
            self._append_annexes()

        self.doc.multiBuild(self.story)

    # --------------------
    # Sections
    # --------------------
    def _append_title_page(self) -> None:
        self.story.append(Paragraph(self.cfg.title, self.styles["h1"]))
        self.story.append(Paragraph(f"Außentemperatur: {self.fmt(self.t_out_c, 1)} °C", self.styles["body"]))
        self.story.append(Spacer(1, 10))

    def _append_toc_page(self) -> None:
        """Acrobat-style TOC page on page 2."""
        self.story.append(PageBreak())
        self.story.append(Paragraph("Inhaltsverzeichnis", self.styles["h1"]))
        self.story.append(Spacer(1, 6))

        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle(
                name="TOCLevel1",
                parent=self.styles["body"],
                fontName=self.cfg.layout.font_bold,
                fontSize=max(9, self.cfg.layout.font_size_body),
                leading=max(11, self.cfg.layout.leading_body),
                leftIndent=0,
                firstLineIndent=0,
                spaceBefore=2,
            ),
            ParagraphStyle(
                name="TOCLevel2",
                parent=self.styles["body"],
                fontName=self.cfg.layout.font_regular,
                fontSize=max(8, self.cfg.layout.font_size_body - 1),
                leading=max(10, self.cfg.layout.leading_body - 1),
                leftIndent=12,
                firstLineIndent=0,
                spaceBefore=1,
            ),
        ]
        self.story.append(toc)
        self.story.append(PageBreak())

    def _append_room_page(self, r: RoomModel) -> None:
        rr = self.results.get(r.id, {}) or {}
        dT = max(0.0, float(r.t_inside_c or 0.0) - float(self.t_out_c))

        self.story.append(Paragraph(f"{r.name} ({r.floor})", self.styles["h2"]))

        # Key info (prefer results if provided)
        A_in = float(rr.get("A_in_m2", 0.0) or 0.0)
        V_in = float(rr.get("V_in_m3", 0.0) or 0.0)
        self.story.append(Paragraph(
            f"A_in={self.fmt(A_in,2)} m², V_in={self.fmt(V_in,2)} m³, "
            f"n={self.fmt(float(r.air_change_1ph or 0.0),2)} 1/h, "
            f"T_in={self.fmt(float(r.t_inside_c or 0.0),1)} °C, ΔT={self.fmt(dT,1)} K",
            self.styles["body"]
        ))

        if self.cfg.show_inner_dims:
            self._append_room_inner_dims(rr)

        q_trans = float(rr.get("Q_trans_W", 0.0) or 0.0)
        q_vent = float(rr.get("Q_vent_W", 0.0) or 0.0)
        q_sum = float(rr.get("Q_sum_W", 0.0) or 0.0)
        wpm2 = float(rr.get("Q_W_per_m2", 0.0) or 0.0)
        wpm2_in = (q_sum / A_in) if A_in > 1e-9 else 0.0

        a_open = float(rr.get("A_openings_m2", 0.0) or 0.0)
        a_outer_eff = float(rr.get("A_outer_eff_m2", 0.0) or 0.0)

        self.story.append(Paragraph(
            f"<b>Q_trans</b>={self.fmt(q_trans,1)} W, <b>Q_ground</b>={self.fmt(float(rr.get('Q_trans_ground_W',0.0) or 0.0),1)} W, <b>Q_vent</b>={self.fmt(q_vent,1)} W, "
            f"<b>Q_sum</b>={self.fmt(q_sum,1)} W ({self.fmt(wpm2,1)} W/m² außen / {self.fmt(wpm2_in,1)} W/m² innen) | "
            f"Fensterabzug Außenwand: {self.fmt(a_open,2)} m²; eff. Außenwand: {self.fmt(a_outer_eff,2)} m²",
            self.styles["body"]
        ))

        if self.cfg.show_transmission_split:
            self._append_transmission_split(rr)

        if self.cfg.content.include_room_type_table:
            self._append_room_type_table(r, rr)

        if self.cfg.content.include_calc_proof_lines:
            self._append_calc_proof(rr)

        # update totals (for total page)
        self.total_Q_sum += q_sum
        self._update_totals_by_type(rr)

    def _append_room_inner_dims(self, rr: dict) -> None:
        w_in = float(rr.get("w_in_m", 0.0) or 0.0)
        h_in = float(rr.get("h_in_m", 0.0) or 0.0)
        tL = float(rr.get("t_left_m", 0.0) or 0.0)
        tR = float(rr.get("t_right_m", 0.0) or 0.0)
        tT = float(rr.get("t_top_m", 0.0) or 0.0)
        tB = float(rr.get("t_bottom_m", 0.0) or 0.0)
        self.story.append(Paragraph(
            f"Innenmaße: w_in={self.fmt(w_in,3)} m, h_in={self.fmt(h_in,3)} m; "
            f"t_L={self.fmt(tL*1000.0,1)} mm, t_R={self.fmt(tR*1000.0,1)} mm, "
            f"t_O={self.fmt(tT*1000.0,1)} mm, t_U={self.fmt(tB*1000.0,1)} mm",
            self.styles["small"]
        ))

    def _append_transmission_split(self, rr: dict) -> None:
        q_out = float(rr.get("Q_trans_out_W", 0.0) or 0.0)
        q_kel = float(rr.get("Q_trans_keller_W", 0.0) or 0.0)
        q_inter = float(rr.get("Q_trans_interzone_W", 0.0) or 0.0)
        q_dach = float(rr.get("Q_trans_dachraum_W", 0.0) or 0.0)
        t_k = float(rr.get("t_keller_c", 14.0) or 14.0)
        t_o = float(rr.get("t_oben_c", 12.0) or 12.0)

        self.story.append(Paragraph(
            f"<b>Transmission-Aufteilung</b>: "
            f"Außen Q_out={self.fmt(q_out,1)} W; "
            f"Kellerdecke (T_keller={self.fmt(t_k,1)}°C) Q_keller={self.fmt(q_kel,1)} W; "
            f"Zwischendecke EG↔DG (Interzone) Q_interzone={self.fmt(q_inter,1)} W; "
            f"Decke zum Speicher/Dachraum (T_speicher={self.fmt(t_o,1)}°C) Q_dachraum={self.fmt(q_dach,1)} W",
            self.styles["small"]
        ))

    # ---- totals by type (prefer heatload precomputed)
    def _room_type_sums_from_rr(self, rr: dict) -> Dict[str, Dict[str, float]]:
        pre = rr.get("type_sums") if isinstance(rr, dict) else None
        if isinstance(pre, dict) and pre:
            out: Dict[str, Dict[str, float]] = {}
            for et, s in pre.items():
                if not isinstance(s, dict):
                    continue
                out[str(et)] = {
                    "A_eff": float(s.get("A_eff_m2", 0.0) or 0.0),
                    "Q": float(s.get("Q_W", 0.0) or 0.0),
                    "A_brutto": float(s.get("A_brutto_m2", 0.0) or 0.0),
                    "A_open": float(s.get("A_open_m2", 0.0) or 0.0),
                }
            return out

        # fallback: from lines
        sums: Dict[str, Dict[str, float]] = {}
        lines = rr.get("lines", []) if isinstance(rr, dict) else []
        if isinstance(lines, list):
            for ln in lines:
                if not isinstance(ln, dict):
                    continue
                lt = str(ln.get("line_type", "TRANSMISSION") or "TRANSMISSION").upper()
                if lt not in ("TRANSMISSION", "THERMAL_BRIDGE", "VENTILATION"):
                    continue
                et = str(ln.get("element_type", "") or "")
                sums.setdefault(et, {"A_eff": 0.0, "Q": 0.0, "A_brutto": 0.0, "A_open": 0.0})
                sums[et]["A_eff"] += float(ln.get("A_eff_m2", 0.0) or 0.0)
                sums[et]["Q"] += float(ln.get("Q_W", 0.0) or 0.0)
                sums[et]["A_brutto"] += float(ln.get("A_brutto_m2", 0.0) or 0.0)
                sums[et]["A_open"] += float(ln.get("A_open_m2", 0.0) or 0.0)
        return sums

    def _update_totals_by_type(self, rr: dict) -> None:
        sums = self._room_type_sums_from_rr(rr)
        for et, s in sums.items():
            self.totals_by_type.setdefault(et, {"A_eff": 0.0, "Q": 0.0, "A_brutto": 0.0, "A_open": 0.0})
            self.totals_by_type[et]["A_eff"] += float(s.get("A_eff", 0.0) or 0.0)
            self.totals_by_type[et]["A_brutto"] += float(s.get("A_brutto", 0.0) or 0.0)
            self.totals_by_type[et]["A_open"] += float(s.get("A_open", 0.0) or 0.0)
            self.totals_by_type[et]["Q"] += float(s.get("Q", 0.0) or 0.0)

    def _append_room_type_table(self, r: RoomModel, rr: dict) -> None:
        q_sum = float(rr.get("Q_sum_W", 0.0) or 0.0)
        sums = self._room_type_sums_from_rr(rr)

        self.story.append(Spacer(1, 6))
        self.story.append(Paragraph("Anteile beziehen sich auf Q_sum (Transmission + Lüftung).", self.styles["body"]))
        self.story.append(Spacer(1, 4))

        data = [["Bauteiltyp", "A_brutto [m²]", "A_open [m²]", "A_eff [m²]", "Q [W]", "Anteil [%]"]]

        def sort_key(et: str) -> int:
            if et in OUTER_WALL_TYPES:
                return 0
            if et in WINDOW_TYPES:
                return 1
            if et == "Lüftung":
                return 99
            return 10

        for et in sorted(sums.keys(), key=sort_key):
            s = sums[et]
            q_et = float(s.get("Q", 0.0) or 0.0)
            pct = (100.0 * q_et / q_sum) if q_sum > 0.0 else 0.0

            et_disp = et
            if isinstance(et, str) and ("keller" in et.lower()) and ("decke" in et.lower()):
                et_disp = "Kellerdecke (unbeheizt)"
            if isinstance(et, str) and (("speicher" in et.lower()) or ("dachraum" in et.lower())) and ("decke" in et.lower()):
                et_disp = "Decke zum Speicher (unbeheizt)"

            data.append([
                et_disp,
                self.fmt(s.get("A_brutto", 0.0), 2) if et != "Lüftung" else "",
                self.fmt(s.get("A_open", 0.0), 2) if et in OUTER_WALL_TYPES else "",
                self.fmt(s.get("A_eff", 0.0), 2) if et != "Lüftung" else "",
                self.fmt(q_et, 1),
                self.fmt(pct, 1),
            ])

        L = self.cfg.layout
        data_wrapped = _wrap_table_data(
            self.styles, data, header_rows=1, wrap_cols=self.cfg.wrap_cols_type_table,
            ps_head=self.styles["th"], ps_body=self.styles["tb"]
        )
        colw = [w * mm for w in L.colw_type_table_mm]
        tbl = Table(data_wrapped, colWidths=colw, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), L.font_bold),
            ("FONTNAME", (0,1), (-1,-1), L.font_regular),
            ("BACKGROUND", (0,0), (-1,0), L.table_header_bg),
            ("GRID", (0,0), (-1,-1), L.table_grid_width, colors.grey),
            ("ALIGN", (1,1), (-1,-1), "RIGHT"),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), list(L.table_row_bg)),
        ]))
        self.story.append(tbl)

    def _append_calc_proof(self, rr: dict) -> None:
        lines = rr.get("lines", []) if isinstance(rr, dict) else []
        if not isinstance(lines, list) or not lines:
            return

        self.story.append(Spacer(1, 8))
        self.story.append(Paragraph("Berechnungsnachweis (aus heatload.py: Formel + eingesetzte Werte)", self.styles["body"]))
        self.story.append(Spacer(1, 4))

        eq_rows = [["Nr.", "Typ", "Formel", "Eingesetzt (Zahlenwerte)", "Ergebnis [W]"]]

        def _fmt_unit(x, nd=2):
            try:
                return self.fmt(float(x), nd)
            except Exception:
                return "—"

        order = {"TRANSMISSION": 0, "THERMAL_BRIDGE": 1, "VENTILATION": 2}
        lines_sorted = sorted(
            [ln for ln in lines if isinstance(ln, dict)],
            key=lambda ln: (order.get(str(ln.get("line_type", "")).upper(), 9), str(ln.get("element_type", "")))
        )

        n_idx = 0
        for ln in lines_sorted:
            lt = str(ln.get("line_type", "") or "").upper()
            et = str(ln.get("element_type", "") or "")
            qW = float(ln.get("Q_W", 0.0) or 0.0)

            if lt == "TRANSMISSION":
                n_idx += 1
                U = ln.get("U_W_m2K", None)
                fct = ln.get("factor", None)
                sf = float(ln.get("scale", 1.0) or 1.0)
                dT = float(ln.get("dT_K", 0.0) or 0.0)
                A_br = float(ln.get("A_brutto_m2", 0.0) or 0.0)
                A_op = float(ln.get("A_open_m2", 0.0) or 0.0)
                A_eff = float(ln.get("A_eff_m2", 0.0) or 0.0)

                formula = "Φ = U · A_eff · ΔT · f"
                ins = (
                    f"U={_fmt_unit(U,3)} W/(m²K), A_brutto={_fmt_unit(A_br,2)} m², "
                    + (f"A_open={_fmt_unit(A_op,2)} m², " if A_op > 0 else "")
                    + f"s={_fmt_unit(sf,3)}, A_eff={_fmt_unit(A_eff,2)} m², "
                    f"ΔT={_fmt_unit(dT,1)} K, f={_fmt_unit(fct,3)}"
                )
                eq_rows.append([str(n_idx), et, formula, ins, _fmt_unit(qW, 1)])

            elif lt == "THERMAL_BRIDGE":
                n_idx += 1
                mode = str(ln.get("mode", "") or "")
                dT = float(ln.get("dT_K", 0.0) or 0.0)
                A_env = float(ln.get("A_env_m2", 0.0) or 0.0)
                L_env = float(ln.get("L_env_m", 0.0) or 0.0)

                if mode == "psi":
                    formula = "Φ_tb = ψ · L_env · ΔT"
                    ins = f"Mode=ψ; L_env={_fmt_unit(L_env,2)} m; ΔT={_fmt_unit(dT,1)} K"
                elif mode == "delta_u":
                    formula = "Φ_tb = ΔU · A_env · ΔT"
                    ins = f"Mode=ΔU; A_env={_fmt_unit(A_env,2)} m²; ΔT={_fmt_unit(dT,1)} K"
                elif mode == "percent":
                    formula = "Φ_tb = p · Φ_trans"
                    ins = f"Mode=%; ΔT={_fmt_unit(dT,1)} K"
                else:
                    formula = "Φ_tb (parametriert)"
                    ins = f"Mode={mode or '—'}; ΔT={_fmt_unit(dT,1)} K"

                eq_rows.append([str(n_idx), et or "Wärmebrücke", formula, ins, _fmt_unit(qW, 1)])

            elif lt == "VENTILATION":
                n_idx += 1
                dT = float(ln.get("dT_K", 0.0) or 0.0)
                formula = "Φ_vent = c_air · n · V_in · (T_in − T_out)"
                ins = str(ln.get("notes", "") or f"ΔT={_fmt_unit(dT,1)} K")
                eq_rows.append([str(n_idx), "Lüftung", formula, ins, _fmt_unit(qW, 1)])

        L = self.cfg.layout
        eq_rows_wrapped = _wrap_table_data(
            self.styles, eq_rows, header_rows=1, wrap_cols=self.cfg.wrap_cols_eq_table,
            ps_head=self.styles["th"], ps_body=self.styles["tb"]
        )
        tbl_eq = Table(eq_rows_wrapped, colWidths=[w * mm for w in L.colw_eq_table_mm], hAlign="LEFT")
        tbl_eq.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), L.font_bold),
            ("FONTNAME", (0, 1), (-1, -1), L.font_regular),
            ("BACKGROUND", (0, 0), (-1, 0), L.table_header_bg),
            ("GRID", (0, 0), (-1, -1), L.table_grid_width, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0,0), (0,-1), "RIGHT"),
            ("ALIGN", (-1,1), (-1,-1), "RIGHT"),
        ]))
        self.story.append(tbl_eq)

    def _append_total_page(self) -> None:
        self.story.append(PageBreak())
        self.story.append(Paragraph("Gesamt", self.styles["h1"]))
        self.story.append(Paragraph(f"Σ Q_sum = {self.fmt(self.total_Q_sum,1)} W", self.styles["body"]))
        self.story.append(Spacer(1, 6))
        self.story.append(Paragraph("Anteile beziehen sich auf Σ Q_sum (Transmission + Lüftung).", self.styles["body"]))
        self.story.append(Spacer(1, 4))

        total_data = [["Bauteiltyp", "A_brutto [m²]", "A_open [m²]", "A_eff [m²]", "Q [W]", "Anteil [%]"]]

        def sort_key(et: str) -> int:
            if et in OUTER_WALL_TYPES:
                return 0
            if et in WINDOW_TYPES:
                return 1
            if et == "Lüftung":
                return 99
            return 10

        for et in sorted(self.totals_by_type.keys(), key=sort_key):
            s = self.totals_by_type[et]
            q_et = float(s.get("Q", 0.0) or 0.0)
            pct = (100.0 * q_et / self.total_Q_sum) if self.total_Q_sum > 0.0 else 0.0
            total_data.append([
                et,
                self.fmt(s.get("A_brutto", 0.0), 2) if et != "Lüftung" else "",
                self.fmt(s.get("A_open", 0.0), 2) if et in OUTER_WALL_TYPES else "",
                self.fmt(s.get("A_eff", 0.0), 2) if et != "Lüftung" else "",
                self.fmt(q_et, 1),
                self.fmt(pct, 1),
            ])

        L = self.cfg.layout
        total_data_wrapped = _wrap_table_data(
            self.styles, total_data, header_rows=1, wrap_cols=self.cfg.wrap_cols_type_table,
            ps_head=self.styles["th"], ps_body=self.styles["tb"]
        )
        total_tbl = Table(total_data_wrapped, colWidths=[w * mm for w in L.colw_type_table_mm], hAlign="LEFT")
        total_tbl.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), L.font_bold),
            ("BACKGROUND", (0,0), (-1,0), L.table_header_bg),
            ("GRID", (0,0), (-1,-1), L.table_grid_width, colors.grey),
            ("ALIGN", (1,1), (-1,-1), "RIGHT"),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), list(L.table_row_bg)),
        ]))
        self.story.append(total_tbl)

    def _append_room_power_table(self) -> None:
        self.story.append(Spacer(1, 10))
        self.story.append(Paragraph("Abschluss: Heizleistung je Raum", self.styles["h2"]))
        self.story.append(Spacer(1, 6))

        rows = [["Raum", "Geschoss", "A_in [m²]", "Q_out [W]", "Q_ground [W]", "Q_keller [W]", "Q_inter [W]", "Q_dach [W]", "Q_vent [W]", "Q_sum [W]"]]

        sum_a = sum_out = sum_ground = sum_kel = sum_int = sum_dach = sum_vent = sum_q = 0.0

        def rkey(r: RoomModel):
            return (str(getattr(r, "floor", "")), str(getattr(r, "name", "")))

        for r in sorted(self.rooms, key=rkey):
            rr = self.results.get(r.id, {}) or {}
            a_in = float(rr.get("A_in_m2", 0.0) or 0.0)
            q_out = float(rr.get("Q_trans_out_W", 0.0) or 0.0)
            q_ground = float(rr.get("Q_trans_ground_W", 0.0) or 0.0)
            q_kel = float(rr.get("Q_trans_keller_W", 0.0) or 0.0)
            q_int = float(rr.get("Q_trans_interzone_W", 0.0) or 0.0)
            q_dach = float(rr.get("Q_trans_dachraum_W", 0.0) or 0.0)
            q_v = float(rr.get("Q_vent_W", 0.0) or 0.0)
            q_s = float(rr.get("Q_sum_W", 0.0) or 0.0)

            sum_a += a_in; sum_out += q_out; sum_ground += q_ground; sum_kel += q_kel; sum_int += q_int; sum_dach += q_dach; sum_vent += q_v; sum_q += q_s

            rows.append([r.name, r.floor, self.fmt(a_in,2), self.fmt(q_out,1), self.fmt(q_ground,1), self.fmt(q_kel,1),
                         self.fmt(q_int,1), self.fmt(q_dach,1), self.fmt(q_v,1), self.fmt(q_s,1)])

        rows.append(["Σ Summe", "", self.fmt(sum_a,2), self.fmt(sum_out,1), self.fmt(sum_ground,1), self.fmt(sum_kel,1),
                     self.fmt(sum_int,1), self.fmt(sum_dach,1), self.fmt(sum_vent,1), self.fmt(sum_q,1)])

        rows_wrapped = _wrap_table_data(self.styles, rows, header_rows=1, wrap_cols={0},
                                        ps_head=self.styles["th"], ps_body=self.styles["tb"])

        colw = [38*mm, 12*mm, 15*mm, 15*mm, 15*mm, 16*mm, 15*mm, 15*mm, 15*mm, 15*mm]
        tbl = Table(rows_wrapped, colWidths=colw, hAlign="LEFT", repeatRows=1)
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), self.cfg.layout.font_bold),
            ("BACKGROUND", (0,0), (-1,0), self.cfg.layout.table_header_bg),
            ("GRID", (0,0), (-1,-1), self.cfg.layout.table_grid_width, colors.grey),
            ("ALIGN", (2,1), (-1,-1), "RIGHT"),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("ROWBACKGROUNDS", (0,1), (-1,-2), list(self.cfg.layout.table_row_bg)),
            ("FONTNAME", (0,-1), (-1,-1), self.cfg.layout.font_bold),
            ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#f0f0f0")),
        ]))
        self.story.append(tbl)


    def _append_floor_area_section(self) -> None:
        """Adds Wohnfläche je Geschoss (Netto-Innenfläche).

        Expects results["floor_area"] created by heatload.py.
        Optional: results["floor_area"]["plot_png"] path (created by GUI/CLI).
        If plot is missing, we try to generate it locally (matplotlib optional).
        """
        fa = self.results.get("floor_area") if isinstance(self.results, dict) else None
        if not isinstance(fa, dict):
            return

        rows = fa.get("by_floor", []) or []
        total = float(fa.get("total_m2", 0.0) or 0.0)
        if not rows:
            return

        self.story.append(Spacer(1, 10))
        self.story.append(Paragraph("Wohnfläche je Geschoss (Innenmaße · shrink)", self.styles["h2"]))
        self.story.append(Spacer(1, 6))

        tbl = [["Geschoss", "Wohnfläche [m²]"]]
        for r in rows:
            tbl.append([str(r.get("floor", "")), self.fmt(r.get("A_m2", 0.0), 1)])
        tbl.append(["Σ Gesamt", self.fmt(total, 1)])

        tbl_wrapped = _wrap_table_data(self.styles, tbl, header_rows=1, wrap_cols={0},
                                       ps_head=self.styles["th"], ps_body=self.styles["tb"])
        t = Table(tbl_wrapped, colWidths=[25*mm, 30*mm], hAlign="LEFT", repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), self.cfg.layout.font_bold),
            ("BACKGROUND", (0,0), (-1,0), self.cfg.layout.table_header_bg),
            ("GRID", (0,0), (-1,-1), self.cfg.layout.table_grid_width, colors.grey),
            ("ALIGN", (1,1), (-1,-1), "RIGHT"),
            ("FONTNAME", (0,-1), (-1,-1), self.cfg.layout.font_bold),
        ]))
        self.story.append(t)

        # Plot (optional)
        png = fa.get("plot_png") or fa.get("png")
        if (not png) or (not isinstance(png, str)) or (not os.path.exists(png)):
            # try to generate next to PDF
            try:
                from ..core.heatload import render_floor_living_area_plot_png
                png_try = os.path.join(os.path.dirname(self.doc.filename) or ".", "wohnflaeche_by_floor.png")
                png = render_floor_living_area_plot_png(fa, png_try)
                if png:
                    fa["plot_png"] = png
            except Exception:
                png = None

        if png and os.path.exists(png):
            self.story.append(Spacer(1, 6))
            img = Image(png)
            img._restrictSize(160*mm, 70*mm)
            self.story.append(img)


    def _append_thermal_bridge_block(self) -> None:
        """Append a thermal-bridge summary (ΔU/ψ/% depending on heatload output).

        Prefers rr['lines'] entries with line_type == 'THERMAL_BRIDGE' (no recomputation).
        Fallback: uses rr keys like Q_tb_out_W, Q_tb_keller_W, ...
        """
        self.story.append(PageBreak())
        self.story.append(Paragraph("Wärmebrücken", self.styles["h1"]))
        self.story.append(Spacer(1, 6))

        rows = [[
            "Raum", "Geschoss", "Φ_tb außen [W]", "Φ_tb Keller [W]", "Φ_tb oben [W]", "Φ_tb Dachraum [W]", "Σ Φ_tb [W]"
        ]]
        details_by_room: Dict[str, List[Dict[str, Any]]] = {}

        for r in self.rooms:
            rr = self.results.get(r.id, {}) or {}
            tb_out = tb_kel = tb_oben = tb_dach = 0.0

            lines = rr.get("lines", []) if isinstance(rr, dict) else []
            if isinstance(lines, list) and any(isinstance(ln, dict) and str(ln.get("line_type","")).upper()=="THERMAL_BRIDGE" for ln in lines):
                for ln in lines:
                    if not isinstance(ln, dict):
                        continue
                    if str(ln.get("line_type","")).upper() != "THERMAL_BRIDGE":
                        continue
                    q = float(ln.get("Q_W", 0.0) or 0.0)
                    bucket = str(ln.get("bucket", "") or ln.get("boundary", "") or "").lower()
                    if bucket in ("out", "outside", "aussen", "außen"):
                        tb_out += q
                    elif bucket in ("keller", "basement"):
                        tb_kel += q
                    elif bucket in ("oben", "attic_floor", "upper"):
                        tb_oben += q
                    elif bucket in ("dachraum", "speicher", "attic"):
                        tb_dach += q
                    details_by_room.setdefault(r.id, []).append(ln)
            else:
                # Fallback on aggregated keys (best-effort)
                tb_out = float(rr.get("Q_tb_out_W", rr.get("Q_tb_outside_W", 0.0)) or 0.0)
                tb_kel = float(rr.get("Q_tb_keller_W", 0.0) or 0.0)
                tb_oben = float(rr.get("Q_tb_oben_W", 0.0) or 0.0)
                tb_dach = float(rr.get("Q_tb_dachraum_W", rr.get("Q_tb_speicher_W", 0.0)) or 0.0)

            rows.append([
                r.name, getattr(r, "floor", "") or "",
                self.fmt(tb_out, 1), self.fmt(tb_kel, 1), self.fmt(tb_oben, 1), self.fmt(tb_dach, 1),
                self.fmt(tb_out + tb_kel + tb_oben + tb_dach, 1),
            ])

        tbl = Table(self.wrap_table(rows, header_rows=1, wrap_cols={0}), colWidths=[55*mm, 16*mm, 26*mm, 26*mm, 26*mm, 26*mm, 26*mm])
        tbl.setStyle(self.table_style(header_font=8, body_font=max(6, self.cfg.layout.table_body_font_size)))
        self.story.append(tbl)

        # Optional detail pages per room (capped)
        max_rows = int(self.cfg.content.max_tb_rows_per_room)
        any_details = any(details_by_room.values())
        if any_details:
            self.story.append(PageBreak())
            self.story.append(Paragraph("Wärmebrücken – Detailnachweis (aus heatload.py)", self.styles["h2"]))
            self.story.append(Spacer(1, 6))
            drows = [["Raum", "Typ", "Mode", "A_env [m²]", "L_env [m]", "ΔT [K]", "Φ_tb [W]", "Hinweis"]]
            for r in self.rooms:
                for ln in (details_by_room.get(r.id, []) or [])[:max_rows]:
                    mode = str(ln.get("mode", "") or "")
                    drows.append([
                        r.name,
                        str(ln.get("element_type","") or ""),
                        mode,
                        self.fmt(float(ln.get("A_env_m2", 0.0) or 0.0), 2) if mode=="delta_u" else "",
                        self.fmt(float(ln.get("L_env_m", 0.0) or 0.0), 2) if mode=="psi" else "",
                        self.fmt(float(ln.get("dT_K", 0.0) or 0.0), 1),
                        self.fmt(float(ln.get("Q_W", 0.0) or 0.0), 1),
                        str(ln.get("notes","") or ""),
                    ])
            dtbl = Table(self.wrap_table(drows, header_rows=1, wrap_cols={0,1,7}),
                         colWidths=[40*mm, 30*mm, 14*mm, 22*mm, 20*mm, 16*mm, 18*mm, 48*mm])
            dtbl.setStyle(self.table_style(header_font=8, body_font=6))
            self.story.append(dtbl)

    def _append_ventilation_parameters_block(self) -> None:
        """Append a ventilation parameter section (inputs + per-room derived values)."""
        self.story.append(PageBreak())
        self.story.append(Paragraph("Lüftungsparameter", self.styles["h1"]))
        self.story.append(Spacer(1, 6))

        c_air = getattr(self.vent_cfg, "c_air", 0.34)
        rows = [["Parameter", "Wert", "Einheit"]]
        rows.append(["c_air", self.fmt(float(c_air), 3), "Wh/(m³·K)"])
        rows.append(["Standard n (falls genutzt)", str(getattr(self.vent_cfg, "n_default", "raumweise")), "1/h"])

        tbl = Table(self.wrap_table(rows, header_rows=1, wrap_cols={0}), colWidths=[70*mm, 50*mm, 25*mm])
        tbl.setStyle(self.table_style(header_font=8, body_font=max(7, self.cfg.layout.font_size_body-1)))
        self.story.append(tbl)
        self.story.append(Spacer(1, 8))

        # Per-room table
        rrows = [["Raum", "Geschoss", "A_in [m²]", "V_in [m³]", "n [1/h]", "ΔT [K]", "Φ_vent [W]"]]
        for r in self.rooms:
            rr = self.results.get(r.id, {}) or {}
            a_in = float(rr.get("A_in_m2", 0.0) or 0.0)
            v_in = float(rr.get("V_in_m3", 0.0) or 0.0)
            n = float(getattr(r, "air_change_1ph", 0.0) or 0.0)
            dT = max(0.0, float(getattr(r, "t_inside_c", 0.0) or 0.0) - float(self.t_out_c))
            qv = float(rr.get("Q_vent_W", 0.0) or 0.0)
            rrows.append([r.name, getattr(r, "floor", "") or "", self.fmt(a_in,2), self.fmt(v_in,2), self.fmt(n,3), self.fmt(dT,1), self.fmt(qv,1)])

        rtbl = Table(self.wrap_table(rrows, header_rows=1, wrap_cols={0}), colWidths=[55*mm, 16*mm, 20*mm, 22*mm, 18*mm, 16*mm, 22*mm])
        rtbl.setStyle(self.table_style(header_font=8, body_font=max(6, self.cfg.layout.table_body_font_size)))
        self.story.append(rtbl)

    def _append_interzone_matrix(self) -> None:
        """Append an interzone matrix based on rr['lines'] (bucket=interzone) or element meta (t_adj_*).

        This is a *reporting* view: it does not attempt to solve adjacency; it lists all interzone transmission lines
        produced by heatload.py and groups them for readability.
        """
        self.story.append(PageBreak())
        self.story.append(Paragraph("Interzone-Matrix (EG↔DG / beheizt↔beheizt)", self.styles["h1"]))
        self.story.append(Spacer(1, 6))

        rows = [[
            "Von Raum", "Geschoss", "Bauteil", "UID", "T_adj [°C]", "U [W/m²K]", "A_eff [m²]", "ΔT [K]", "Φ [W]"
        ]]

        max_rows = self.cfg.content.max_interzone_rows
        count = 0

        for r in self.rooms:
            rr = self.results.get(r.id, {}) or {}
            lines = rr.get("lines", []) if isinstance(rr, dict) else []
            if isinstance(lines, list):
                for ln in lines:
                    if not isinstance(ln, dict):
                        continue
                    if str(ln.get("line_type","")).upper() != "TRANSMISSION":
                        continue
                    bucket = str(ln.get("bucket","") or ln.get("boundary","") or "").lower()
                    if bucket != "interzone":
                        continue

                    t_adj = ln.get("t_adj_c", None)
                    uid = str(ln.get("uid","") or "")
                    rows.append([
                        r.name,
                        getattr(r, "floor", "") or "",
                        str(ln.get("element_type","") or ""),
                        uid,
                        self.fmt(float(t_adj), 1) if t_adj is not None else "—",
                        self.fmt(float(ln.get("U_W_m2K", 0.0) or 0.0), 3),
                        self.fmt(float(ln.get("A_eff_m2", 0.0) or 0.0), 2),
                        self.fmt(float(ln.get("dT_K", 0.0) or 0.0), 1),
                        self.fmt(float(ln.get("Q_W", 0.0) or 0.0), 1),
                    ])
                    count += 1
                    if max_rows is not None and count >= int(max_rows):
                        break
            if max_rows is not None and count >= int(max_rows):
                break

        # Fallback if no line-based data exists
        if len(rows) == 1:
            self.story.append(Paragraph(
                "Hinweis: Keine interzone-spezifischen Rechenzeilen (rr['lines'] mit bucket='interzone') gefunden. "
                "Für eine Matrix muss heatload.py Interzone-Transmissionen als 'lines' exportieren (empfohlen).",
                self.styles["small"]
            ))
            return

        tbl = Table(self.wrap_table(rows, header_rows=1, wrap_cols={0,2}), colWidths=[45*mm, 14*mm, 34*mm, 20*mm, 18*mm, 18*mm, 20*mm, 14*mm, 18*mm])
        tbl.setStyle(self.table_style(header_font=8, body_font=6))
        self.story.append(tbl)

    def _append_floorplan_heatmaps(self) -> None:
        """Append floorplan heatmaps per floor as embedded images.

        Uses the dedicated FloorplanExporter class so rendering logic is centralized and
        extendable outside of the PDF report.
        """
        self.story.append(PageBreak())
        self.story.append(Paragraph("Floorplan-Heatmap", self.styles["h1"]))
        self.story.append(Spacer(1, 6))

        # Configure exporter from report config
        fp_cfg = FloorplanExportCfg(
            heatmap_enabled=True,
            heatmap_cap_w_per_m2=float(self.cfg.content.heatmap_cap_w_per_m2),
            draw_elements=bool(self.cfg.content.heatmap_include_elements),
            element_label=False,
            label_outer_walls=False,
            label_inner_walls=False,
            match_gui_orientation=False,
            draw_dimensions=False,
        )

        exporter = FloorplanExporter(fp_cfg)

        outdir = os.path.dirname(self.path) or "."
        base_name = f"floorplan_heatmap_{uuid.uuid4().hex[:8]}"
        out_paths = exporter.export(
            rooms=self.rooms,
            elements=self.elements,
            results=self.results,
            outdir=outdir,
            base_name=base_name,
            export_pdf=False,
        )

        # Embed each floor image
        max_w = min(self.doc.width, float(self.cfg.content.heatmap_max_width_mm) * mm)
        max_h = min(self.doc.height * 0.92, float(self.cfg.content.heatmap_max_height_mm) * mm)

        # Stable ordering: floors alphabetically (EG, DG, KG, ...)
        for floor in sorted(out_paths.keys()):
            png = out_paths.get(floor, {}).get("png")
            if not png or (not os.path.exists(png)):
                continue

            self.story.append(Paragraph(f"Geschoss: {floor}", self.styles["h2"]))
            self.story.append(Spacer(1, 4))

            img = Image(png)
            img._restrictSize(max_w, max_h)
            self.story.append(img)
            self.story.append(Spacer(1, 8))

        # Note: temp PNGs are written next to the PDF; leaving them is useful for debugging/sweeps.
    def _append_decks_section(self) -> None:
        """
        Adds an auditable deck section (Kellerdecke / Interzone Decke / Speicherdecke).
        Prefer rr["lines"] from heatload.py, no re-calc.
        """
        # Collect from lines across rooms
        deck_lines = []
        for r in self.rooms:
            rr = self.results.get(r.id, {}) or {}
            for ln in (rr.get("lines", []) if isinstance(rr, dict) else []):
                if not isinstance(ln, dict):
                    continue
                if str(ln.get("line_type","")).upper() != "TRANSMISSION":
                    continue
                et = str(ln.get("element_type","") or "").lower()
                if ("decke" in et) or ("boden" in et):
                    deck_lines.append((r, ln))

        if not deck_lines:
            return

        self.story.append(PageBreak())
        self.story.append(Paragraph("Zusatz: Decken (Keller / Zwischen / Speicher)", self.styles["h1"]))
        self.story.append(Spacer(1, 4))

        # Summaries by category
        def cat(et: str) -> str:
            s = (et or "").lower()
            if "keller" in s:
                return "Kellerdecke"
            if "speicher" in s or "dachraum" in s:
                return "Speicherdecke"
            if "geschoss" in s or "zwischen" in s or "interzone" in s:
                return "Zwischendecke"
            return "Decke"

        sums = {"Kellerdecke": 0.0, "Zwischendecke": 0.0, "Speicherdecke": 0.0, "Decke": 0.0}
        for _r, ln in deck_lines:
            sums[cat(str(ln.get("element_type","")))] += float(ln.get("Q_W", 0.0) or 0.0)

        sum_rows = [["Deckentyp", "Σ Φ [W]"]]
        for k in ["Kellerdecke", "Zwischendecke", "Speicherdecke", "Decke"]:
            if abs(sums.get(k, 0.0)) > 1e-9:
                sum_rows.append([k, self.fmt(sums[k], 1)])
        sum_rows.append(["Σ Decken gesamt", self.fmt(sum(v for v in sums.values()), 1)])

        tbl_sum = Table(
            _wrap_table_data(self.styles, sum_rows, header_rows=1, wrap_cols={0}, ps_head=self.styles["th"], ps_body=self.styles["tb"]),
            colWidths=[85*mm, 35*mm],
            hAlign="LEFT",
        )
        tbl_sum.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), self.cfg.layout.font_bold),
            ("BACKGROUND", (0,0), (-1,0), self.cfg.layout.table_header_bg),
            ("GRID", (0,0), (-1,-1), self.cfg.layout.table_grid_width, colors.grey),
            ("ALIGN", (1,1), (1,-1), "RIGHT"),
            ("FONTNAME", (0,-1), (-1,-1), self.cfg.layout.font_bold),
            ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#f0f0f0")),
        ]))
        self.story.append(tbl_sum)
        self.story.append(Spacer(1, 6))

        # Detail table
        rows = [["Raum", "Geschoss", "Typ", "U", "A_eff", "ΔT", "f", "Φ [W]", "Bucket", "UID"]]
        for r, ln in deck_lines:
            rows.append([
                r.name,
                str(getattr(r, "floor", "") or ""),
                str(ln.get("element_type","")),
                self.fmt(ln.get("U_W_m2K", 0.0), 3),
                self.fmt(ln.get("A_eff_m2", 0.0), 2),
                self.fmt(ln.get("dT_K", 0.0), 1),
                self.fmt(ln.get("factor", 1.0), 3),
                self.fmt(ln.get("Q_W", 0.0), 1),
                str(ln.get("bucket","")),
                str(ln.get("uid","")),
            ])

        rows_wrapped = _wrap_table_data(self.styles, rows, header_rows=1, wrap_cols={0,2}, ps_head=self.styles["th"], ps_body=self.styles["tb"])
        colw = [36*mm, 12*mm, 30*mm, 12*mm, 16*mm, 10*mm, 8*mm, 16*mm, 18*mm, 18*mm]
        tbl = Table(rows_wrapped, colWidths=colw, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), self.cfg.layout.font_bold),
            ("BACKGROUND", (0,0), (-1,0), self.cfg.layout.table_header_bg),
            ("GRID", (0,0), (-1,-1), self.cfg.layout.table_grid_width, colors.grey),
            ("FONTSIZE", (0,1), (-1,-1), self.cfg.layout.table_body_font_size),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("ALIGN", (3,1), (-2,-1), "RIGHT"),
        ]))
        self.story.append(tbl)

    def _append_envelope_section(self) -> None:
        """
        Uses results["envelope"] generated by heatload.py.
        Expected keys:
          envelope = { "summary_by_floor": [...], "totals": {...}, "details": [...], "notes": [...] }
        """
        env = self.results.get("envelope") if isinstance(self.results, dict) else None
        if not isinstance(env, dict):
            return

        self.story.append(PageBreak())
        self.story.append(Paragraph("Gebäude-Hüllflächen (DIN-Nachweis)", self.styles["h1"]))
        self.story.append(Spacer(1, 6))

        summary = env.get("summary_by_floor", []) or []
        totals = env.get("totals", {}) or {}

        tbl = [["Geschoss", "A_out [m²]", "A_erdreich [m²]", "A_keller [m²]", "A_oben [m²]", "A_speicher [m²]", "A_sum [m²]"]]
        for row in summary:
            tbl.append([
                str(row.get("floor", "")),
                self.fmt(row.get("A_env_out_m2", 0.0), 1),
                self.fmt(row.get("A_env_ground_m2", 0.0), 1),
                self.fmt(row.get("A_env_keller_m2", 0.0), 1),
                self.fmt(row.get("A_env_oben_m2", 0.0), 1),
                self.fmt(row.get("A_env_dachraum_m2", 0.0), 1),
                self.fmt(row.get("A_env_sum_m2", 0.0), 1),
            ])

        tbl.append([
            "SUMME",
            self.fmt(totals.get("A_env_out_m2", 0.0), 1),
            self.fmt(totals.get("A_env_ground_m2", 0.0), 1),
            self.fmt(totals.get("A_env_keller_m2", 0.0), 1),
            self.fmt(totals.get("A_env_oben_m2", 0.0), 1),
            self.fmt(totals.get("A_env_dachraum_m2", 0.0), 1),
            self.fmt(totals.get("A_env_sum_m2", 0.0), 1),
        ])

        tbl_wrapped = _wrap_table_data(self.styles, tbl, header_rows=1, wrap_cols={0},
                                       ps_head=self.styles["th"], ps_body=self.styles["tb"])
        t_env = Table(tbl_wrapped, hAlign="LEFT", repeatRows=1)
        t_env.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), self.cfg.layout.font_bold),
            ("BACKGROUND", (0,0), (-1,0), self.cfg.layout.table_header_bg),
            ("GRID", (0,0), (-1,-1), self.cfg.layout.table_grid_width, colors.grey),
            ("ALIGN", (1,1), (-1,-1), "RIGHT"),
            ("ROWBACKGROUNDS", (0,1), (-1,-2), list(self.cfg.layout.table_row_bg)),
            ("FONTNAME", (0,-1), (-1,-1), self.cfg.layout.font_bold),
        ]))
        self.story.append(t_env)

        notes = env.get("notes", []) or []
        if notes:
            self.story.append(Spacer(1, 6))
            self.story.append(Paragraph("Hinweise:", self.styles["h2"]))
            for n in notes[: self.cfg.content.max_envelope_notes]:
                self.story.append(Paragraph(f"• {n}", self.styles["small"]))

        details = env.get("details", []) or []
        if details:
            self.story.append(PageBreak())
            self.story.append(Paragraph("Hüllflächen – Detailnachweis (Flächenbildung)", self.styles["h2"]))
            self.story.append(Spacer(1, 6))
            self.story.append(Paragraph(
                "A_eff = A − A_open (nur bei Außenwänden mit Öffnungsabzug). Interzone-Flächen zählen nicht zur Hüllfläche.",
                self.styles["small"]
            ))
            self.story.append(Spacer(1, 6))

            d_tbl = [["Geschoss", "Bucket", "Element", "UID", "A [m²]", "A_open [m²]", "A_eff [m²]"]]

            limit = self.cfg.content.max_envelope_details_rows
            rows_iter = details[:limit] if (isinstance(limit, int) and limit > 0) else details
            for d in rows_iter:
                d_tbl.append([
                    str(d.get("floor","")),
                    str(d.get("bucket","")),
                    str(d.get("element_type","")),
                    str(d.get("uid","")),
                    self.fmt(d.get("A_m2", 0.0), 2),
                    self.fmt(d.get("A_open_m2", 0.0), 2),
                    self.fmt(d.get("A_eff_m2", 0.0), 2),
                ])

            d_tbl_wrapped = _wrap_table_data(self.styles, d_tbl, header_rows=1, wrap_cols={0,1,2,3},
                                             ps_head=self.styles["th"], ps_body=self.styles["tb"])
            t_det = Table(d_tbl_wrapped, hAlign="LEFT", repeatRows=1,
                          colWidths=[w * mm for w in self.cfg.layout.colw_env_det_mm])
            t_det.setStyle(TableStyle([
                ("FONTNAME", (0,0), (-1,0), self.cfg.layout.font_bold),
                ("BACKGROUND", (0,0), (-1,0), self.cfg.layout.table_header_bg),
                ("GRID", (0,0), (-1,-1), self.cfg.layout.table_grid_width, colors.grey),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("ALIGN", (4,1), (-1,-1), "RIGHT"),
            ]))
            self.story.append(t_det)

    def _append_annexes(self) -> None:
        self.story.append(PageBreak())
        self.story.append(Paragraph("Anhänge", self.styles["h1"]))
        self.story.append(Spacer(1, 6))

        first = _safe_first_result(self.results)
        meta = {
            "t_out_c": float(self.t_out_c),
            "t_out_source": str(self.t_out_src or (getattr(self.project_cfg, "t_out_source", "") if self.project_cfg else "") or "—"),
            "location_plz": str(getattr(self.project_cfg, "location_plz", "") if self.project_cfg else "—"),
            "altitude_m": (getattr(self.project_cfg, "altitude_m", None) if self.project_cfg else None),
            "t_keller_c": float(first.get("t_keller_c", 14.0) if isinstance(first, dict) else 14.0),
            "t_oben_c": float(first.get("t_oben_c", 12.0) if isinstance(first, dict) else 12.0),
            "c_air": getattr(self.vent_cfg, "c_air", "—"),
            "area_shrink_factor": (first.get("area_shrink_factor") if isinstance(first, dict) else None) or "—",
            "thickness_mode": (first.get("thickness_mode") if isinstance(first, dict) else None) or "—",
            "floor_area_mode": (first.get("floor_area_mode") if isinstance(first, dict) else None) or "—",
        }

        if self.cfg.content.include_model_text:
            self.story.append(Paragraph("Anhang A – Rechenmodell & Annahmen (DIN-ähnlich)", self.styles["h2"]))
            self.story.append(Paragraph(ANNEX_MODEL_TEXT, self.styles["body"]))
            self.story.append(Spacer(1, 6))

        if self.cfg.content.include_din_matrix:
            self.story.append(Paragraph("Anhang B – Abgleich DIN EN 12831-1 vs. Tool (Konformität)", self.styles["h2"]))
            tbl_data = _wrap_table_data(self.styles, ANNEX_DIN_CONFORMITY_ROWS, header_rows=1, wrap_cols=None,
                                        ps_head=self.styles["th"], ps_body=self.styles["tb"])
            tbl = Table(tbl_data, colWidths=[45*mm, 55*mm, 55*mm, 30*mm], hAlign="LEFT")
            tbl.setStyle(TableStyle([
                ("FONTNAME", (0,0), (-1,0), self.cfg.layout.font_bold),
                ("BACKGROUND", (0,0), (-1,0), self.cfg.layout.table_header_bg),
                ("GRID", (0,0), (-1,-1), self.cfg.layout.table_grid_width, colors.grey),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("ALIGN", (-1,1), (-1,-1), "CENTER"),
            ]))
            self.story.append(tbl)
            self.story.append(Spacer(1, 6))
            self.story.append(Paragraph(
                "Bewertung: DIN-nah, jedoch nicht voll DIN-konform (z.B. Erdreichverfahren, Aufheizzuschlag, WRG).",
                self.styles["body"]
            ))
            self.story.append(Spacer(1, 6))

        if self.cfg.content.include_factor_table:
            self.story.append(Paragraph("Anhang C – Verwendete Faktoren & Parameter", self.styles["h2"]))
            ft = [
                ["Parameter", "Wert", "Einheit"],
                ["Außentemperatur T_out", self.fmt(meta.get("t_out_c", 0.0), 1), "°C"],
                ["T_out Quelle", str(meta.get("t_out_source", "—")), ""],
                ["Standort (PLZ)", str(meta.get("location_plz", "—")), ""],
                ["Höhe", str(meta.get("altitude_m", "—")), "m"],
                ["Kellertemperatur", self.fmt(meta.get("t_keller_c", 0.0), 1), "°C"],
                ["Geschossdecke oben", self.fmt(meta.get("t_oben_c", 0.0), 1), "°C"],
                ["c_air", str(meta.get("c_air", "—")), "Wh/(m³·K)"],
                ["Flächenkorrektur", str(meta.get("area_shrink_factor", "—")), "—"],
                ["Wandabzug", str(meta.get("thickness_mode", "—")), "full/half"],
                ["Transmissionsmaß", str(meta.get("floor_area_mode", "—")), "inner/outer"],
                ["Erdreichmodell", str((self.project_cfg.ground.mode if getattr(self.project_cfg, "ground", None) else "simplified") if self.project_cfg else "simplified"), "—"],
                ["T_ground", self.fmt((self.project_cfg.ground.ground_temp_c if getattr(self.project_cfg, "ground", None) else 10.0) if self.project_cfg else 10.0, 1), "°C"],
                ["f_ground Bodenplatte", self.fmt((self.project_cfg.ground.f_slab if getattr(self.project_cfg, "ground", None) else 0.40) if self.project_cfg else 0.40, 3), "—"],
                ["f_ground Kellerwand", self.fmt((self.project_cfg.ground.f_wall if getattr(self.project_cfg, "ground", None) else 0.60) if self.project_cfg else 0.60, 3), "—"],
                ["ψ Perimeter", self.fmt((self.project_cfg.ground.psi_perimeter_w_mk if getattr(self.project_cfg, "ground", None) else 0.0) if self.project_cfg else 0.0, 3), "W/mK"],
            ]
            ft_wrapped = _wrap_table_data(self.styles, ft, header_rows=1, wrap_cols={0},
                                          ps_head=self.styles["th"], ps_body=self.styles["tb"])
            tbl_fac = Table(ft_wrapped, colWidths=[60*mm, 35*mm, 35*mm], hAlign="LEFT")
            tbl_fac.setStyle(TableStyle([
                ("FONTNAME", (0,0), (-1,0), self.cfg.layout.font_bold),
                ("BACKGROUND", (0,0), (-1,0), self.cfg.layout.table_header_bg),
                ("GRID", (0,0), (-1,-1), self.cfg.layout.table_grid_width, colors.grey),
                ("ALIGN", (1,1), (2,-1), "LEFT"),
            ]))
            self.story.append(tbl_fac)


# ============================================================
# Backwards compatible API (keeps your existing CLI calls working)
# ============================================================

def export_heatload_report_pdf(
    path: str,
    rooms: List[RoomModel],
    elements: List[ElementModel],
    results: Dict[str, Dict[str, float]],
    *,
    t_out_c: float,
    project_cfg: ProjectCfg | None = None,
    vent_cfg: VentilationCfg = VentilationCfg(),
    title: str = "Heizlast-Report",
    report_cfg: ReportPDFCfg | None = None,
    font_dir: str = "assets/fonts",
) -> None:
    cfg = report_cfg or ReportPDFCfg()
    cfg.title = title
    rep = HeatloadPDFReport(
        path=path,
        rooms=rooms,
        elements=elements,
        results=results,
        t_out_c=t_out_c,
        project_cfg=project_cfg,
        vent_cfg=vent_cfg,
        cfg=cfg,
        font_dir=font_dir,
    )
    rep.build()


# ============================================================
# CSV exports (kept from your previous structure)
# ============================================================

def write_heatload_results_csv(path: str, rooms: List[RoomModel], results: Dict[str, Dict[str, float]], delimiter: str = CSV_DELIMITER) -> None:
    headers = [
        "id", "floor", "name", "area_m2",
        "t_inside_c", "volume_m3", "air_change_1ph",
        "Q_trans_W", "Q_vent_W", "Q_sum_W", "Q_W_per_m2",
        "A_openings_m2", "A_outer_eff_m2",
    ]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(headers)
        for r in rooms:
            rr = results.get(r.id, {}) or {}
            w.writerow([
                r.id, r.floor, r.name,
                f"{float(rr.get('A_in_m2', 0.0)):.2f}".replace(".", ","),
                f"{float(r.t_inside_c or 0.0):.1f}".replace(".", ","),
                f"{float(rr.get('V_in_m3', 0.0)):.2f}".replace(".", ","),
                f"n={float(r.air_change_1ph or 0.0):.3f} 1/h; V={float(rr.get('V_in_m3', 0.0)):.3f} m³",
                f"{float(rr.get('Q_trans_W', 0.0)):.1f}".replace(".", ","),
                f"{float(rr.get('Q_vent_W', 0.0)):.1f}".replace(".", ","),
                f"{float(rr.get('Q_sum_W', 0.0)):.1f}".replace(".", ","),
                f"{float(rr.get('Q_W_per_m2', 0.0)):.1f}".replace(".", ","),
                f"{float(rr.get('A_openings_m2', 0.0)):.2f}".replace(".", ","),
                f"{float(rr.get('A_outer_eff_m2', 0.0)):.2f}".replace(".", ","),
            ])


def write_heatload_details_csv(
    path: str,
    rooms: List[RoomModel],
    elements: List[ElementModel],
    results: Dict[str, Dict[str, float]],
    *,
    t_out_c: float,
    delimiter: str = CSV_DELIMITER
) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    e_by_room: Dict[str, List[ElementModel]] = {}
    for e in elements:
        e_by_room.setdefault(e.room_id, []).append(e)

    headers = [
        "room_id", "floor", "room_name",
        "line_type", "element_type",
        "U_W_m2K", "factor",
        "A_brutto_m2", "A_openings_m2", "A_eff_m2",
        "dT_K", "Q_W",
        "notes",
    ]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(headers)

        for r in rooms:
            rr = results.get(r.id, {}) or {}
            dT = max(0.0, (float(r.t_inside_c or 0.0) - float(t_out_c)))
            room_elements = e_by_room.get(r.id, [])
            room_windows = [e for e in room_elements if e.element_type in WINDOW_TYPES]

            for e in room_elements:
                U = float(getattr(e, "u_w_m2k", 0.0) or 0.0)
                fac = float(getattr(e, "factor", 1.0) or 1.0)
                A = float(getattr(e, "area_m2", 0.0) or 0.0)

                A_open = 0.0
                A_eff = A
                notes = ""

                if e.element_type in OUTER_WALL_TYPES:
                    try:
                        A_open = float(_opening_area_on_wall_segment(e, room_windows))
                    except Exception:
                        A_open = 0.0
                    A_eff = max(0.0, A - A_open)
                    if A_open > 0:
                        notes = "outer wall: window subtraction"

                Q = U * A_eff * dT * fac

                writer.writerow([
                    r.id, r.floor, r.name,
                    "TRANSMISSION", e.element_type,
                    f"{U:.3f}".replace(".", ","),
                    f"{fac:.3f}".replace(".", ","),
                    f"{A:.3f}".replace(".", ","),
                    f"{A_open:.3f}".replace(".", ","),
                    f"{A_eff:.3f}".replace(".", ","),
                    f"{dT:.2f}".replace(".", ","),
                    f"{Q:.1f}".replace(".", ","),
                    notes,
                ])

            q_vent = float(rr.get("Q_vent_W", 0.0) or 0.0)
            writer.writerow([
                r.id, r.floor, r.name,
                "VENTILATION", "",
                "", "",
                "", "", "",
                f"{dT:.2f}".replace(".", ","),
                f"{q_vent:.1f}".replace(".", ","),
                f"c_air=0.34 W/(m³K); n={float(r.air_change_1ph or 0.0):.3f} 1/h; V={float(rr.get('V_in_m3', 0.0)):.3f} m³",
            ])

            writer.writerow([
                r.id, r.floor, r.name,
                "SUMMARY", "",
                "", "",
                "", "", "",
                f"{dT:.2f}".replace(".", ","),
                f"{float(rr.get('Q_sum_W', 0.0) or 0.0):.1f}".replace(".", ","),
                f"Q_trans={float(rr.get('Q_trans_W', 0.0) or 0.0):.1f} W; Q_vent={q_vent:.1f} W; W/m²={float(rr.get('Q_W_per_m2', 0.0) or 0.0):.2f}",
            ])


# ============================================================
# Legacy Floorplan Export API (compatibility)
# ============================================================
# ---------------------------
# Floorplan export (matplotlib)
# ---------------------------

@dataclass(frozen=True)
class FloorplanExportCfg:
    heatmap_enabled: bool = True
    heatmap_cap_w_per_m2: float = HEATMAP_CAP_W_PER_M2
    draw_elements: bool = True
    element_label: bool = True
    element_linewidth: float = 3.0
    room_label_fontsize: int = 10
    element_label_fontsize: int = 8

    # Label toggles
    label_outer_walls: bool = False
    label_inner_walls: bool = False

    # Orientation: match QGraphicsScene (y grows downward)
    match_gui_orientation: bool = True
    # Overall dimensioning (Bemassung)
    draw_dimensions: bool = True
    dimension_offset_m: float = 0.7   # distance outside bounding box [m]
    dimension_linewidth: float = 1.2
    dimension_fontsize: int = 10

    # Label placement
    wall_label_offset_m: float = 0.20   # label distance outside building along outward normal [m]

    # Window rendering (ensure visibility)
    window_overlay: bool = True
    window_overlay_extra_lw: float = 2.0

    # Optional: window list block in top-left (IDs stacked)
    window_list_top_left: bool = True
    window_list_fontsize: int = 9
    window_list_padding_m: float = 0.25

class FloorplanExporter:
    """Encapsulates all floorplan/heatmap rendering.

    Everything related to floorplan drawing lives inside this class so the module
    stays maintainable and callers have a single extension point.

    The legacy module-level `export_floorplans(...)` remains available and simply
    delegates to this class.
    """

    def __init__(self, cfg: 'FloorplanExportCfg | None' = None) -> None:
        self.cfg = cfg or FloorplanExportCfg()

    # ---------- Public API ----------

    def export(
        self,
        rooms: List[RoomModel],
        elements: List[ElementModel],
        results: Dict[str, Dict[str, float]],
        *,
        outdir: str,
        base_name: str = "floorplan",
        export_pdf: bool = False,
    ) -> Dict[str, Dict[str, str]]:
        return self._export_impl(
            rooms=rooms,
            elements=elements,
            results=results,
            outdir=outdir,
            base_name=base_name,
            export_pdf=export_pdf,
        )

    # ---------- Implementation helpers (all kept inside class) ----------

    @staticmethod
    def _compute_bounds(rooms: List[RoomModel]) -> Tuple[float, float, float, float]:
        minx = min(r.x_m for r in rooms)
        miny = min(r.y_m for r in rooms)
        maxx = max(r.x_m + r.w_m for r in rooms)
        maxy = max(r.y_m + r.h_m for r in rooms)
        return minx, miny, maxx, maxy

    @staticmethod
    def _heat_color_rgba(value: float, cap: float) -> Tuple[float, float, float, float]:
        x = max(0.0, min(float(value), float(cap))) / max(float(cap), 1e-9)
        # 0 blue -> 0.5 yellow -> 1 red (same as GUI)
        if x <= 0.5:
            t = x / 0.5
            r = 0.0 + t * 1.0
            g = 0.3 + t * 0.7
            b = 1.0 - t * 1.0
        else:
            t = (x - 0.5) / 0.5
            r = 1.0
            g = 1.0 - t
            b = 0.0
        return (r, g, b, 0.35)

    @staticmethod
    def _element_midpoint(e: ElementModel) -> Optional[Tuple[float, float]]:
        if getattr(e, "label_x_m", None) is not None and getattr(e, "label_y_m", None) is not None:
            return (float(e.label_x_m), float(e.label_y_m))
        if e.has_geometry():
            return ((float(e.x0_m) + float(e.x1_m)) / 2.0, (float(e.y0_m) + float(e.y1_m)) / 2.0)
        return None

    @staticmethod
    def _element_length(e: ElementModel) -> Optional[float]:
        if not e.has_geometry():
            return None
        return math.hypot(float(e.x1_m) - float(e.x0_m), float(e.y1_m) - float(e.y0_m))

    @staticmethod
    def _snap_point(p: Tuple[float, float], tol: float = 1e-6) -> Tuple[float, float]:
        return (round(float(p[0]) / tol) * tol, round(float(p[1]) / tol) * tol)

    @staticmethod
    def _polygon_area(poly: List[Tuple[float, float]]) -> float:
        if len(poly) < 3:
            return 0.0
        a = 0.0
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            a += x0 * y1 - x1 * y0
        return 0.5 * a

    @classmethod
    def _poly_centroid(cls, poly: List[Tuple[float, float]]) -> Tuple[float, float]:
        if len(poly) < 3:
            if not poly:
                return (0.0, 0.0)
            return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
        A = cls._polygon_area(poly)
        if abs(A) < 1e-12:
            return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
        cx = 0.0
        cy = 0.0
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            cross = x0 * y1 - x1 * y0
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
        cx /= (6.0 * A)
        cy /= (6.0 * A)
        return (cx, cy)

    @staticmethod
    def _point_in_poly(pt: Tuple[float, float], poly: List[Tuple[float, float]]) -> bool:
        x, y = pt
        inside = False
        n = len(poly)
        if n < 3:
            return False
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            if ((y0 > y) != (y1 > y)):
                x_int = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                if x_int > x:
                    inside = not inside
        return inside

    @classmethod
    def _outer_boundary_polygon_from_segments(
        cls,
        segs: List[Tuple[Tuple[float, float], Tuple[float, float]]],
        tol: float = 1e-6
    ) -> Optional[List[Tuple[float, float]]]:
        if not segs:
            return None

        def to_yup(p): return (p[0], -p[1])
        def from_yup(p): return (p[0], -p[1])

        adj: Dict[Tuple[float, float], set] = {}
        for a, b in segs:
            a0 = cls._snap_point(a, tol)
            b0 = cls._snap_point(b, tol)
            au = to_yup(a0)
            bu = to_yup(b0)
            adj.setdefault(au, set()).add(bu)
            adj.setdefault(bu, set()).add(au)

        nbr_sorted: Dict[Tuple[float, float], List[Tuple[float, float]]] = {}
        for v, nbs in adj.items():
            vx, vy = v
            items = []
            for nb in nbs:
                dx = nb[0] - vx
                dy = nb[1] - vy
                ang = math.atan2(dy, dx)
                items.append((ang, nb))
            items.sort(key=lambda t: t[0])
            nbr_sorted[v] = [nb for _, nb in items]

        visited = set()
        faces: List[List[Tuple[float, float]]] = []

        def prev_ccw(v, u):
            lst = nbr_sorted.get(v, [])
            if not lst:
                return None
            try:
                idx = lst.index(u)
            except ValueError:
                return lst[-1]
            return lst[(idx - 1) % len(lst)]

        for u in adj:
            for v in adj[u]:
                if (u, v) in visited:
                    continue
                face = []
                start = (u, v)
                cu, cv = u, v
                while True:
                    visited.add((cu, cv))
                    face.append(cu)
                    nw = prev_ccw(cv, cu)
                    if nw is None:
                        break
                    cu, cv = cv, nw
                    if (cu, cv) == start:
                        break
                    if len(face) > 5000:
                        break

                if len(face) >= 3:
                    poly = [from_yup(p) for p in face]
                    cleaned = []
                    for p in poly:
                        if not cleaned or (abs(cleaned[-1][0]-p[0]) > tol or abs(cleaned[-1][1]-p[1]) > tol):
                            cleaned.append(p)
                    if len(cleaned) >= 3:
                        faces.append(cleaned)

        if not faces:
            return None

        faces.sort(key=lambda poly: abs(cls._polygon_area(poly)), reverse=True)
        outer = faces[0]
        if len(outer) >= 2 and (abs(outer[0][0]-outer[-1][0]) < tol and abs(outer[0][1]-outer[-1][1]) < tol):
            outer = outer[:-1]
        return outer

    @classmethod
    def _label_pos_outside_building(
        cls,
        e: ElementModel,
        *,
        building_poly: Optional[List[Tuple[float, float]]],
        building_ref: Tuple[float, float],
        offset_m: float
    ) -> Optional[Tuple[float, float]]:
        if not e.has_geometry():
            return None
        p0 = (float(e.x0_m), float(e.y0_m))
        p1 = (float(e.x1_m), float(e.y1_m))
        mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0

        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 1e-12:
            return (mx, my - offset_m)

        n1 = (-dy / L, dx / L)
        n2 = (dy / L, -dx / L)

        if building_poly and len(building_poly) >= 3:
            eps = max(1e-3, 0.05 * offset_m)
            test1 = (mx + n1[0] * eps, my + n1[1] * eps)
            test2 = (mx + n2[0] * eps, my + n2[1] * eps)
            inside1 = cls._point_in_poly(test1, building_poly)
            inside2 = cls._point_in_poly(test2, building_poly)

            if inside1 and not inside2:
                nx, ny = n2
            elif inside2 and not inside1:
                nx, ny = n1
            else:
                vx, vy = (mx - building_ref[0], my - building_ref[1])
                if (n1[0] * vx + n1[1] * vy) >= (n2[0] * vx + n2[1] * vy):
                    nx, ny = n1
                else:
                    nx, ny = n2
        else:
            vx, vy = (mx - building_ref[0], my - building_ref[1])
            if (n1[0] * vx + n1[1] * vy) >= (n2[0] * vx + n2[1] * vy):
                nx, ny = n1
            else:
                nx, ny = n2

        return (mx + nx * offset_m, my + ny * offset_m)

    @staticmethod
    def _push_point_outside_bbox(
        p: Tuple[float, float],
        direction: Tuple[float, float],
        *,
        bbox: Tuple[float, float, float, float],
        margin: float
    ) -> Tuple[float, float]:
        x, y = float(p[0]), float(p[1])
        dx, dy = float(direction[0]), float(direction[1])
        n = math.hypot(dx, dy)
        if n < 1e-12:
            return (x, y)
        dx /= n
        dy /= n

        minx, maxx, miny, maxy = bbox

        t_candidates = [0.0]
        if abs(dx) > 1e-12:
            if dx > 0:
                t_candidates.append((maxx + margin - x) / dx)
            else:
                t_candidates.append((minx - margin - x) / dx)

        if abs(dy) > 1e-12:
            if dy > 0:
                t_candidates.append((maxy + margin - y) / dy)
            else:
                t_candidates.append((miny - margin - y) / dy)

        t = max(t_candidates)
        eps = max(1e-4, 0.05 * max(1e-6, margin))
        return (x + dx * (t + eps), y + dy * (t + eps))

    @staticmethod
    def _draw_windows_on_ax(ax, elements: List[ElementModel], window_types: set = {"Fenster"}) -> None:
        """
        Draw window segments using the coordinates currently stored on the element objects.
        Elements passed here should already be in the target coordinate system.
        """
        window_segments = []
        for e in elements:
            if e.element_type in window_types and e.has_geometry():
                window_segments.append([(float(e.x0_m), float(e.y0_m)), (float(e.x1_m), float(e.y1_m))])
        if window_segments:
            lc = LineCollection(
                window_segments,
                colors="cyan",
                linewidths=4,
                label="Fenster",
                zorder=5
            )
            ax.add_collection(lc)

    @staticmethod
    def _draw_overall_dimensions(ax, minx: float, miny: float, maxx: float, maxy: float, *, cfg: 'FloorplanExportCfg') -> None:
        try:
            w = float(maxx - minx)
            h = float(maxy - miny)
        except Exception:
            return

        off = float(cfg.dimension_offset_m)
        lw = float(cfg.dimension_linewidth)

        y_dim = miny - off
        ax.plot([minx, minx], [miny, y_dim], color="black", linewidth=lw)
        ax.plot([maxx, maxx], [miny, y_dim], color="black", linewidth=lw)
        ax.annotate(
            "",
            xy=(minx, y_dim),
            xytext=(maxx, y_dim),
            arrowprops=dict(arrowstyle="<->", color="black", linewidth=lw, shrinkA=0, shrinkB=0),
        )
        ax.text(
            (minx + maxx) / 2.0,
            y_dim - 0.05 * off,
            f"Gesamtbreite: {w:.2f} m",
            ha="center",
            va="top",
            fontsize=int(cfg.dimension_fontsize),
            bbox=dict(boxstyle="round,pad=0.15", fc=(1, 1, 1, 0.75), ec=(0, 0, 0, 0.15), lw=0.8),
        )

        x_dim = maxx + off
        ax.plot([maxx, x_dim], [miny, miny], color="black", linewidth=lw)
        ax.plot([maxx, x_dim], [maxy, maxy], color="black", linewidth=lw)
        ax.annotate(
            "",
            xy=(x_dim, miny),
            xytext=(x_dim, maxy),
            arrowprops=dict(arrowstyle="<->", color="black", linewidth=lw, shrinkA=0, shrinkB=0),
        )
        ax.text(
            x_dim + 0.05 * off,
            (miny + maxy) / 2.0,
            f"Gesamthöhe: {h:.2f} m",
            ha="left",
            va="center",
            rotation=90,
            fontsize=int(cfg.dimension_fontsize),
            bbox=dict(boxstyle="round,pad=0.15", fc=(1, 1, 1, 0.75), ec=(0, 0, 0, 0.15), lw=0.8),
        )

    def _export_impl(
        self,
        rooms: List[RoomModel],
        elements: List[ElementModel],
        results: Dict[str, Dict[str, float]],
        *,
        outdir: str,
        base_name: str,
        export_pdf: bool,
    ) -> Dict[str, Dict[str, str]]:
        os.makedirs(outdir, exist_ok=True)

        floors: Dict[str, List[RoomModel]] = {}
        for r in rooms:
            floors.setdefault(str(r.floor), []).append(r)

        els_by_room: Dict[str, List[ElementModel]] = {}
        for e in elements:
            els_by_room.setdefault(e.room_id, []).append(e)

        # ---------- global house origin (bottom-left = 0,0) ----------
        if rooms:
            gminx = min(float(r.x_m) for r in rooms)
            gminy = min(float(r.y_m) for r in rooms)
            gmaxx = max(float(r.x_m + r.w_m) for r in rooms)
            gmaxy = max(float(r.y_m + r.h_m) for r in rooms)
        else:
            gminx = gminy = 0.0
            gmaxx = gmaxy = 1.0

        def X(x: float) -> float:
            return float(x) - float(gminx)

        def Y(y: float) -> float:
            return float(y) - float(gminy)

        out_paths: Dict[str, Dict[str, str]] = {}

        for floor, rlist in floors.items():
            if not rlist:
                continue

            # local floor bounds (only for padding/label placement), plotted in global coordinates
            minx, miny, maxx, maxy = self._compute_bounds(rlist)

            outer_segs: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
            for r in rlist:
                for e in els_by_room.get(r.id, []):
                    if (e.element_type in OUTER_WALL_TYPES or e.element_type in {"Aussenwand", "Außenwand"}) and e.has_geometry():
                        outer_segs.append(((X(float(e.x0_m)), Y(float(e.y0_m))), (X(float(e.x1_m)), Y(float(e.y1_m)))))

            building_poly = self._outer_boundary_polygon_from_segments(outer_segs, tol=1e-6)
            building_ref = self._poly_centroid(building_poly) if building_poly else ((X(minx) + X(maxx)) / 2.0, (Y(miny) + Y(maxy)) / 2.0)

            gw = max(1.0, gmaxx - gminx)
            gh = max(1.0, gmaxy - gminy)
            pad = max(0.5, 0.04 * max(gw, gh))

            fig_w = min(17.0, max(10.0, gw * 1.25))
            fig_h = min(13.0, max(8.0, gh * 1.25))

            fig, ax = plt.subplots(figsize=(fig_w, fig_h))
            ax.set_aspect("equal", adjustable="box")
            ax.set_title(f"Floorplan {floor} – Heizlast je Raum")

            # rooms
            all_elements_this_floor: List[ElementModel] = []
            transformed_elements_this_floor: List[ElementModel] = []

            for r in rlist:
                all_elements_this_floor.extend(els_by_room.get(r.id, []))
                rr = results.get(r.id, {})
                q_sum = float(rr.get("Q_sum_W", 0.0) or 0.0)
                q_wpm2 = float(rr.get("Q_W_per_m2", 0.0) or 0.0)

                face = (0, 0, 0, 0)
                if self.cfg.heatmap_enabled:
                    face = self._heat_color_rgba(q_wpm2, self.cfg.heatmap_cap_w_per_m2)

                rx = X(float(r.x_m))
                ry = Y(float(r.y_m))
                ax.add_patch(Rectangle((rx, ry), float(r.w_m), float(r.h_m), facecolor=face, edgecolor="black", linewidth=2.0))

                cx = rx + float(r.w_m) / 2.0
                cy = ry + float(r.h_m) / 2.0
                area_m2 = float(rr.get("A_in_m2", 0.0) or 0.0)
                ax.text(
                    cx, cy,
                    f"{r.name}\n{q_sum:.0f} W\n{q_wpm2:.0f} W/m²\n{area_m2:.1f} m²",
                    ha="center", va="center",
                    fontsize=self.cfg.room_label_fontsize
                )

                for e in els_by_room.get(r.id, []):
                    if e.has_geometry():
                        e2 = ElementModel(
                            room_id=e.room_id,
                            element_type=e.element_type,
                            area_m2=e.area_m2,
                            u_w_m2k=e.u_w_m2k,
                            factor=e.factor,
                        )
                        # copy optional attrs used by renderer
                        for attr in ("floor","x0_m","y0_m","x1_m","y1_m","length_m","height_m","label_x_m","label_y_m","uid","meta"):
                            if hasattr(e, attr):
                                setattr(e2, attr, getattr(e, attr))
                        if getattr(e2, "x0_m", None) is not None: e2.x0_m = X(float(e2.x0_m))
                        if getattr(e2, "x1_m", None) is not None: e2.x1_m = X(float(e2.x1_m))
                        if getattr(e2, "y0_m", None) is not None: e2.y0_m = Y(float(e2.y0_m))
                        if getattr(e2, "y1_m", None) is not None: e2.y1_m = Y(float(e2.y1_m))
                        if getattr(e2, "label_x_m", None) is not None: e2.label_x_m = X(float(e2.label_x_m))
                        if getattr(e2, "label_y_m", None) is not None: e2.label_y_m = Y(float(e2.label_y_m))
                        transformed_elements_this_floor.append(e2)

            # windows overlay (already transformed)
            self._draw_windows_on_ax(ax, transformed_elements_this_floor)

            # elements
            if self.cfg.draw_elements and transformed_elements_this_floor:
                segments: List[List[Tuple[float, float]]] = []
                seg_style: List[Tuple[float, float, float, float]] = []
                labels: List[Tuple[str, float, float]] = []

                bbox = (X(minx), X(maxx), Y(miny), Y(maxy))

                for e in transformed_elements_this_floor:
                    if e.floor is not None and str(e.floor).strip().upper() != str(floor).strip().upper():
                        continue
                    if not e.has_geometry():
                        continue

                    segments.append([(float(e.x0_m), float(e.y0_m)), (float(e.x1_m), float(e.y1_m))])

                    st = ELEMENT_STYLES.get(e.element_type, ELEMENT_STYLES.get("default", {}))
                    col = st.get("color")
                    if col is not None and hasattr(col, "red"):
                        seg_style.append((col.red() / 255.0, col.green() / 255.0, col.blue() / 255.0, 1.0))
                    else:
                        seg_style.append((1.0, 0.0, 0.0, 1.0))

                    if self.cfg.element_label:
                        L = self._element_length(e) or 0.0
                        try:
                            A_txt = float(e.area_m2 or 0.0)
                        except Exception:
                            A_txt = 0.0
                        label_txt = f"{e.element_type} L={L:.2f} m  A={A_txt:.2f} m²"

                        etype_l = str(e.element_type).strip().lower()
                        is_outer_wall = (e.element_type in OUTER_WALL_TYPES) or (e.element_type in {"Aussenwand", "Außenwand"})
                        is_inner_wall = (e.element_type in {"Innenwand"}) or ("innen" in etype_l) or ("inner" in etype_l)
                        if is_outer_wall and (not self.cfg.label_outer_walls):
                            continue
                        if (not is_outer_wall) and is_inner_wall and (not self.cfg.label_inner_walls):
                            continue

                        if is_outer_wall:
                            mid = self._element_midpoint(e) or ((float(e.x0_m) + float(e.x1_m)) / 2.0, (float(e.y0_m) + float(e.y1_m)) / 2.0)
                            pos = self._label_pos_outside_building(
                                e,
                                building_poly=building_poly,
                                building_ref=building_ref,
                                offset_m=float(self.cfg.wall_label_offset_m),
                            )
                            if pos is None:
                                pos = (mid[0], mid[1] + float(self.cfg.wall_label_offset_m))
                            dir_vec = (pos[0] - mid[0], pos[1] - mid[1])
                            pos = self._push_point_outside_bbox(pos, dir_vec, bbox=bbox, margin=float(self.cfg.wall_label_offset_m))
                        else:
                            pos = self._element_midpoint(e)

                        if pos is not None:
                            labels.append((label_txt, pos[0], pos[1]))

                if segments:
                    lc = LineCollection(segments, colors=seg_style, linewidths=self.cfg.element_linewidth)
                    ax.add_collection(lc)

                    if self.cfg.element_label:
                        for txt, x, y in labels:
                            ax.text(
                                x, y, txt,
                                ha="left", va="bottom",
                                fontsize=self.cfg.element_label_fontsize,
                                bbox=dict(boxstyle="round,pad=0.2", fc=(1, 1, 1, 0.65), ec=(0, 0, 0, 0.2), lw=0.8),
                            )

            # global origin marker (0,0) bottom-left
            origin_cross = max(0.35, 0.03 * max(gw, gh))
            ax.plot([0.0], [0.0], marker="o", markersize=6, color="red", zorder=10)
            ax.plot([-origin_cross, origin_cross], [0.0, 0.0], color="red", linewidth=1.2, zorder=10)
            ax.plot([0.0, 0.0], [-origin_cross, origin_cross], color="red", linewidth=1.2, zorder=10)
            ax.text(
                origin_cross * 0.6,
                origin_cross * 0.6,
                "Ursprung (0,0)",
                color="red",
                fontsize=max(8, self.cfg.dimension_fontsize),
                ha="left",
                va="bottom",
                bbox=dict(boxstyle="round,pad=0.15", fc=(1, 1, 1, 0.85), ec=(1, 0, 0, 0.35), lw=0.8),
                zorder=10,
            )

            margin = pad
            if self.cfg.draw_dimensions:
                margin = max(margin, pad + 2.2 * float(self.cfg.dimension_offset_m))
            if self.cfg.draw_elements and self.cfg.element_label:
                margin = max(margin, pad + 2.5 * float(self.cfg.wall_label_offset_m))
            margin = max(margin, origin_cross * 1.6)

            x0 = 0.0 - margin
            x1 = X(gmaxx) + margin
            y0 = 0.0 - margin
            y1 = Y(gmaxy) + margin

            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)  # 0 unten, y wächst nach oben

            if self.cfg.draw_dimensions:
                self._draw_overall_dimensions(ax, 0.0, 0.0, X(gmaxx), Y(gmaxy), cfg=self.cfg)

            # ticks ab 0
            try:
                xtick_max = max(1, int(math.ceil(X(gmaxx))))
                ytick_max = max(1, int(math.ceil(Y(gmaxy))))
                ax.set_xticks(range(0, xtick_max + 1))
                ax.set_yticks(range(0, ytick_max + 1))
            except Exception:
                pass

            ax.set_xlabel("x [m]")
            ax.set_ylabel("y [m]")
            ax.grid(True, linewidth=0.5)
            fig.tight_layout()

            out_png = os.path.join(outdir, f"{base_name}_{floor}.png")
            fig.savefig(out_png, dpi=260)

            out_pdf_path = None
            if export_pdf:
                out_pdf_path = os.path.join(outdir, f"{base_name}_{floor}.pdf")
                fig.savefig(out_pdf_path, dpi=260)

            plt.close(fig)

            out_paths[floor] = {"png": out_png}
            if out_pdf_path:
                out_paths[floor]["pdf"] = out_pdf_path

        return out_paths



# Backwards-compatible public API (kept for existing callers)
def export_floorplans(
    rooms: List[RoomModel],
    elements: List[ElementModel],
    results: Dict[str, Dict[str, float]],
    *,
    outdir: str,
    base_name: str = "floorplan",
    cfg: FloorplanExportCfg = FloorplanExportCfg(),
    export_pdf: bool = False,
) -> Dict[str, Dict[str, str]]:
    """Legacy wrapper for floorplan export.

    Prefer: `FloorplanExporter(cfg).export(...)`
    """
    return FloorplanExporter(cfg).export(
        rooms=rooms,
        elements=elements,
        results=results,
        outdir=outdir,
        base_name=base_name,
        export_pdf=export_pdf,
    )


# Backwards-compatible helper (kept for older callers; delegates to FloorplanExporter)
def draw_windows_on_ax(ax, elements, window_types={"Fenster"}):
    FloorplanExporter()._draw_windows_on_ax(ax, list(elements), set(window_types) if not isinstance(window_types, set) else window_types)