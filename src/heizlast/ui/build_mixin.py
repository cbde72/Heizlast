from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut, QIcon
from .graphics import PlanView, PX_PER_M, RoomRectItem, ElementLineItem, WindowLineItem, snap_m

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

class MainWindowBuildMixin:
    def _build_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self._create_menus()
        self._create_toolbars()
        self._create_central_widget()
        self._create_docks()
        self._create_statusbar()
        self._apply_modern_chrome()

        self.eg_shadow_items = {}  # room_id -> QGraphicsRectItem (EG outline in DG)
        self._labels_dirty = True

        # Signale erst verbinden, wenn alle Widgets (inkl. DockWidgets) existieren.
        self._connect_signals()

    def _std_icon(self, sp):
        return self.style().standardIcon(sp)

    def _toolbar_icon(self, name: str):
        """Liefert konsistente Standard-Icons für Toolbar und Menüs."""
        icon_map = {
            "new": QStyle.SP_FileIcon,
            "open": QStyle.SP_DialogOpenButton,
            "save": QStyle.SP_DialogSaveButton,
            "save_as": QStyle.SP_DriveFDIcon,
            "export": QStyle.SP_DialogApplyButton,
            "project_settings": QStyle.SP_FileDialogContentsView,
            "window_insert": QStyle.SP_FileDialogNewFolder,
            "polygon_room": QStyle.SP_DialogResetButton,
            "rect_room": QStyle.SP_FileDialogDetailedView,
            "l_room": QStyle.SP_FileDialogListView,
            "split_room": QStyle.SP_ArrowRight,
            "merge_rooms": QStyle.SP_CommandLink,
            "subtract_rooms": QStyle.SP_LineEditClearButton,
            "draw_floorplan": QStyle.SP_ComputerIcon,
            "delete_selection": QStyle.SP_TrashIcon,
            "auto_keller": QStyle.SP_ArrowDown,
            "view_3d": QStyle.SP_TitleBarMaxButton,
            "regen": QStyle.SP_BrowserReload,
        }
        return self._std_icon(icon_map.get(name, QStyle.SP_FileDialogDetailedView))

    def _add_toolbar_section(self, toolbar, title: str):
        """Fügt eine dezente Gruppenüberschrift in die Toolbar ein."""
        if toolbar.actions():
            toolbar.addSeparator()
        lbl = QLabel(title)
        lbl.setObjectName("toolbarSectionLabel")
        toolbar.addWidget(lbl)

    def _make_action(self, text: str, *, slot=None, shortcut=None, checkable: bool = False, checked: bool | None = None, icon=None, tip: str | None = None) -> QAction:
        act = QAction(icon if icon is not None else self._std_icon(QStyle.SP_FileDialogDetailedView), text, self)
        if shortcut:
            act.setShortcut(shortcut)
            act.setShortcutContext(Qt.ApplicationShortcut)
            self.addAction(act)
        if tip:
            act.setStatusTip(tip)
            act.setToolTip(tip)
        act.setCheckable(checkable)
        if checked is not None:
            act.setChecked(bool(checked))
        if slot is not None:
            act.triggered.connect(slot)
        return act

    def _create_menus(self):
        """Erstellt die Menüleiste."""
        mbar = self.menuBar()

        # Datei-Menü
        m_file = mbar.addMenu("&Datei")
        self._create_file_menu(m_file)

        # Projekt-Menü
        m_project = mbar.addMenu("&Projekt")
        self._create_project_menu(m_project)

        # Bearbeiten-Menü
        m_edit = mbar.addMenu("&Bearbeiten")
        self._create_edit_menu(m_edit)

        # Ansicht-Menü
        m_view = mbar.addMenu("&Ansicht")
        self._create_view_menu(m_view)

    def _create_file_menu(self, menu):
        """Erstellt das Datei-Menü."""
        self.act_new_project = self._make_action(
            "Neues leeres Projekt",
            slot=self._on_new_project_empty,
            shortcut=QKeySequence.New,
            icon=self._toolbar_icon("new"),
            tip="Leeres Projekt mit Standardwerten anlegen",
        )
        self.act_new_project_with_settings = self._make_action(
            "Neues Projekt mit Projektparametern…",
            slot=self._on_new_project_with_settings,
            icon=self._std_icon(QStyle.SP_FileDialogContentsView),
            tip="Leeres Projekt anlegen und direkt die Projektparameter öffnen",
        )

        self.act_load = self._make_action(
            "Projekt laden…",
            slot=self._on_load,
            shortcut=QKeySequence.Open,
            icon=self._toolbar_icon("open"),
            tip="Raum- und Element-CSV laden",
        )
        self.act_save = self._make_action(
            "Projekt speichern",
            slot=self._on_save,
            shortcut=QKeySequence.Save,
            icon=self._toolbar_icon("save"),
            tip="Aktuelles Projekt speichern",
        )
        self.act_save_as = self._make_action(
            "Projekt speichern unter…",
            slot=self._on_save_as,
            shortcut=QKeySequence.SaveAs,
            icon=self._toolbar_icon("save_as"),
            tip="Projekt unter neuem Namen speichern",
        )
        self.act_export = self._make_action(
            "Report & Grundrisse exportieren…",
            slot=self._on_export_floorplans_csv,
            icon=self._toolbar_icon("export"),
            tip="PDF-Report, Grundrisse und CSV exportieren",
        )
        self.act_quit = self._make_action(
            "Beenden",
            slot=self.close,
            shortcut=QKeySequence.Quit,
            icon=self._std_icon(QStyle.SP_DialogCloseButton),
            tip="Anwendung schließen",
        )

        m_new = menu.addMenu(self._std_icon(QStyle.SP_FileIcon), "Neues Projekt")
        m_new.setToolTipsVisible(True)
        m_new.addAction(self.act_new_project)
        m_new.addAction(self.act_new_project_with_settings)

        self.menu_recent_files = menu.addMenu(self._std_icon(QStyle.SP_DirOpenIcon), "Zuletzt verwendet")
        self.menu_recent_files.setToolTipsVisible(True)
        self._refresh_recent_files_menu()

        menu.addSeparator()
        menu.addAction(self.act_load)
        menu.addAction(self.act_save)
        menu.addAction(self.act_save_as)
        menu.addSeparator()
        menu.addAction(self.act_export)
        menu.addSeparator()
        menu.addAction(self.act_quit)

    def _create_project_menu(self, menu):
        """Erstellt das Projekt-Menü."""
        self.act_project_settings = self._make_action(
            "Projektparameter…",
            slot=self._on_project_settings,
            icon=self._toolbar_icon("project_settings"),
            tip="Randbedingungen, Geometrie, Erdreich und Wärmebrücken bearbeiten",
        )
        self.act_autowalls = self._make_action(
            "Auto-Wände neu",
            slot=self._rebuild_autowalls_all,
            icon=self._std_icon(QStyle.SP_BrowserReload),
            tip="Außen- und Innenwände aus der Raumgeometrie neu erzeugen",
        )
        self.act_auto_keller = self._make_action(
            "Auto Keller",
            slot=self._on_auto_keller,
            icon=self._toolbar_icon("auto_keller"),
            tip="Keller aus den EG-Außenflächen erzeugen",
        )
        self.act_show_3d = self._make_action(
            "3D Ansicht",
            slot=self._on_show_3d_house,
            icon=self._toolbar_icon("view_3d"),
            tip="3D-Darstellung des Hauses anzeigen",
        )
        menu.addAction(self.act_project_settings)
        menu.addSeparator()
        menu.addAction(self.act_autowalls)
        menu.addAction(self.act_auto_keller)
        menu.addAction(self.act_show_3d)

    def _create_edit_menu(self, menu):
        """Erstellt das Bearbeiten-Menü."""
        self.act_delete_selection = QAction(self._toolbar_icon("delete_selection"), "Auswahl löschen", self)
        self.act_delete_selection.setShortcut(QKeySequence.Delete)
        self.act_delete_selection.triggered.connect(self._delete_selection)
        self.act_delete_selection.setShortcutContext(Qt.ApplicationShortcut)
        self.addAction(self.act_delete_selection)
        menu.addAction(self.act_delete_selection)

        self.act_delete_windows = QAction(self._std_icon(QStyle.SP_TitleBarShadeButton), "Fenster löschen", self)
        self.act_delete_windows.setShortcut(QKeySequence("Ctrl+Delete"))
        self.act_delete_windows.triggered.connect(self._delete_selected_windows)
        self.act_delete_windows.setShortcutContext(Qt.ApplicationShortcut)
        self.addAction(self.act_delete_windows)
        menu.addAction(self.act_delete_windows)

        self._room_tool_group = QActionGroup(self)
        self._room_tool_group.setExclusive(True)

        self.act_draw_floorplan = self._make_action(
            "Grundriss zeichnen",
            slot=self._on_draw_floorplan,
            icon=self._toolbar_icon("draw_floorplan"),
            tip="Aktiviert das Zeichnen von Räumen im Grundriss",
        )
        menu.addAction(self.act_draw_floorplan)

        self.act_rect_room = self._make_action(
            "Rechteck-Raum zeichnen",
            slot=self._on_toggle_rect_room_mode,
            checkable=True,
            checked=True,
            icon=self._toolbar_icon("rect_room"),
            tip="Rechteckige Räume per Drag im Grundriss zeichnen",
        )
        self._room_tool_group.addAction(self.act_rect_room)
        menu.addAction(self.act_rect_room)

        self.act_l_room = self._make_action(
            "L-Raum zeichnen",
            slot=self._on_toggle_l_room_mode,
            checkable=True,
            checked=False,
            icon=self._toolbar_icon("l_room"),
            tip="L-förmigen Raum mit drei Klickpunkten zeichnen",
        )
        self._room_tool_group.addAction(self.act_l_room)
        menu.addAction(self.act_l_room)

        self.act_polygon_room = self._make_action(
            "Polygon-Raum zeichnen",
            slot=self._on_toggle_polygon_room_mode,
            checkable=True,
            checked=False,
            icon=self._toolbar_icon("polygon_room"),
            tip="Orthogonalen Polygonraum per Klickpunkten zeichnen",
        )
        self._room_tool_group.addAction(self.act_polygon_room)
        menu.addAction(self.act_polygon_room)

        self.act_split_room = self._make_action(
            "Raum teilen",
            slot=self._on_toggle_split_room_mode,
            checkable=True,
            checked=False,
            icon=self._toolbar_icon("split_room"),
            tip="Selektierten Raum mit einer horizontalen oder vertikalen Schnittlinie teilen",
        )
        menu.addAction(self.act_split_room)

        self.act_merge_rooms = self._make_action(
            "Räume verschmelzen",
            slot=self._on_merge_selected_rooms,
            icon=self._toolbar_icon("merge_rooms"),
            tip="Zwei oder mehr selektierte Räume zu einem Raum verschmelzen",
        )
        menu.addAction(self.act_merge_rooms)

        self.act_subtract_rooms = self._make_action(
            "Räume subtrahieren",
            slot=self._on_subtract_selected_rooms,
            icon=self._toolbar_icon("subtract_rooms"),
            tip="Selektierte Räume voneinander abziehen: erster minus weitere",
        )
        menu.addAction(self.act_subtract_rooms)

        self.act_delete_rooms = QAction(self._std_icon(QStyle.SP_TrashIcon), "Raum löschen", self)
        self.act_delete_rooms.setShortcut(QKeySequence("Shift+Delete"))
        self.act_delete_rooms.triggered.connect(self._delete_selected_rooms)
        self.act_delete_rooms.setShortcutContext(Qt.ApplicationShortcut)
        self.addAction(self.act_delete_rooms)
        menu.addAction(self.act_delete_rooms)

    def _create_view_menu(self, menu):
        """Erstellt das Ansicht-Menü."""
        self.act_regen = self._make_action(
            "Beschriftungen regenerieren",
            slot=self._on_regenerate_labels,
            shortcut="F5",
            icon=self._toolbar_icon("regen"),
            tip="Labels und Leader-Lines neu aufbauen",
        )
        self.act_lbl_outer = self._make_action(
            "Beschriftung Außenwände",
            slot=self._on_toggle_outerwall_labels,
            checkable=True,
            checked=True,
            icon=self._std_icon(QStyle.SP_FileDialogListView),
        )
        self.act_lbl_windows = self._make_action(
            "Beschriftung Fenster",
            slot=self._on_toggle_window_labels,
            checkable=True,
            checked=True,
            icon=self._std_icon(QStyle.SP_FileDialogInfoView),
        )
        self.act_lbl_inner = self._make_action(
            "Beschriftung Innenwände",
            slot=self._on_toggle_innerwall_labels,
            checkable=True,
            checked=True,
            icon=self._std_icon(QStyle.SP_FileDialogDetailedView),
        )
        self.act_debug_overlay = self._make_action(
            "Debug-Overlay: A_in/A_out/A_ref",
            slot=self._on_toggle_debug_overlay,
            checkable=True,
            checked=False,
            icon=self._std_icon(QStyle.SP_MessageBoxInformation),
        )
        self.act_area_ref_outer = self._make_action(
            "W/m²: Außenfläche als Bezugsfläche",
            slot=self._on_toggle_area_ref_outer_action,
            checkable=True,
            checked=False,
            icon=self._std_icon(QStyle.SP_ArrowRight),
        )
        self.act_heatmap = self._make_action(
            "Heatmap anzeigen",
            slot=self._on_heat_toggle,
            checkable=True,
            checked=True,
            icon=self._std_icon(QStyle.SP_DialogYesButton),
        )
        self.act_autowalls_enabled = self._make_action(
            "Auto-Wände aktiv",
            slot=self._on_autow_toggle,
            checkable=True,
            checked=True,
            icon=self._std_icon(QStyle.SP_DialogApplyButton),
        )
        self.act_add_window = self._make_action(
            "Fenster einfügen",
            slot=self._on_add_window_toggle,
            checkable=True,
            checked=False,
            icon=self._std_icon(QStyle.SP_FileDialogNewFolder),
            tip="Aktiviert den Modus zum Einfügen von Fenstern",
        )

        menu.addAction(self.act_regen)
        menu.addSeparator()
        menu.addAction(self.act_heatmap)
        menu.addAction(self.act_autowalls_enabled)
        menu.addAction(self.act_add_window)
        menu.addSeparator()
        menu.addAction(self.act_lbl_outer)
        menu.addAction(self.act_lbl_windows)
        menu.addAction(self.act_lbl_inner)
        menu.addAction(self.act_debug_overlay)
        menu.addSeparator()
        menu.addAction(self.act_area_ref_outer)

    def _create_toolbars(self):
        """Erstellt eine kompakte, thematisch gruppierte Haupt-Toolbar."""
        self.tb_main = QToolBar("Hauptwerkzeuge", self)
        self.tb_main.setObjectName("toolbar_main")
        self.tb_main.setMovable(False)
        self.tb_main.setFloatable(False)
        self.tb_main.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.tb_main.setIconSize(QSize(20, 20))
        self.tb_main.setToolTip("Hauptwerkzeuge")
        self.addToolBar(Qt.TopToolBarArea, self.tb_main)

        groups = [
            ("Datei", [
                self.act_new_project,
                self.act_load,
                self.act_save,
                self.act_save_as,
                self.act_export,
            ]),
            ("Projekt", [
                self.act_project_settings,
                self.act_auto_keller,
                self.act_show_3d,
                self.act_regen,
            ]),
            ("Zeichnen", [
                self.act_draw_floorplan,
                self.act_rect_room,
                self.act_l_room,
                self.act_polygon_room,
                self.act_split_room,
            ]),
            ("Bearbeiten", [
                self.act_merge_rooms,
                self.act_subtract_rooms,
                self.act_add_window,
                self.act_delete_selection,
            ]),
        ]

        seen = set()
        for title, actions in groups:
            self._add_toolbar_section(self.tb_main, title)
            for action in actions:
                if action is None:
                    continue
                key = action.text().strip()
                if key in seen:
                    continue
                seen.add(key)
                self.tb_main.addAction(action)

        for btn in self.tb_main.findChildren(QToolButton):
            btn.setAutoRaise(True)
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)

    def _create_central_widget(self):
        """Erstellt das zentrale Widget nur mit Geschoss-Tabs; Eigenschaften/Elemente liegen in DockWidgets."""
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)

        left = self._create_left_panel()
        root.addLayout(left, 1)

    def _create_left_panel(self):
        """Erstellt das linke Panel mit Geschoss-Tabs und einer kompakten Info-Leiste."""
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        self.tabs.addTab(self.view_KG, "Keller")
        self.tabs.addTab(self.view_EG, "EG")
        self.tabs.addTab(self.view_DG, "DG")
        for _v in (self.view_KG, self.view_EG, self.view_DG):
            try:
                _v.setMouseTracking(True)
                _v.viewport().setMouseTracking(True)
            except Exception:
                pass

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(self.tabs)

        control_bar = QFrame()
        control_bar.setObjectName("planInfoBar")
        control_bar.setFrameShape(QFrame.NoFrame)
        control_lay = QHBoxLayout(control_bar)
        control_lay.setContentsMargins(10, 8, 10, 8)
        control_lay.setSpacing(12)

        lbl_hint = QLabel("Planansicht")
        lbl_hint.setObjectName("planInfoTitle")
        lbl_sub = QLabel("Grundriss zeichnen: Rechteck-, L- und Polygonräume, Trennen/Verschmelzen/Subtrahieren über Menü und Toolbar")
        lbl_sub.setObjectName("planInfoText")

        control_lay.addWidget(lbl_hint)
        control_lay.addWidget(lbl_sub, 1)
        left.addWidget(control_bar)

        return left

    def _create_docks(self):
        """Erstellt echte DockWidgets für Eigenschaften und Elemente."""
        # Eigenschaften
        self.dock_properties = QDockWidget("Eigenschaften", self)
        self.dock_properties.setObjectName("dock_properties")
        self.dock_properties.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        prop_widget = QWidget()
        prop_layout = QVBoxLayout(prop_widget)
        prop_layout.setContentsMargins(8, 8, 8, 8)
        prop_layout.addWidget(QLabel("Raum-Eigenschaften (Auswahl):"))

        form = QFormLayout()
        self._create_room_form_widgets(form)
        prop_layout.addLayout(form)

        self.cb_area_ref_outer = QCheckBox("W/m² auf Außenfläche beziehen")
        self.cb_area_ref_outer.setChecked(False)
        self.cb_area_ref_outer.setToolTip(
            "Aktiv: Bezugsfläche A_ref = Außenmaße (w*h).\n"
            "Inaktiv: Bezugsfläche A_ref = Innenmaße (aus Wanddicken).\n"
            "Volumen/Lüftung bleiben immer Innenmaß-basiert."
        )
        prop_layout.addWidget(self.cb_area_ref_outer)

        self.btn_apply = QPushButton("Übernehmen")
        self.btn_apply.setIcon(self._std_icon(QStyle.SP_DialogApplyButton))
        prop_layout.addWidget(self.btn_apply)
        prop_layout.addStretch(1)
        self.dock_properties.setWidget(prop_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_properties)

        # Elemente
        self.dock_elements = QDockWidget("Elemente", self)
        self.dock_elements.setObjectName("dock_elements")
        self.dock_elements.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        elem_widget = QWidget()
        elem_layout = QVBoxLayout(elem_widget)
        elem_layout.setContentsMargins(8, 8, 8, 8)
        elem_layout.addWidget(QLabel("Elemente des selektierten Raums:"))

        self.list_room_elements = QListWidget()
        self.list_room_elements.setMinimumHeight(200)
        self.list_room_elements.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_room_elements.itemSelectionChanged.connect(self._on_room_element_selected)
        self.list_room_elements.itemDoubleClicked.connect(self._on_room_element_double_clicked)
        self.list_room_elements.setToolTip("Klick: Element in Grafik hervorheben\nEntf: Element löschen")
        elem_layout.addWidget(self.list_room_elements)

        self.dock_elements.setWidget(elem_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_elements)
        self.splitDockWidget(self.dock_properties, self.dock_elements, Qt.Vertical)
        self.dock_properties.raise_()

    def _create_statusbar(self):
        """Statusbar mit Projektpfad, Raumanzahl und Heizlast gesamt."""
        sb = QStatusBar(self)
        self.setStatusBar(sb)

        self.lbl_status_project = QLabel("Projekt: —")
        self.lbl_status_project.setTextFormat(Qt.PlainText)
        self.lbl_status_project.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.lbl_status_recent = QLabel("Zuletzt: —")
        self.lbl_status_rooms = QLabel("Räume: 0")
        self.lbl_status_heat = QLabel("Heizlast gesamt: 0 W")

        sb.addWidget(self.lbl_status_project, 1)
        sb.addPermanentWidget(self.lbl_status_recent)
        sb.addPermanentWidget(self.lbl_status_rooms)
        sb.addPermanentWidget(self.lbl_status_heat)

        self._update_statusbar_summary()

    def _update_statusbar_summary(self):
        project_path = str(self._project_rooms_path) if self._project_rooms_path else "—"
        try:
            total_q = 0.0
            if isinstance(getattr(self, "_last_heatload_results", None), dict):
                for rid, rr in self._last_heatload_results.items():
                    if rid == "envelope" or not isinstance(rr, dict):
                        continue
                    total_q += float(rr.get("Q_sum_W", 0.0) or 0.0)
            last_dir = getattr(self, "_last_project_dir", None) or "—"
            self.lbl_status_project.setText(f"Projekt: {project_path}")
            self.lbl_status_recent.setText(f"Ordner: {last_dir}")
            self.lbl_status_rooms.setText(f"Räume: {len(self.rooms)}")
            self.lbl_status_heat.setText(f"Heizlast gesamt: {total_q:,.0f} W".replace(",", "."))
        except Exception:
            pass

    def _create_right_panel(self):
        """Erstellt das rechte Panel mit Raumeigenschaften."""
        right = QVBoxLayout()
        right.addWidget(QLabel("Raum-Eigenschaften (Auswahl):"))

        form = QFormLayout()
        self._create_room_form_widgets(form)
        right.addLayout(form)

        # Elemente des selektierten Raums
        right.addWidget(QLabel("Elemente des Raums:"))
        self.list_room_elements = QListWidget()
        self.list_room_elements.setMinimumHeight(160)
        self.list_room_elements.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_room_elements.itemSelectionChanged.connect(self._on_room_element_selected)
        self.list_room_elements.setToolTip("Klick: Element in Grafik hervorheben\nEntf: Element löschen")
        self.list_room_elements.itemDoubleClicked.connect(self._on_room_element_double_clicked)
        right.addWidget(self.list_room_elements)

        # Bezugsfläche für W/m²
        self.cb_area_ref_outer = QCheckBox("W/m² auf Außenfläche beziehen")
        self.cb_area_ref_outer.setChecked(False)
        self.cb_area_ref_outer.setToolTip(
            "Aktiv: Bezugsfläche A_ref = Außenmaße (w*h).\n"
            "Inaktiv: Bezugsfläche A_ref = Innenmaße (aus Wanddicken).\n"
            "Volumen/Lüftung bleiben immer Innenmaß-basiert."
        )
        right.addWidget(self.cb_area_ref_outer)

        self.btn_apply = QPushButton("Übernehmen")
        right.addWidget(self.btn_apply)

        right.addStretch(1)
        return right

    def _create_room_form_widgets(self, form):
        """Erstellt die Eingabefelder für Raumeigenschaften."""
        self.ed_id = QLineEdit()
        self.ed_id.setReadOnly(True)
        self.ed_name = QLineEdit()
        self.cb_floor = QComboBox()
        self.cb_floor.addItems(["KG", "EG", "DG"])
        self.sp_x = QDoubleSpinBox()
        self.sp_x.setRange(-1000, 1000)
        self.sp_x.setDecimals(2)
        self.sp_x.setSingleStep(0.05)
        self.sp_y = QDoubleSpinBox()
        self.sp_y.setRange(-1000, 1000)
        self.sp_y.setDecimals(2)
        self.sp_y.setSingleStep(0.05)
        self.sp_w = QDoubleSpinBox()
        self.sp_w.setRange(0.2, 1000)
        self.sp_w.setDecimals(2)
        self.sp_w.setSingleStep(0.05)
        self.sp_h = QDoubleSpinBox()
        self.sp_h.setRange(0.2, 1000)
        self.sp_h.setDecimals(2)
        self.sp_h.setSingleStep(0.05)
        self.sp_height = QDoubleSpinBox()
        self.sp_height.setRange(1.8, 6.0)
        self.sp_height.setDecimals(2)
        self.sp_height.setSingleStep(0.05)
        self.sp_tin = QDoubleSpinBox()
        self.sp_tin.setRange(5, 30)
        self.sp_tin.setDecimals(1)
        self.sp_tin.setSingleStep(0.5)
        self.sp_n = QDoubleSpinBox()
        self.sp_n.setRange(0.0, 5.0)
        self.sp_n.setDecimals(2)
        self.sp_n.setSingleStep(0.05)

        form.addRow("ID", self.ed_id)
        form.addRow("Name", self.ed_name)
        form.addRow("Geschoss", self.cb_floor)
        form.addRow("x [m]", self.sp_x)
        form.addRow("y [m]", self.sp_y)
        form.addRow("Länge w [m]", self.sp_w)
        form.addRow("Breite h [m]", self.sp_h)
        form.addRow("Raumhöhe [m]", self.sp_height)
        form.addRow("T innen [°C]", self.sp_tin)
        form.addRow("n [1/h]", self.sp_n)

    def _connect_signals(self):
        """Verbindet die UI-Signale mit den Slots."""
        self.act_heatmap.toggled.connect(self._on_heat_toggle)
        self.act_autowalls_enabled.toggled.connect(self._on_autow_toggle)
        if getattr(self, "cb_area_ref_outer", None) is not None:
            self.cb_area_ref_outer.toggled.connect(lambda _: self._recompute_and_redraw())
        self.btn_apply.clicked.connect(self._apply_room_form)

        # Auswahländerungen in den Szenen
        self.scene_KG.selectionChanged.connect(lambda: self._on_scene_selection_changed("KG"))
        self.scene_EG.selectionChanged.connect(lambda: self._on_scene_selection_changed("EG"))
        self.scene_DG.selectionChanged.connect(lambda: self._on_scene_selection_changed("DG"))


        #
        # Shortcut für Element löschen in der Liste
        self._sc_del_elem = QShortcut(QKeySequence.Delete, self.list_room_elements)
        self._sc_del_elem.activated.connect(self._delete_selected_room_element)

    def _restore_ui_settings(self):
        """Stellt gespeicherte UI-Einstellungen wieder her."""
        try:
            use_outer = self._settings.value("area_ref_outer", False, type=bool)
            if hasattr(self, "cb_area_ref_outer"):
                self.cb_area_ref_outer.blockSignals(True)
                self.cb_area_ref_outer.setChecked(bool(use_outer))
                self.cb_area_ref_outer.blockSignals(False)
            if hasattr(self, "act_area_ref_outer"):
                self.act_area_ref_outer.blockSignals(True)
                self.act_area_ref_outer.setChecked(bool(use_outer))
                self.act_area_ref_outer.blockSignals(False)
        except Exception:
            pass

        try:
            dbg_on = self._settings.value("debug_overlay", False, type=bool)
            self.show_debug_overlay = bool(dbg_on)
            if hasattr(self, "act_debug_overlay"):
                self.act_debug_overlay.blockSignals(True)
                self.act_debug_overlay.setChecked(bool(dbg_on))
                self.act_debug_overlay.blockSignals(False)
        except Exception:
            pass

        try:
            self._last_project_dir = self._settings.value("last_project_dir", "", type=str) or ""
        except Exception:
            self._last_project_dir = ""

        try:
            geom = self._settings.value("main_geometry")
            if geom:
                self.restoreGeometry(geom)
            state = self._settings.value("main_state")
            if state:
                self.restoreState(state)
            was_maximized = self._settings.value("main_was_maximized", True, type=bool)
            if was_maximized:
                self.showMaximized()
        except Exception:
            pass

        try:
            if hasattr(self, "menu_recent_files"):
                self._refresh_recent_files_menu()
        except Exception:
            pass

    # ---------------- Hilfsfunktionen ----------------

    def closeEvent(self, event):
        try:
            self._settings.setValue("main_geometry", self.saveGeometry())
            self._settings.setValue("main_state", self.saveState())
            self._settings.setValue("main_was_maximized", self.isMaximized())
            self._settings.setValue("last_project_dir", getattr(self, "_last_project_dir", "") or "")
        except Exception:
            pass
        return super().closeEvent(event)

    def _refresh_recent_files_menu(self):
        menu = getattr(self, "menu_recent_files", None)
        if menu is None:
            return
        menu.clear()
        recent = []
        try:
            recent = self._settings.value("recent_project_files", [], type=list) or []
        except Exception:
            recent = []
        recent = [str(x) for x in recent if str(x).strip()]
        if not recent:
            act = menu.addAction("Keine zuletzt verwendeten Projekte")
            act.setEnabled(False)
            return
        for path in recent[:10]:
            act = menu.addAction(self._std_icon(QStyle.SP_FileLinkIcon), path)
            act.setToolTip(path)
            act.triggered.connect(lambda _=False, p=path: self._open_recent_project(p))
        menu.addSeparator()
        clear_act = menu.addAction("Liste leeren")
        clear_act.triggered.connect(self._clear_recent_files)


    def _apply_modern_chrome(self):
        """Wendet ein modernes, aber robustes Qt-Stylesheet auf MainWindow, Menüs und Toolbars an."""
        self.setDocumentMode(True)
        try:
            self.setUnifiedTitleAndToolBarOnMac(False)
        except Exception:
            pass

        self.setStyleSheet("""
        QMainWindow {
            background: #f4f6f8;
        }
        QMenuBar {
            background: #ffffff;
            border-bottom: 1px solid #d7dbe0;
            padding: 4px 6px;
        }
        QMenuBar::item {
            background: transparent;
            padding: 6px 10px;
            margin: 0 2px;
            border-radius: 6px;
        }
        QMenuBar::item:selected {
            background: #e9eef5;
        }
        QMenu {
            background: #ffffff;
            border: 1px solid #d7dbe0;
            padding: 6px;
        }
        QMenu::item {
            padding: 7px 28px 7px 12px;
            border-radius: 6px;
        }
        QMenu::item:selected {
            background: #e9eef5;
        }
        QToolBar {
            background: #ffffff;
            border: none;
            border-bottom: 1px solid #d7dbe0;
            spacing: 4px;
            padding: 6px 8px;
        }
        QToolButton {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 6px;
            margin: 1px;
        }
        QToolButton:hover {
            background: #edf3fb;
            border-color: #c9d8ea;
        }
        QToolButton:checked {
            background: #dbe9f8;
            border-color: #a8c2df;
        }
        QLabel#toolbarSectionLabel {
            color: #66788a;
            font-size: 11px;
            font-weight: 700;
            padding: 0 8px 0 4px;
        }
        QStatusBar {
            background: #ffffff;
            border-top: 1px solid #d7dbe0;
        }
        QTabWidget::pane {
            border: none;
            background: #f4f6f8;
        }
        QTabBar::tab {
            background: #e7ebf0;
            padding: 8px 14px;
            margin-right: 4px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
        QTabBar::tab:selected {
            background: #ffffff;
        }
        QDockWidget {
            titlebar-close-icon: none;
            titlebar-normal-icon: none;
        }
        QDockWidget::title {
            background: #ffffff;
            border-bottom: 1px solid #d7dbe0;
            padding: 8px 10px;
            text-align: left;
            font-weight: 600;
        }
        QListWidget, QLineEdit, QComboBox, QDoubleSpinBox {
            background: #ffffff;
            border: 1px solid #cfd6de;
            border-radius: 8px;
            padding: 4px 6px;
        }
        QPushButton {
            background: #ffffff;
            border: 1px solid #cfd6de;
            border-radius: 8px;
            padding: 7px 12px;
        }
        QPushButton:hover {
            background: #edf3fb;
            border-color: #c9d8ea;
        }
        QFrame#planInfoBar {
            background: #ffffff;
            border-top: 1px solid #d7dbe0;
        }
        QLabel#planInfoTitle {
            font-size: 13px;
            font-weight: 600;
            color: #243447;
        }
        QLabel#planInfoText {
            color: #5b6978;
        }
        QLabel#newProjectTitle {
            font-size: 16px;
            font-weight: 700;
            color: #243447;
        }
        """)
