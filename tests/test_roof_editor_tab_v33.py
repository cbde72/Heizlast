from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'src' / 'heizlast' / 'ui' / 'build_mixin.py'
SETTINGS = ROOT / 'src' / 'heizlast' / 'ui' / 'settings_mixin.py'


def test_build_mixin_contains_dach_editor_tab():
    src = BUILD.read_text(encoding='utf-8')
    assert 'self.tabs.addTab(self.view_DG, "DG")' in src
    assert 'self.tabs.addTab(self.roof_editor_tab, "Dach")' not in src
    assert 'self.act_open_roof_editor = self._make_action(' in src
    assert 'slot=self._open_roof_editor_dialog' in src
    assert 'def _create_roof_editor_panel(self, parent=None):' in src
    assert 'def _open_roof_editor_dialog(self):' in src
    assert 'dlg.setWindowTitle("Dach-Editor")' in src
    assert 'self.roof_line_editor_tab = RoofLineEditorWidget(self)' in src
    assert 'self.lst_roof_tab_lines = QListWidget()' in src
    assert 'self.btn_roof_tab_open_settings = QPushButton("Weitere Projektparameter")' in src


def test_settings_mixin_contains_roof_editor_sync_and_handlers():
    src = SETTINGS.read_text(encoding='utf-8')
    assert 'def _sync_roof_editor_tab_widgets(self) -> None:' in src
    assert 'def _on_roof_editor_lines_changed(self) -> None:' in src
    assert 'attic.roof_lines = editor.current_lines()' in src
    assert 'def _delete_selected_roof_editor_line(self) -> None:' in src


def test_roof_editor_dialog_contains_professional_splitter_metrics_and_live_preview():
    src = BUILD.read_text(encoding='utf-8')
    assert 'content_splitter = QSplitter(Qt.Horizontal, page)' in src
    assert 'self.roof_editor_right_splitter = QSplitter(Qt.Vertical, right_wrap)' in src
    assert 'self.roof_editor_right_splitter.setSizes([420, 160, 260])' in src
    assert 'summary_wrap = QFrame()' in src
    assert 'self.lbl_roof_metric_area = QLabel("–")' in src
    assert 'preview_title = QLabel("Live-Dachvorschau")' in src
    assert 'facet_title = QLabel("Dachflächen / Facetten")' in src
    assert 'self.lst_roof_tab_facets = QListWidget()' in src
    assert 'line_title = QLabel("Dachlinien-Editor")' in src
    assert 'self.roof_editor_panel.setMinimumSize(720, 560)' in src


def test_attic_sketch_uses_responsive_preview_layout():
    src = Path("src/heizlast/ui/attic_sketch.py").read_text(encoding="utf-8")
    assert 'if rect.width() < 720:' in src
    assert 'self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)' in src


def test_main_window_refresh_updates_dialog_preview_panel_and_summary():
    src = (ROOT / 'src' / 'heizlast' / 'ui' / 'main_window.py').read_text(encoding='utf-8')
    assert 'roof_editor_panel = getattr(self, "roof_editor_preview_panel", None)' in src
    assert 'roof_editor_panel.set_geometry(geom)' in src
    assert 'self._sync_roof_editor_summary()' in src
    assert 'self._sync_roof_editor_facet_list()' in src


def test_settings_mixin_updates_roof_editor_metrics_and_facets():
    src = SETTINGS.read_text(encoding='utf-8')
    assert 'def _sync_roof_editor_summary(self) -> None:' in src
    assert 'def _sync_roof_editor_facet_list(self) -> None:' in src
    assert 'metrics["lbl_roof_metric_area"]' in src
    assert 'lst.addItem("Keine Facetten berechnet")' in src


def test_roof_editor_contains_help_button_and_help_dialog():
    src = BUILD.read_text(encoding='utf-8')
    assert 'self.btn_roof_tab_help = QPushButton("Hilfe")' in src
    assert 'self.btn_roof_tab_help_secondary = QPushButton("Ausführliche Hilfe")' in src
    assert 'def _open_roof_help_dialog(self, section_key: str | None = None):' in src
    assert 'def _create_roof_help_dialog(self) -> QDialog:' in src
    assert 'def _make_roof_help_pixmap(self, kind: str, size: QSize | None = None) -> QPixmap:' in src
    assert 'QScrollArea' in src


def test_roof_help_context_navigation_and_gallery_present():
    src = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    assert 'def _wrap_roof_editor_field_with_help' in src
    assert 'self._open_roof_help_dialog(key)' in src
    assert 'def _create_roof_type_gallery' in src
    assert 'Dach-Mini-Renderings je Dachtyp' in src
    assert 'roof_type_gable' in src


def test_property_dock_is_scrollable():
    src = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    assert 'prop_scroll = QScrollArea()' in src
    assert 'self.dock_properties.setWidget(prop_scroll)' in src
    assert 'prop_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)' in src
    assert 'form.setRowWrapPolicy(QFormLayout.WrapLongRows)' in src


