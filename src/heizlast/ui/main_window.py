from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from ..configs.project_config import ProjectCfg
from ..core.attic_geometry import AtticGeometry

from PySide6.QtCore import QPointF, QSettings
from PySide6.QtWidgets import QGraphicsScene, QMainWindow

from ..core.element_metrics import ElementMetricsService
from ..domain.models import ElementModel, RoomModel
from .graphics import PlanView, RoomPolygonItem, ElementLineItem
from .build_mixin import MainWindowBuildMixin
from .load_save_mixin import MainWindowLoadSaveMixin
from .export_mixin import MainWindowExportMixin
from .settings_mixin import MainWindowSettingsMixin
from .selection_mixin import MainWindowSelectionMixin
from .element_edit_mixin import MainWindowElementEditMixin
from .element_delete_mixin import MainWindowElementDeleteMixin
from .window_insert_mixin import MainWindowWindowInsertMixin
from .redraw_mixin import MainWindowRedrawMixin
from .autowalls_mixin import MainWindowAutowallsMixin
from .overlay_mixin import MainWindowOverlayMixin
from .misc_mixin import MainWindowMiscMixin
from ..infrastructure.attic_svg import AtticSvgRenderer
from .. import APP_NAME, __internal_version__

class MainWindow(
    MainWindowBuildMixin,
    MainWindowLoadSaveMixin,
    MainWindowExportMixin,
    MainWindowSettingsMixin,
    MainWindowSelectionMixin,
    MainWindowElementEditMixin,
    MainWindowElementDeleteMixin,
    MainWindowWindowInsertMixin,
    MainWindowRedrawMixin,
    MainWindowAutowallsMixin,
    MainWindowOverlayMixin,
    MainWindowMiscMixin,
    QMainWindow,
):
    """Integrated split MainWindow for the V5.16 package."""

    def __init__(self):
        #import gui_room_refactor_v2.element_metrics
        #print("ELEMENT_METRICS FILE:", gui_room_refactor_v2.element_metrics.__file__)
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} – {__internal_version__}")

        # Data
        self.rooms: Dict[str, RoomModel] = {}
        self.elements: List[ElementModel] = []
        self.metrics = ElementMetricsService(self.rooms, self.elements)

        self.element_items_by_uid: Dict[str, Any] = {}
        self._highlight_item = None

        # Graphics
        self.scene_KG = QGraphicsScene(0, 0, 2200, 1400)
        self.scene_EG = QGraphicsScene(0, 0, 2200, 1400)
        self.scene_DG = QGraphicsScene(0, 0, 2200, 1400)
        self.view_KG = PlanView(self.scene_KG)
        self.view_EG = PlanView(self.scene_EG)
        self.view_DG = PlanView(self.scene_DG)

        self.view_KG.viewport().installEventFilter(self)
        self.view_EG.viewport().installEventFilter(self)
        self.view_DG.viewport().installEventFilter(self)
        self.view_KG._context_menu_handler = self._handle_plan_context_menu
        self.view_EG._context_menu_handler = self._handle_plan_context_menu
        self.view_DG._context_menu_handler = self._handle_plan_context_menu

        self.room_items: Dict[str, RoomPolygonItem] = {}
        self.element_items: Dict[str, ElementLineItem] = {}

        # UI state
        self.project_cfg = ProjectCfg()
        self.t_out_c = float(self.project_cfg.t_out_c)

        self.heatmap_enabled = True
        self.autowalls_enabled = True

        # Label visibility toggles
        self.show_outerwall_labels = True
        self.show_innerwall_labels = True
        self.show_window_labels = True
        self.show_debug_overlay = False
        self.show_auto_attic_markers = True

        self._room_draw_mode = False
        self._draw_tool = 'select'
        self._polygon_room_mode = False
        self._l_room_mode = False
        self._split_room_mode = False
        self._polygon_points_scene: List[QPointF] = []
        self._l_room_points_scene: List[QPointF] = []
        self._preview_polygon = None
        self._start_pos_scene: Optional[Tuple[str, QPointF]] = None
        self._preview_room: Optional[Any] = None
        self._split_start_scene: Optional[Tuple[str, QPointF]] = None
        self._preview_split_line: Optional[Any] = None
        self._add_window_mode = False
        self._selected_room_id: Optional[str] = None
        self._last_heatload_results: Optional[Dict] = None

        # Project paths
        self._project_rooms_path: Optional[Path] = None
        self._project_elements_path: Optional[Path] = None

        # Persisted UI settings
        self._settings = QSettings("Heizlast", "HouseTool")
        self._build_ui()
        # Re-entrancy guards (verhindert doppelte/rekursive Updates)
        self._in_populate_room_elements_list = False
        self._in_sync_list_with_graphics_selection = False
        # Restore persisted settings
        self._restore_ui_settings()


        self._recompute_and_redraw()
        self._refresh_attic_preview()

    def _current_attic_geometry(self) -> Optional[AtticGeometry]:
        cfg = getattr(self, "project_cfg", None)
        attic_cfg = getattr(cfg, "attic", None)
        if not attic_cfg or not bool(getattr(attic_cfg, "enabled", False)):
            return None
        try:
            return AtticGeometry(
                building_width_m=float(attic_cfg.building_width_m),
                building_length_m=float(attic_cfg.building_length_m),
                knee_wall_height_m=float(attic_cfg.knee_wall_height_m),
                roof_pitch_deg=float(attic_cfg.roof_pitch_deg),
                roof_type=str(getattr(attic_cfg, "roof_type", "satteldach") or "satteldach").strip().lower(),
                ridge_orientation=str(getattr(attic_cfg, "ridge_orientation", "length") or "length").strip().lower(),
                roof_overhang_m=float(getattr(attic_cfg, "roof_overhang_m", 0.30) or 0.0),
                ridge_offset_ratio=float(getattr(attic_cfg, "ridge_offset_ratio", 0.0) or 0.0),
                pult_rise_side=str(getattr(attic_cfg, "pult_rise_side", "right") or "right").strip().lower(),
                roof_lines=tuple((str(getattr(line, "kind", "first") or "first"), float(getattr(line, "x1_ratio", 0.0) or 0.0), float(getattr(line, "y1_ratio", 0.0) or 0.0), float(getattr(line, "x2_ratio", 0.0) or 0.0), float(getattr(line, "y2_ratio", 0.0) or 0.0)) for line in list(getattr(attic_cfg, "roof_lines", []) or [])),
            )
        except Exception:
            return None

    def _refresh_attic_preview(self) -> None:
        geom = self._current_attic_geometry()
        panel = getattr(self, "attic_sketch_panel", None)
        if panel is not None:
            panel.set_geometry(geom)
        roof_editor_panel = getattr(self, "roof_editor_preview_panel", None)
        if roof_editor_panel is not None:
            roof_editor_panel.set_geometry(geom)
        if hasattr(self, "_sync_roof_editor_summary"):
            self._sync_roof_editor_summary()
        if hasattr(self, "_sync_roof_editor_facet_list"):
            self._sync_roof_editor_facet_list()

    def _export_attic_svg_to(self, path: Path) -> bool:
        geom = self._current_attic_geometry()
        if geom is None:
            return False
        svg = AtticSvgRenderer().render(geom)
        path.write_text(svg, encoding="utf-8")
        return True

    def _current_plan_view(self):
        tabs = getattr(self, "tabs", None)
        current = tabs.currentWidget() if tabs is not None else None
        if current in (getattr(self, "view_KG", None), getattr(self, "view_EG", None), getattr(self, "view_DG", None)):
            return current
        return getattr(self, "view_EG", None)

    def _fit_current_plan_view(self) -> None:
        view = self._current_plan_view()
        if view is None:
            return
        try:
            if hasattr(view, "fit_content"):
                view.fit_content()
            else:
                view.fit_all()
        except Exception:
            try:
                view.fit_all()
            except Exception:
                return
        try:
            self.statusBar().showMessage("Ansicht auf aktuelle Skizze zentriert.", 2000)
        except Exception:
            pass

    # ---------------- UI Setup ----------------
