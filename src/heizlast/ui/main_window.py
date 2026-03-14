from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from ..domain.models import RoomModel
from ..configs.project_config import ProjectCfg

from PySide6.QtCore import QPointF, QSettings
from PySide6.QtWidgets import QGraphicsScene, QMainWindow

from ..core.element_metrics import ElementMetricsService
from ..domain.models import ElementModel, RoomModel
from .graphics import PlanView, PX_PER_M, RoomPolygonItem, ElementLineItem, WindowLineItem
from ..core.polygon_ops import snap_m
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
        self.setWindowTitle("Heizlast Tool")

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

        self._room_draw_mode = True
        self._draw_tool = 'rect'
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

    # ---------------- UI Setup ----------------