def test_main_docks_have_professional_titlebars_and_tabbed_layout():
    src = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    assert 'class DockTitleBar(QFrame):' in src
    assert 'self.setDockOptions(' in src
    assert 'QMainWindow.AllowTabbedDocks' in src
    assert 'QMainWindow.GroupedDragging' in src
    assert 'self.dock_attic.setTitleBarWidget(DockTitleBar(' in src
    assert 'self.tabifyDockWidget(self.dock_elements, self.dock_plausibility)' in src
    assert 'QFrame#dockTitleBar' in src
    assert 'def _configure_side_dock(self, dock: QDockWidget, min_width: int = 220) -> None:' in src
    assert 'dock.setMaximumWidth(self._DOCK_MAX_WIDTH)' in src
    assert 'widget.setMaximumWidth(self._DOCK_MAX_WIDTH)' in src
    assert 'def _release_side_dock_width_limits(self) -> None:' in src
    assert 'self.resizeDocks(docks, [preferred] * len(docks), Qt.Horizontal)' not in src


def test_central_plan_area_can_shrink_for_wide_side_docks():
    build_src = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    graphics_src = Path("src/heizlast/ui/graphics.py").read_text(encoding="utf-8")
    assert 'cw.setMinimumWidth(0)' in build_src
    assert 'cw.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)' in build_src
    assert 'self.tabs.setMinimumWidth(0)' in build_src
    assert 'self.tabs.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)' in build_src
    assert 'control_bar.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)' in build_src
    assert 'self.btn_fit_current_view = QPushButton("Ansicht einpassen")' not in build_src
    assert 'self.btn_show_current_floor_3d = QPushButton("3D Geschoss")' not in build_src
    assert 'self.btn_show_shell_2d = QPushButton("2D Hülle+")' not in build_src
    assert 'self.btn_show_shell_3d_gl = QPushButton("3D Hülle+")' not in build_src
    assert 'self.setMinimumSize(0, 0)' in graphics_src
    assert 'self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)' in graphics_src


def test_main_window_does_not_restore_oversized_geometry_before_maximize():
    src = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    assert 'was_maximized = self._settings.value("main_was_maximized", True, type=bool)' in src
    assert 'if geom and not was_maximized:' in src


def test_roof_help_contains_interactive_example_roofs():
    src = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    assert 'class RoofExampleCard(QFrame):' in src
    assert 'def _roof_example_presets(self) -> dict[str, dict]:' in src
    assert 'def _apply_roof_example(self, example_key: str) -> None:' in src
    assert 'Beispiel laden' in src
    assert 'gable_standard' in src
    assert 'flat_modern' in src


def test_roof_editor_contains_dormer_section_and_buttons():
    src = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    assert 'dormer_title = QLabel("Gauben")' in src
    assert 'self.lst_roof_tab_dormers = QListWidget()' in src
    assert 'self.btn_roof_tab_add_dormer = QPushButton("Gaube hinzufügen")' in src
    assert 'self.btn_roof_tab_edit_dormer = QPushButton("Bearbeiten")' in src
    assert 'self.btn_roof_tab_delete_dormer = QPushButton("Löschen")' in src


def test_settings_mixin_contains_dormer_sync_and_handlers_for_roof_editor():
    src = Path("src/heizlast/ui/settings_mixin.py").read_text(encoding="utf-8")
    assert 'def _sync_roof_editor_dormer_list(self) -> None:' in src
    assert 'def _add_roof_editor_dormer(self) -> None:' in src
    assert 'def _edit_selected_roof_editor_dormer(self) -> None:' in src
    assert 'def _delete_selected_roof_editor_dormer(self) -> None:' in src
    assert 'DormerEditDialog' in src


def test_roof_editor_contains_graphical_dormer_placement_controls():
    src = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    assert 'self.btn_roof_tab_place_dormer = QPushButton("Grafisch platzieren")' in src
    assert 'self.btn_roof_tab_place_dormer.setCheckable(True)' in src
    assert 'self.roof_editor_preview_panel.planClicked.connect(self._on_roof_editor_preview_plan_clicked)' in src


def test_attic_sketch_emits_plan_click_for_graphical_dormer_placement():
    src = Path("src/heizlast/ui/attic_sketch.py").read_text(encoding="utf-8")
    assert 'planClicked = Signal(dict)' in src
    assert 'def _build_plan_click_payload(self, px: float, py: float) -> dict | None:' in src
    assert 'self.planClicked.emit(payload)' in src


def test_settings_mixin_handles_graphical_dormer_placement():
    src = Path("src/heizlast/ui/settings_mixin.py").read_text(encoding="utf-8")
    assert 'def _on_toggle_roof_editor_dormer_place_mode(self, checked: bool) -> None:' in src
    assert 'def _on_roof_editor_preview_plan_clicked(self, payload: dict) -> None:' in src
    assert 'Gaube grafisch eingefügt.' in src
    assert 'Gaube grafisch verschoben.' in src


def test_attic_sketch_contains_hover_preview_and_insertion_markers():
    src = Path("src/heizlast/ui/attic_sketch.py").read_text(encoding="utf-8")
    assert 'self._hover_plan_payload: dict | None = None' in src
    assert 'self.setMouseTracking(True)' in src
    assert 'def set_dormer_preview_state(self, active: bool, *, has_selection: bool = False, dormer_width_m: float = 1.80, min_edge_clearance_m: float = 0.40, draw_mode: bool = False) -> None:' in src
    assert 'def _build_hover_preview_rect(self, payload: dict) -> QRectF | None:' in src
    assert 'def _build_hover_side_highlight_rect(self, payload: dict) -> QRectF | None:' in src
    assert 'def mouseMoveEvent(self, event):' in src


def test_settings_mixin_syncs_preview_interaction_state_for_dormer_hover_preview():
    src = Path("src/heizlast/ui/settings_mixin.py").read_text(encoding="utf-8")
    assert 'def _sync_roof_editor_preview_interaction_state(self) -> None:' in src
    assert 'panel.set_dormer_preview_state(' in src
    assert 'Einfügemarker und Hover-Vorschau' in src


def test_roof_editor_contains_drag_and_drop_connections_for_dormers():
    src = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    assert 'dormerDragStarted.connect(self._on_roof_editor_dormer_drag_started)' in src
    assert 'dormerDragMoved.connect(self._on_roof_editor_dormer_drag_moved)' in src
    assert 'dormerDragFinished.connect(self._on_roof_editor_dormer_drag_finished)' in src


def test_attic_sketch_contains_drag_and_drop_support_for_selected_dormers():
    src = Path("src/heizlast/ui/attic_sketch.py").read_text(encoding="utf-8")
    assert 'dormerDragStarted = Signal(dict)' in src
    assert 'dormerDragMoved = Signal(dict)' in src
    assert 'dormerDragFinished = Signal(dict)' in src
    assert 'def set_selected_dormer_state(self, payload: dict | None) -> None:' in src
    assert 'def mouseReleaseEvent(self, event):' in src
    assert 'self.dormerDragFinished.emit(payload)' in src


def test_settings_mixin_contains_drag_and_drop_handlers_for_dormers():
    src = Path("src/heizlast/ui/settings_mixin.py").read_text(encoding="utf-8")
    assert 'def _selected_roof_editor_dormer_preview_payload(self) -> dict | None:' in src
    assert 'def _apply_roof_editor_dormer_payload(self, payload: dict, *, finalize: bool) -> bool:' in src
    assert 'def _on_roof_editor_dormer_drag_started(self, payload: dict) -> None:' in src
    assert 'def _on_roof_editor_dormer_drag_moved(self, payload: dict) -> None:' in src
    assert 'def _on_roof_editor_dormer_drag_finished(self, payload: dict) -> None:' in src
    assert 'Gaube per Drag&Drop verschoben.' in src


def test_roof_editor_contains_resize_handle_connections_for_dormers():
    src = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    assert 'dormerResizeStarted.connect(self._on_roof_editor_dormer_resize_started)' in src
    assert 'dormerResizeMoved.connect(self._on_roof_editor_dormer_resize_moved)' in src
    assert 'dormerResizeFinished.connect(self._on_roof_editor_dormer_resize_finished)' in src


def test_attic_sketch_contains_resize_handle_support_for_selected_dormers():
    src = Path("src/heizlast/ui/attic_sketch.py").read_text(encoding="utf-8")
    assert 'dormerResizeStarted = Signal(dict)' in src
    assert 'dormerResizeMoved = Signal(dict)' in src
    assert 'dormerResizeFinished = Signal(dict)' in src
    assert 'def _build_selected_dormer_handle_rects(self) -> dict[str, QRectF]:' in src
    assert 'def _hit_selected_dormer_resize_handle(self, payload: dict | None) -> str | None:' in src
    assert 'def _build_resize_payload(self, payload: dict | None) -> dict | None:' in src


def test_settings_mixin_contains_resize_handlers_for_dormers():
    src = Path("src/heizlast/ui/settings_mixin.py").read_text(encoding="utf-8")
    assert 'def _on_roof_editor_dormer_resize_started(self, payload: dict) -> None:' in src
    assert 'def _on_roof_editor_dormer_resize_moved(self, payload: dict) -> None:' in src
    assert 'def _on_roof_editor_dormer_resize_finished(self, payload: dict) -> None:' in src
    assert '"depth_m": float(getattr(dormer, "depth_m", 1.40) or 1.40),' in src
