from pathlib import Path

from PySide6.QtCore import Qt, QSize, QPointF, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut, QIcon, QPainter, QPen, QBrush, QColor, QPolygonF, QPainterPath, QPixmap
from .attic_sketch import AtticSketchPanel
from .dialogs.project_settings_dialog import RoofLineEditorWidget
from ..core.config import ROOM_USAGE_DEFAULTS

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QDialog,
    QDialogButtonBox,
    QSplitter,
    QGridLayout,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QTabWidget,
    QTableWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class RoofExampleCard(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class DockTitleBar(QFrame):
    def __init__(self, dock: QDockWidget, title: str, subtitle: str = "", badge: str = ""):
        super().__init__(dock)
        self.setObjectName("dockTitleBar")
        self._dock = dock
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 8, 8)
        lay.setSpacing(8)

        text_box = QWidget(self)
        text_lay = QVBoxLayout(text_box)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(1)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("dockTitle")
        title_lbl.setMinimumWidth(0)
        title_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        text_lay.addWidget(title_lbl)
        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setObjectName("dockSubtitle")
            sub_lbl.setWordWrap(False)
            sub_lbl.setMinimumWidth(0)
            sub_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            text_lay.addWidget(sub_lbl)
        lay.addWidget(text_box, 1)

        if badge:
            badge_lbl = QLabel(badge)
            badge_lbl.setObjectName("dockBadge")
            lay.addWidget(badge_lbl, 0, Qt.AlignVCenter)

        self.btn_float = QToolButton(self)
        self.btn_float.setObjectName("dockTitleButton")
        self.btn_float.setText("↗")
        self.btn_float.setToolTip("Dock abdocken / andocken")
        self.btn_float.clicked.connect(lambda: dock.setFloating(not dock.isFloating()))
        lay.addWidget(self.btn_float, 0, Qt.AlignVCenter)

        self.btn_close = QToolButton(self)
        self.btn_close.setObjectName("dockTitleButton")
        self.btn_close.setText("×")
        self.btn_close.setToolTip("Dock ausblenden")
        self.btn_close.clicked.connect(dock.hide)
        lay.addWidget(self.btn_close, 0, Qt.AlignVCenter)


class MainWindowBuildMixin:
    _DOCK_MAX_WIDTH = 16777215

    def _build_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self.setDockOptions(
            self.dockOptions()
            | QMainWindow.AllowNestedDocks
            | QMainWindow.AllowTabbedDocks
            | QMainWindow.GroupedDragging
            | QMainWindow.AnimatedDocks
        )
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

    def _configure_side_dock(self, dock: QDockWidget, min_width: int = 220) -> None:
        dock.setMinimumWidth(min_width)
        dock.setMaximumWidth(self._DOCK_MAX_WIDTH)
        dock.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget = dock.widget()
        if widget is not None:
            widget.setMinimumWidth(0)
            widget.setMaximumWidth(self._DOCK_MAX_WIDTH)
            widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)

    def _side_dock_widgets(self) -> list[QDockWidget]:
        names = ("dock_dashboard", "dock_properties", "dock_elements", "dock_attic", "dock_plausibility")
        return [getattr(self, name) for name in names if hasattr(self, name)]

    def _release_side_dock_width_limits(self) -> None:
        for dock in self._side_dock_widgets():
            self._configure_side_dock(dock)

    def _std_icon(self, sp):
        return self.style().standardIcon(sp)

    def _asset_icon_path(self, name: str) -> Path | None:
        base = Path(__file__).resolve().parents[1] / "assets" / "icons"
        candidate = base / f"{name}.svg"
        return candidate if candidate.exists() else None

    def _load_asset_icon(self, name: str) -> QIcon:
        candidate = self._asset_icon_path(name)
        if candidate is None:
            return QIcon()
        return QIcon(str(candidate))

    def _draw_shape_icon(self, name: str) -> QIcon:
        size = 24
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        fg = self.palette().buttonText().color()
        accent = self.palette().highlight().color()
        muted = QColor(fg)
        muted.setAlpha(150)
        pen = QPen(fg, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        accent_pen = QPen(accent, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        dashed_pen = QPen(accent, 1.6, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if name == "select":
            path = QPainterPath()
            path.moveTo(5, 4)
            path.lineTo(5, 18)
            path.lineTo(9.5, 14.0)
            path.lineTo(12.5, 20)
            path.lineTo(15.2, 18.8)
            path.lineTo(12.1, 12.8)
            path.lineTo(18.5, 12.8)
            path.closeSubpath()
            painter.fillPath(path, QBrush(accent))
            painter.drawPath(path)
        elif name == "draw_floorplan":
            painter.setPen(QPen(muted, 1.2))
            for x in (5, 11, 17):
                painter.drawLine(x, 4, x, 20)
            for y in (5, 11, 17):
                painter.drawLine(4, y, 20, y)
            painter.setPen(accent_pen)
            painter.drawRect(6, 6, 12, 9)
        elif name == "rect_room":
            painter.setPen(accent_pen)
            painter.drawRect(5.5, 6.0, 13.0, 10.0)
        elif name == "l_room":
            painter.setPen(accent_pen)
            painter.drawPolyline(QPolygonF([
                QPointF(5.5, 6.0), QPointF(18.0, 6.0), QPointF(18.0, 10.0),
                QPointF(12.0, 10.0), QPointF(12.0, 16.0), QPointF(5.5, 16.0), QPointF(5.5, 6.0)
            ]))
        elif name == "polygon_room":
            painter.setPen(accent_pen)
            painter.drawPolygon(QPolygonF([
                QPointF(6.0, 7.0), QPointF(16.5, 5.5), QPointF(19.0, 11.0),
                QPointF(14.0, 17.5), QPointF(7.0, 16.0), QPointF(4.5, 11.0)
            ]))
        elif name == "split_room":
            painter.setPen(QPen(fg, 1.6))
            painter.drawRect(4.5, 5.5, 15.0, 12.0)
            painter.setPen(dashed_pen)
            painter.drawLine(12.0, 4.0, 12.0, 19.0)
        elif name == "merge_rooms":
            painter.setPen(QPen(fg, 1.6))
            painter.drawRect(4.5, 7.0, 6.5, 8.0)
            painter.drawRect(13.0, 7.0, 6.5, 8.0)
            painter.setPen(accent_pen)
            painter.drawLine(10.5, 11.0, 13.0, 11.0)
            painter.drawLine(11.7, 9.8, 11.7, 12.2)
        elif name == "subtract_rooms":
            painter.setPen(QPen(fg, 1.6))
            painter.drawRect(4.5, 6.0, 14.5, 11.0)
            painter.setBrush(QBrush(accent))
            painter.drawRect(12.0, 8.0, 5.0, 5.0)
            painter.setPen(QPen(Qt.white, 1.8, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(13.0, 10.5, 16.0, 10.5)
        elif name == "window_insert":
            painter.setPen(QPen(fg, 1.6))
            painter.drawLine(5.0, 17.0, 19.0, 17.0)
            painter.setPen(accent_pen)
            painter.drawLine(8.0, 17.0, 16.0, 17.0)
            painter.drawLine(8.0, 14.0, 8.0, 20.0)
            painter.drawLine(16.0, 14.0, 16.0, 20.0)
        elif name == "roof_profile":
            painter.setPen(accent_pen)
            painter.drawPolyline(QPolygonF([QPointF(4.5, 16.5), QPointF(10.0, 7.0), QPointF(19.5, 16.5)]))
            painter.setPen(QPen(fg, 1.4))
            painter.drawLine(4.5, 16.5, 4.5, 20.0)
            painter.drawLine(19.5, 16.5, 19.5, 20.0)
            painter.drawLine(4.5, 20.0, 19.5, 20.0)
        elif name == "roof_settings":
            painter.setPen(accent_pen)
            painter.drawPolyline(QPolygonF([QPointF(4.5, 15.5), QPointF(10.0, 7.0), QPointF(19.5, 15.5)]))
            painter.setPen(QPen(fg, 1.4))
            painter.drawLine(4.5, 15.5, 4.5, 19.0)
            painter.drawLine(19.5, 15.5, 19.5, 19.0)
            painter.drawLine(4.5, 19.0, 19.5, 19.0)
            painter.drawEllipse(14.5, 4.0, 5.0, 5.0)
            painter.drawLine(17.0, 4.0, 17.0, 2.5)
            painter.drawLine(17.0, 9.0, 17.0, 10.5)
            painter.drawLine(14.5, 6.5, 13.0, 6.5)
            painter.drawLine(19.5, 6.5, 21.0, 6.5)
        elif name == "attic_markers":
            painter.setPen(accent_pen)
            painter.drawPolyline(QPolygonF([QPointF(4.5, 15.5), QPointF(10.0, 7.5), QPointF(19.5, 15.5)]))
            painter.setPen(QPen(fg, 1.4))
            painter.drawRoundedRect(4.0, 16.0, 7.0, 4.5, 1.5, 1.5)
            painter.drawRoundedRect(13.0, 16.0, 7.0, 4.5, 1.5, 1.5)
            painter.drawLine(4.5, 15.5, 4.5, 20.5)
            painter.drawLine(19.5, 15.5, 19.5, 20.5)
        elif name == "fit_view":
            painter.setPen(QPen(fg, 1.6))
            painter.drawRect(5.5, 5.5, 13.0, 13.0)
            painter.setPen(accent_pen)
            painter.drawLine(3.5, 9.0, 3.5, 5.0)
            painter.drawLine(3.5, 5.0, 7.5, 5.0)
            painter.drawLine(20.5, 9.0, 20.5, 5.0)
            painter.drawLine(20.5, 5.0, 16.5, 5.0)
            painter.drawLine(3.5, 15.0, 3.5, 19.0)
            painter.drawLine(3.5, 19.0, 7.5, 19.0)
            painter.drawLine(20.5, 15.0, 20.5, 19.0)
            painter.drawLine(20.5, 19.0, 16.5, 19.0)
        elif name == "go_dg":
            painter.setPen(QPen(fg, 1.4))
            painter.drawRect(4.5, 10.0, 15.0, 9.0)
            painter.setPen(accent_pen)
            painter.drawPolyline(QPolygonF([QPointF(4.5, 10.0), QPointF(10.0, 4.5), QPointF(19.5, 10.0)]))
            painter.drawLine(12.5, 13.0, 17.5, 13.0)
            painter.drawLine(15.0, 10.5, 17.5, 13.0)
            painter.drawLine(15.0, 15.5, 17.5, 13.0)
        else:
            painter.end()
            return QIcon()

        painter.end()
        return QIcon(pm)

    def _toolbar_icon(self, name: str):
        """Liefert konsistente und funktionsnahe Icons für Toolbar und Menüs."""
        icon = self._load_asset_icon(name)
        if not icon.isNull():
            return icon

        vector_names = {
            "select", "draw_floorplan", "rect_room", "l_room", "polygon_room",
            "split_room", "merge_rooms", "subtract_rooms", "window_insert",
            "auto_walls", "auto_keller", "project_settings", "view_3d",
            "regen", "delete_selection", "roof_profile", "roof_settings",
            "attic_markers", "fit_view", "go_dg"
        }
        if name in vector_names:
            icon = self._draw_shape_icon(name)
            if not icon.isNull():
                return icon
        icon_map = {
            "new": QStyle.SP_FileIcon,
            "open": QStyle.SP_DialogOpenButton,
            "save": QStyle.SP_DialogSaveButton,
            "save_as": QStyle.SP_DriveFDIcon,
            "export": QStyle.SP_DialogApplyButton,
            "project_settings": QStyle.SP_FileDialogContentsView,
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

        # Dach-Menü
        m_roof = mbar.addMenu("&Dach")
        self._create_roof_menu(m_roof)

        # Hilfe-Menü
        m_help = mbar.addMenu("&Hilfe")
        self._create_help_menu(m_help)


    def _create_help_menu(self, menu):
        """Erstellt das Hilfe-Menü."""
        self.act_info_dialog = self._make_action(
            "Info…",
            slot=self._on_show_info_dialog,
            icon=self._toolbar_icon("project_settings"),
            tip="Versionen, Hauptfunktionen und DIN-Prüfstatus anzeigen",
        )
        menu.addAction(self.act_info_dialog)

    def _create_info_menu(self, menu):
        self._create_help_menu(menu)

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
            icon=self._toolbar_icon("new_with_settings"),
            tip="Leeres Projekt anlegen und direkt die Projektparameter öffnen",
        )
        self.act_new_project_wizard = self._make_action(
            "Neues Projekt-Assistent…",
            slot=self._on_new_project_wizard,
            icon=self._toolbar_icon("new_with_settings"),
            tip="Geführter Start: Projekt anlegen und anschließend die wichtigsten Projektparameter durchgehen",
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
            icon=self._toolbar_icon("quit"),
            tip="Anwendung schließen",
        )

        m_new = menu.addMenu(self._std_icon(QStyle.SP_FileIcon), "Neues Projekt")
        m_new.setToolTipsVisible(True)
        m_new.addAction(self.act_new_project)
        m_new.addAction(self.act_new_project_with_settings)
        m_new.addAction(self.act_new_project_wizard)

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
        self.act_project_settings_norm = self._make_action(
            "Normprüfung…",
            slot=self._on_project_settings_norm,
            icon=self._toolbar_icon("project_settings"),
            tip="DIN-Prüfliste und fehlende Quellen direkt öffnen",
        )
        self.act_project_settings_u_values = self._make_action(
            "U-Werte…",
            slot=self._on_project_settings_u_values,
            icon=self._toolbar_icon("project_settings"),
            tip="Projekt-U-Werte für Außenwand, Fenster, Türen, Decken, Boden und Dach öffnen",
        )
        self.act_project_settings_ventilation = self._make_action(
            "Lüftung…",
            slot=self._on_project_settings_ventilation,
            icon=self._toolbar_icon("project_settings"),
            tip="Lüftung, Infiltration, WRG und Aufheizzuschlag öffnen",
        )
        self.act_project_settings_ground = self._make_action(
            "Erdreich…",
            slot=self._on_project_settings_ground,
            icon=self._toolbar_icon("project_settings"),
            tip="Bodenplatte, erdberührte Bauteile und DIN/TS-Faktoren öffnen",
        )
        self.act_project_dashboard = self._make_action(
            "Projekt-Dashboard",
            slot=self._show_project_dashboard,
            icon=self._toolbar_icon("project_settings"),
            tip="Projektstatus, DIN-Ampel, Räume, Bauteile und offene Punkte anzeigen",
        )
        self.act_project_manager = self._make_action(
            "Projektverwaltung…",
            slot=self._on_project_manager,
            icon=self._toolbar_icon("open"),
            tip="Zuletzt verwendete Projekte, Versionen und Backups anzeigen",
        )
        self.act_autowalls = self._make_action(
            "Auto-Wände neu",
            slot=self._rebuild_autowalls_all,
            icon=self._toolbar_icon("auto_walls"),
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
        self.act_show_3d_floor = self._make_action(
            "3D Geschoss",
            slot=self._on_show_3d_floor,
            icon=self._toolbar_icon("view_3d"),
            tip="3D-Darstellung des aktuell gewählten Geschosses anzeigen",
        )
        self.act_show_2d_shell = self._make_action(
            "2D Gebäudehülle+",
            slot=self._on_show_2d_shell,
            icon=self._toolbar_icon("view_3d"),
            tip="2D-Darstellung der Gebäudehülle mit echter Wanddicke, Öffnungen und Dachlinien in der Draufsicht",
        )
        self.act_show_house_side = self._make_action(
            "Haus Seitenansicht",
            slot=self._on_show_house_side_view,
            icon=self._toolbar_icon("view_3d"),
            tip="Seitenansicht des Hauses mit Keller, Erdgeschoss, Obergeschoss und Dach anzeigen",
        )
        self.act_show_3d_shell_gl = self._make_action(
            "3D Gebäudehülle+",
            slot=self._on_show_3d_shell_gl,
            icon=self._toolbar_icon("view_3d"),
            tip="OpenGL-Darstellung der Gebäudehülle mit echter Wanddicke, Fensterlaibungen und Dach aus Firstlinien",
        )
        menu.addAction(self.act_project_settings)
        menu.addAction(self.act_project_settings_norm)
        menu.addAction(self.act_project_dashboard)
        menu.addAction(self.act_project_manager)
        menu.addSeparator()
        menu.addAction(self.act_project_settings_u_values)
        menu.addAction(self.act_project_settings_ventilation)
        menu.addAction(self.act_project_settings_ground)
        menu.addSeparator()
        menu.addAction(self.act_autowalls)
        menu.addAction(self.act_auto_keller)
        menu.addAction(self.act_show_3d_floor)
        menu.addAction(self.act_show_2d_shell)
        menu.addAction(self.act_show_house_side)
        menu.addAction(self.act_show_3d_shell_gl)
        menu.addAction(self.act_show_3d)

    def _create_edit_menu(self, menu):
        """Erstellt das Bearbeiten-Menü."""
        self.act_delete_selection = QAction(self._toolbar_icon("delete_selection"), "Auswahl löschen", self)
        self.act_delete_selection.setShortcut(QKeySequence.Delete)
        self.act_delete_selection.triggered.connect(self._delete_selection)
        self.act_delete_selection.setShortcutContext(Qt.ApplicationShortcut)
        self.addAction(self.act_delete_selection)
        menu.addAction(self.act_delete_selection)

        self.act_delete_windows = QAction(self._toolbar_icon("delete_windows"), "Fenster löschen", self)
        self.act_delete_windows.setShortcut(QKeySequence("Ctrl+Delete"))
        self.act_delete_windows.triggered.connect(self._delete_selected_windows)
        self.act_delete_windows.setShortcutContext(Qt.ApplicationShortcut)
        self.addAction(self.act_delete_windows)
        menu.addAction(self.act_delete_windows)

        self.act_undo_room_op = QAction(self._toolbar_icon("undo"), "Raum-Operation rückgängig", self)
        self.act_undo_room_op.setShortcut(QKeySequence.Undo)
        self.act_undo_room_op.triggered.connect(self._undo_last_room_operation)
        self.act_undo_room_op.setShortcutContext(Qt.ApplicationShortcut)
        self.addAction(self.act_undo_room_op)
        menu.addAction(self.act_undo_room_op)

        self.act_redo_room_op = QAction(self._toolbar_icon("redo"), "Raum-Operation wiederholen", self)
        self.act_redo_room_op.setShortcut(QKeySequence.Redo)
        self.act_redo_room_op.triggered.connect(self._redo_last_room_operation)
        self.act_redo_room_op.setShortcutContext(Qt.ApplicationShortcut)
        self.addAction(self.act_redo_room_op)
        menu.addAction(self.act_redo_room_op)
        menu.addSeparator()

        self.act_comfort_undo = self._make_action(
            "Änderung rückgängig",
            slot=self._comfort_undo,
            shortcut="Ctrl+Alt+Z",
            icon=self._toolbar_icon("undo"),
            tip="Letzte Projektänderung per Snapshot rückgängig machen",
        )
        self.act_comfort_redo = self._make_action(
            "Änderung wiederholen",
            slot=self._comfort_redo,
            shortcut="Ctrl+Alt+Y",
            icon=self._toolbar_icon("redo"),
            tip="Zuletzt rückgängig gemachte Projektänderung wiederholen",
        )
        menu.addAction(self.act_comfort_undo)
        menu.addAction(self.act_comfort_redo)

        self._room_tool_group = QActionGroup(self)
        self._room_tool_group.setExclusive(True)

        self.act_select_tool = self._make_action(
            "Auswahlmodus",
            slot=self._on_toggle_select_mode,
            checkable=True,
            checked=True,
            icon=self._toolbar_icon("select"),
            tip="Objekte selektieren und verschieben, ohne neue Räume zu zeichnen",
        )
        self._room_tool_group.addAction(self.act_select_tool)
        menu.addAction(self.act_select_tool)

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
            checked=False,
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
        self._room_tool_group.addAction(self.act_split_room)
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

        self.act_delete_rooms = QAction(self._toolbar_icon("delete_room"), "Raum löschen", self)
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
        self.act_fit_current_view = self._make_action(
            "Aktuelle Skizze einpassen",
            slot=self._fit_current_plan_view,
            shortcut="Ctrl+0",
            icon=self._toolbar_icon("fit_view"),
            tip="Zentriert und zoomt die aktuelle Skizze in der aktiven Geschossansicht",
        )
        self.act_lbl_outer = self._make_action(
            "Beschriftung Außenwände",
            slot=self._on_toggle_outerwall_labels,
            checkable=True,
            checked=True,
            icon=self._toolbar_icon("label_outer"),
        )
        self.act_lbl_windows = self._make_action(
            "Beschriftung Fenster",
            slot=self._on_toggle_window_labels,
            checkable=True,
            checked=True,
            icon=self._toolbar_icon("label_windows"),
        )
        self.act_lbl_inner = self._make_action(
            "Beschriftung Innenwände",
            slot=self._on_toggle_innerwall_labels,
            checkable=True,
            checked=True,
            icon=self._toolbar_icon("label_inner"),
        )
        self.act_debug_overlay = self._make_action(
            "Debug-Overlay: A_in/A_out/A_ref",
            slot=self._on_toggle_debug_overlay,
            checkable=True,
            checked=False,
            icon=self._toolbar_icon("debug_overlay"),
        )
        self.act_auto_attic_markers = self._make_action(
            "Auto-DG-Markierungen in Grafik",
            slot=self._on_toggle_auto_attic_markers,
            checkable=True,
            checked=True,
            icon=self._toolbar_icon("attic_markers"),
        )
        self.act_area_ref_outer = self._make_action(
            "W/m²: Außenfläche als Bezugsfläche",
            slot=self._on_toggle_area_ref_outer_action,
            checkable=True,
            checked=False,
            icon=self._toolbar_icon("area_ref_outer"),
        )
        self.act_heatmap = self._make_action(
            "Heatmap anzeigen",
            slot=self._on_heat_toggle,
            checkable=True,
            checked=True,
            icon=self._toolbar_icon("heatmap"),
        )
        self.act_autowalls_enabled = self._make_action(
            "Auto-Wände aktiv",
            slot=self._on_autow_toggle,
            checkable=True,
            checked=True,
            icon=self._toolbar_icon("auto_walls"),
            tip="Automatische Außen- und Innenwände ein- oder ausschalten",
        )
        self.act_add_window = self._make_action(
            "Fenster einfügen",
            slot=self._on_add_window_toggle,
            checkable=True,
            checked=False,
            icon=self._toolbar_icon("window_insert"),
            tip="Aktiviert den Modus zum Einfügen von Fenstern",
        )

        menu.addAction(self.act_regen)
        menu.addAction(self.act_fit_current_view)
        menu.addSeparator()
        menu.addAction(self.act_heatmap)
        menu.addAction(self.act_autowalls_enabled)
        menu.addAction(self.act_add_window)
        menu.addSeparator()
        menu.addAction(self.act_lbl_outer)
        menu.addAction(self.act_lbl_windows)
        menu.addAction(self.act_lbl_inner)
        menu.addAction(self.act_debug_overlay)
        menu.addAction(self.act_auto_attic_markers)
        menu.addSeparator()
        menu.addAction(self.act_area_ref_outer)


    def _create_roof_menu(self, menu):
        """Erstellt Menüeinträge speziell für DG-Dach / Giebel."""
        self._roof_profile_actions = {}
        self._roof_profile_group = QActionGroup(self)
        self._roof_profile_group.setExclusive(True)
        self.act_attic_settings = self._make_action(
            "DG-Dachparameter…",
            slot=self._on_attic_project_settings,
            icon=self._toolbar_icon("roof_settings"),
            tip="Öffnet die Projektparameter direkt auf dem Tab DG Dach",
        )
        self.act_open_roof_editor = self._make_action(
            "Dach-Editor…",
            slot=self._open_roof_editor_dialog,
            icon=self._toolbar_icon("roof_settings"),
            tip="Öffnet den separaten Dialog zum Bearbeiten von Dachform, Geometrie und Dachlinien",
        )
        self.act_switch_to_dg = self._make_action(
            "Zum Dachgeschoss wechseln",
            slot=self._on_switch_to_dg_view,
            icon=self._toolbar_icon("go_dg"),
            tip="Aktiviert die DG-Ansicht und passt die aktuelle Skizze ein",
        )
        self.act_refresh_attic_preview = self._make_action(
            "DG-Skizze aktualisieren",
            slot=self._refresh_attic_preview,
            icon=self._toolbar_icon("roof_profile"),
            tip="Aktualisiert die Dach-/Giebelskizze aus den aktuellen Projektparametern",
        )
        self.act_show_attic_dock = self._make_action(
            "DG-Dock anzeigen",
            slot=self._on_toggle_attic_dock,
            checkable=True,
            checked=True,
            icon=self._toolbar_icon("roof_profile"),
            tip="Blendet das Dock DG Dach / Giebel ein oder aus",
        )
        self.act_auto_attic_markers.setIcon(self._toolbar_icon("attic_markers"))

        roof_menu = menu.addMenu("Dachprofil wählen")
        for label, key in (("Satteldach", "satteldach"), ("Pultdach", "pultdach"), ("Walmdach", "walmdach"), ("Krüppelwalmdach", "krueppelwalmdach"), ("Flachdach", "flachdach"), ("Winkel-/Kehldach", "winkeldach")):
            act = self._make_action(
                label,
                slot=lambda checked=False, rt=key: self._set_attic_roof_type(rt),
                checkable=True,
                checked=(key == "satteldach"),
                icon=self._toolbar_icon("roof_profile"),
                tip=f"Setzt das Dachprofil auf {label}",
            )
            self._roof_profile_group.addAction(act)
            roof_menu.addAction(act)
            self._roof_profile_actions[key] = act

        self._facade_material_actions = {}
        self._facade_material_group = QActionGroup(self)
        self._facade_material_group.setExclusive(True)
        facade_menu = menu.addMenu("3D-Material wählen")
        self._roof_material_actions = {}
        self._roof_material_group = QActionGroup(self)
        self._roof_material_group.setExclusive(True)
        roof_material_menu = menu.addMenu("Dachmaterial wählen")
        for key, label in (("ziegel", "Ziegel"),):
            act = self._make_action(
                label,
                slot=lambda checked=False, mt=key: self._set_roof_material(mt),
                checkable=True,
                checked=False,
                icon=self._toolbar_icon("roof_profile"),
                tip=f"Setzt das 3D-Dachmaterial auf {label}",
            )
            self._roof_material_group.addAction(act)
            roof_material_menu.addAction(act)
            self._roof_material_actions[key] = act
        for label, key in (("Klinker", "klinker"), ("Putz", "putz"), ("Holz", "holz"), ("Beton", "beton")):
            act = self._make_action(
                label,
                slot=lambda checked=False, mt=key: self._set_facade_material(mt),
                checkable=True,
                checked=(key == "klinker"),
                icon=self._toolbar_icon("roof_profile"),
                tip=f"Setzt das 3D-Fassadenmaterial auf {label}",
            )
            self._facade_material_group.addAction(act)
            facade_menu.addAction(act)
            self._facade_material_actions[key] = act

        menu.addAction(self.act_open_roof_editor)
        menu.addSeparator()
        menu.addAction(self.act_attic_settings)
        menu.addAction(self.act_switch_to_dg)
        menu.addAction(self.act_refresh_attic_preview)
        menu.addAction(self.act_fit_current_view)
        menu.addSeparator()
        menu.addAction(self.act_show_attic_dock)
        menu.addAction(self.act_auto_attic_markers)

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
                self.act_project_settings_norm,
                self.act_project_dashboard,
                self.act_project_manager,
                self.act_project_settings_u_values,
                self.act_project_settings_ventilation,
                self.act_project_settings_ground,
                self.act_auto_keller,
                self.act_show_house_side,
                self.act_show_3d_floor,
                self.act_show_3d_shell_gl,
                self.act_show_3d,
                self.act_regen,
                self.act_fit_current_view,
                self.act_area_ref_outer,
            ]),
            ("Werkzeuge", [
                self.act_select_tool,
                self.act_rect_room,
                self.act_l_room,
                self.act_polygon_room,
                self.act_split_room,
                self.act_add_window,
                self.act_autowalls_enabled,
            ]),
            ("Bearbeiten", [
                self.act_comfort_undo,
                self.act_comfort_redo,
                self.act_merge_rooms,
                self.act_subtract_rooms,
                self.act_delete_selection,
            ]),
        ]

        # Auto-Wände bewusst als latched Toggle in der Werkzeuge-Gruppe platzieren:
        # Die Funktion gehört zum Geometrie-/Zeichenworkflow und soll daher
        # direkt bei Auswahl-, Raum- und Fensterwerkzeugen erreichbar sein.
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

        self.tb_roof = QToolBar("Dachgestaltung", self)
        self.tb_roof.setObjectName("toolbar_roof")
        self.tb_roof.setMovable(False)
        self.tb_roof.setFloatable(False)
        self.tb_roof.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.tb_roof.setIconSize(QSize(22, 22))
        self.tb_roof.setToolTip("Werkzeuge für DG-Dach, Giebel und Skizzenansicht")
        self.addToolBar(Qt.TopToolBarArea, self.tb_roof)

        self.tb_roof.addWidget(QLabel("Dachprofil:"))
        self.cb_roof_profile_quick = QComboBox()
        self.cb_roof_profile_quick.addItems(["Satteldach", "Pultdach", "Walmdach", "Krüppelwalmdach", "Flachdach"])
        self.cb_roof_profile_quick.setToolTip("Schnellauswahl des Dachprofils")
        self.cb_roof_profile_quick.currentTextChanged.connect(self._on_roof_profile_changed)
        self.tb_roof.addWidget(self.cb_roof_profile_quick)
        self.tb_roof.addSeparator()
        self.tb_roof.addWidget(QLabel("3D-Material:"))
        self.cb_facade_material_quick = QComboBox()
        self.cb_facade_material_quick.addItems(["Klinker", "Putz", "Holz", "Beton"])
        self.cb_facade_material_quick.setToolTip("Schnellauswahl des 3D-Fassadenmaterials")
        self.cb_facade_material_quick.currentTextChanged.connect(self._on_facade_material_changed)
        self.tb_roof.addWidget(self.cb_facade_material_quick)
        self.tb_roof.addSeparator()
        self.tb_roof.addWidget(QLabel("Dachmaterial:"))
        self.cb_roof_material_quick = QComboBox()
        self.cb_roof_material_quick.addItems(["Ziegel"])
        self.cb_roof_material_quick.setToolTip("Schnellauswahl des 3D-Dachmaterials")
        self.cb_roof_material_quick.currentTextChanged.connect(self._on_roof_material_changed)
        self.tb_roof.addWidget(self.cb_roof_material_quick)
        self.tb_roof.addSeparator()

        roof_actions = [
            self.act_attic_settings,
            self.act_switch_to_dg,
            self.act_refresh_attic_preview,
            self.act_show_attic_dock,
            self.act_auto_attic_markers,
            self.act_fit_current_view,
        ]
        for action in roof_actions:
            if action is None:
                continue
            self.tb_roof.addAction(action)

        for btn in self.tb_roof.findChildren(QToolButton):
            btn.setAutoRaise(True)
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        if hasattr(self, "_sync_roof_profile_widgets"):
            self._sync_roof_profile_widgets()
        if hasattr(self, "_sync_facade_material_widgets"):
            self._sync_facade_material_widgets()
        if hasattr(self, "_sync_roof_material_widgets"):
            self._sync_roof_material_widgets()


    def _create_central_widget(self):
        """Erstellt das zentrale Widget nur mit Geschoss-Tabs; Eigenschaften/Elemente liegen in DockWidgets."""
        cw = QWidget()
        cw.setMinimumWidth(0)
        cw.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
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
        self.tabs.setMinimumWidth(0)
        self.tabs.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
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
        control_bar.setMinimumWidth(0)
        control_bar.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        control_lay = QHBoxLayout(control_bar)
        control_lay.setContentsMargins(10, 8, 10, 8)
        control_lay.setSpacing(12)

        lbl_hint = QLabel("Planansicht")
        lbl_hint.setObjectName("planInfoTitle")
        lbl_hint.setMinimumWidth(0)
        lbl_sub = QLabel("Auswahlmodus zum Selektieren, dazu Werkzeuge für Rechteck-, L- und Polygonräume, Trennen, Verschmelzen, Subtrahieren und Fenster")
        lbl_sub.setObjectName("planInfoText")
        lbl_sub.setMinimumWidth(0)
        lbl_sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        control_lay.addWidget(lbl_hint)
        control_lay.addWidget(lbl_sub, 1)

        left.addWidget(control_bar)

        return left

    def _create_roof_editor_panel(self, parent=None):
        page = QWidget(parent)
        root = QVBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("roofEditorHero")
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(14, 12, 14, 12)
        hero_lay.setSpacing(8)
        hero_head = QHBoxLayout()
        hero_head.setSpacing(8)
        hero_title = QLabel("Dach-Editor")
        hero_title.setObjectName("roofEditorTitle")
        hero_head.addWidget(hero_title)
        hero_head.addStretch(1)
        self.btn_roof_tab_help = QPushButton("Hilfe")
        self.btn_roof_tab_help.setObjectName("roofEditorHelpButton")
        self.btn_roof_tab_help.setToolTip("Öffnet eine ausführliche Hilfe zu Dachformen, Parametern, Dachlinien und Vorschau")
        self.btn_roof_tab_help.clicked.connect(self._open_roof_help_dialog)
        hero_head.addWidget(self.btn_roof_tab_help)
        hero_lay.addLayout(hero_head)
        hero_sub = QLabel("Linke Parameter-Spalte für Geometrie und Aktionen, rechte Seite mit Live-Dachvorschau und Linieneditor.")
        hero_sub.setWordWrap(True)
        hero_sub.setObjectName("roofEditorText")
        hero_lay.addWidget(hero_sub)
        root.addWidget(hero)

        summary_wrap = QFrame()
        summary_wrap.setObjectName("roofEditorSummaryWrap")
        summary_grid = QGridLayout(summary_wrap)
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setHorizontalSpacing(12)
        summary_grid.setVerticalSpacing(12)
        self.lbl_roof_metric_area = QLabel("–")
        self.lbl_roof_metric_facets = QLabel("–")
        self.lbl_roof_metric_lines = QLabel("–")
        self.lbl_roof_metric_height = QLabel("–")
        summary_grid.addWidget(self._create_roof_editor_metric_card("Dachfläche", self.lbl_roof_metric_area, "roofMetricAreaCard"), 0, 0)
        summary_grid.addWidget(self._create_roof_editor_metric_card("Facetten", self.lbl_roof_metric_facets, "roofMetricFacetCard"), 0, 1)
        summary_grid.addWidget(self._create_roof_editor_metric_card("Dachlinien", self.lbl_roof_metric_lines, "roofMetricLineCard"), 0, 2)
        summary_grid.addWidget(self._create_roof_editor_metric_card("Gesamthöhe", self.lbl_roof_metric_height, "roofMetricHeightCard"), 0, 3)
        root.addWidget(summary_wrap)

        balance_wrap = QFrame()
        balance_wrap.setObjectName("roofEditorBalanceWrap")
        balance_grid = QGridLayout(balance_wrap)
        balance_grid.setContentsMargins(12, 10, 12, 10)
        balance_grid.setHorizontalSpacing(16)
        balance_grid.setVerticalSpacing(6)
        balance_title = QLabel("Live-Bilanz")
        balance_title.setObjectName("roofEditorSectionTitle")
        balance_grid.addWidget(balance_title, 0, 0, 1, 4)
        self.lbl_roof_balance_gross = QLabel("–")
        self.lbl_roof_balance_openings = QLabel("–")
        self.lbl_roof_balance_effective = QLabel("–")
        self.lbl_roof_balance_heat = QLabel("–")
        for col, (title, label) in enumerate((
            ("Dach brutto", self.lbl_roof_balance_gross),
            ("Öffnungen", self.lbl_roof_balance_openings),
            ("Dach wirksam", self.lbl_roof_balance_effective),
            ("Dach Φ", self.lbl_roof_balance_heat),
        )):
            t = QLabel(title)
            t.setObjectName("roofEditorMetricTitle")
            label.setObjectName("roofEditorMetricValue")
            balance_grid.addWidget(t, 1, col)
            balance_grid.addWidget(label, 2, col)
        self.lbl_roof_validation = QLabel("–")
        self.lbl_roof_validation.setObjectName("roofEditorValidation")
        self.lbl_roof_validation.setWordWrap(True)
        balance_grid.addWidget(self.lbl_roof_validation, 3, 0, 1, 4)
        root.addWidget(balance_wrap)

        content_splitter = QSplitter(Qt.Horizontal, page)
        content_splitter.setObjectName("roofEditorSplitter")
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setOpaqueResize(True)
        root.addWidget(content_splitter, 1)

        left_wrap = QFrame()
        left_wrap.setObjectName("roofEditorParamWrap")
        left_wrap.setMinimumWidth(280)
        left_wrap.setMaximumWidth(520)
        left_wrap.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_lay = QVBoxLayout(left_wrap)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(12)
        content_splitter.addWidget(left_wrap)
        self.roof_editor_param_tabs = QTabWidget()
        self.roof_editor_param_tabs.setObjectName("roofEditorParamTabs")
        left_lay.addWidget(self.roof_editor_param_tabs, 1)

        form_wrap = QFrame()
        form_wrap.setObjectName("roofEditorFormWrap")
        form_lay = QVBoxLayout(form_wrap)
        form_lay.setContentsMargins(12, 12, 12, 12)
        form_lay.setSpacing(8)
        form_title = QLabel("Parameter")
        form_title.setObjectName("roofEditorSectionTitle")
        form_lay.addWidget(form_title)
        form_hint = QLabel("Dachprofil und Grundparameter wirken sofort auf die Vorschau und die DG-Geometrie.")
        form_hint.setWordWrap(True)
        form_hint.setObjectName("roofEditorText")
        form_lay.addWidget(form_hint)

        form = QFormLayout()
        form.setContentsMargins(0, 8, 0, 0)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)

        self.cb_roof_tab_profile = QComboBox()
        self.cb_roof_tab_profile.addItems(["Satteldach", "Pultdach", "Walmdach", "Krüppelwalmdach", "Flachdach", "Winkel-/Kehldach"])
        self.cb_roof_tab_profile.currentTextChanged.connect(self._on_roof_editor_profile_changed)

        self.cb_roof_tab_ridge = QComboBox()
        self.cb_roof_tab_ridge.addItems(["First längs", "First quer"])
        self.cb_roof_tab_ridge.currentTextChanged.connect(self._on_roof_editor_ridge_changed)

        self.sp_roof_tab_pitch = QDoubleSpinBox()
        self.sp_roof_tab_pitch.setRange(0.0, 85.0)
        self.sp_roof_tab_pitch.setDecimals(1)
        self.sp_roof_tab_pitch.setSuffix(" °")
        self.sp_roof_tab_pitch.valueChanged.connect(self._on_roof_editor_numeric_changed)

        self.sp_roof_tab_knee = QDoubleSpinBox()
        self.sp_roof_tab_knee.setRange(0.0, 5.0)
        self.sp_roof_tab_knee.setDecimals(2)
        self.sp_roof_tab_knee.setSuffix(" m")
        self.sp_roof_tab_knee.valueChanged.connect(self._on_roof_editor_numeric_changed)

        self.sp_roof_tab_overhang = QDoubleSpinBox()
        self.sp_roof_tab_overhang.setRange(0.0, 3.0)
        self.sp_roof_tab_overhang.setDecimals(2)
        self.sp_roof_tab_overhang.setSuffix(" m")
        self.sp_roof_tab_overhang.valueChanged.connect(self._on_roof_editor_numeric_changed)

        form.addRow("Dachform", self._wrap_roof_editor_field_with_help(self.cb_roof_tab_profile, "roof_types", "Erklärung der Dachformen und Mini-Renderings öffnen"))
        form.addRow("Firstausrichtung", self._wrap_roof_editor_field_with_help(self.cb_roof_tab_ridge, "ridge", "Hilfe zur Firstausrichtung öffnen"))
        form.addRow("Dachneigung", self._wrap_roof_editor_field_with_help(self.sp_roof_tab_pitch, "pitch", "Hilfe zur Dachneigung öffnen"))
        form.addRow("Kniestock", self._wrap_roof_editor_field_with_help(self.sp_roof_tab_knee, "knee", "Hilfe zum Kniestock öffnen"))
        form.addRow("Dachüberstand", self._wrap_roof_editor_field_with_help(self.sp_roof_tab_overhang, "overhang", "Hilfe zum Dachüberstand öffnen"))
        form_lay.addLayout(form)
        self.roof_editor_param_tabs.addTab(form_wrap, "Geometrie")

        dormer_wrap = QFrame()
        dormer_wrap.setObjectName("roofEditorDormerWrap")
        dormer_lay = QVBoxLayout(dormer_wrap)
        dormer_lay.setContentsMargins(12, 12, 12, 12)
        dormer_lay.setSpacing(8)
        dormer_head = QHBoxLayout()
        dormer_head.setSpacing(8)
        dormer_title = QLabel("Gauben")
        dormer_title.setObjectName("roofEditorSectionTitle")
        dormer_head.addWidget(dormer_title)
        dormer_head.addStretch(1)
        self.lbl_roof_dormer_count = QLabel("0 Gauben")
        self.lbl_roof_dormer_count.setObjectName("roofEditorBadge")
        dormer_head.addWidget(self.lbl_roof_dormer_count)
        dormer_lay.addLayout(dormer_head)
        dormer_desc = QLabel("Hier können Sie einzelne Gauben direkt im Dach-Dialog anlegen, bearbeiten und löschen. Die Vorschau und die DG-Geometrie werden nach jeder Änderung aktualisiert.")
        dormer_desc.setWordWrap(True)
        dormer_desc.setObjectName("roofEditorText")
        dormer_lay.addWidget(dormer_desc)
        self.lst_roof_tab_dormers = QListWidget()
        self.lst_roof_tab_dormers.setObjectName("roofTabDormerList")
        self.lst_roof_tab_dormers.currentRowChanged.connect(self._on_roof_editor_dormer_selected)
        dormer_lay.addWidget(self.lst_roof_tab_dormers, 1)
        dormer_btn_row = QHBoxLayout()
        dormer_btn_row.setSpacing(8)
        self.btn_roof_tab_add_dormer = QPushButton("Gaube hinzufügen")
        self.btn_roof_tab_add_dormer.clicked.connect(self._add_roof_editor_dormer)
        dormer_btn_row.addWidget(self.btn_roof_tab_add_dormer)
        self.btn_roof_tab_edit_dormer = QPushButton("Bearbeiten")
        self.btn_roof_tab_edit_dormer.clicked.connect(self._edit_selected_roof_editor_dormer)
        dormer_btn_row.addWidget(self.btn_roof_tab_edit_dormer)
        self.btn_roof_tab_delete_dormer = QPushButton("Löschen")
        self.btn_roof_tab_delete_dormer.clicked.connect(self._delete_selected_roof_editor_dormer)
        dormer_btn_row.addWidget(self.btn_roof_tab_delete_dormer)
        dormer_lay.addLayout(dormer_btn_row)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.btn_roof_tab_place_dormer = QPushButton("Grafisch platzieren")
        self.btn_roof_tab_place_dormer.setCheckable(True)
        self.btn_roof_tab_place_dormer.setToolTip("Aktiviert die Platzierung in der Dachvorschau. Ohne Auswahl wird per Klick eine neue Gaube eingefügt. Mit Auswahl kann die markierte Gaube per Drag&Drop verschoben oder über Resize-Griffe in Breite und Tiefe angepasst werden.")
        self.btn_roof_tab_place_dormer.toggled.connect(self._on_toggle_roof_editor_dormer_place_mode)
        mode_row.addWidget(self.btn_roof_tab_place_dormer)
        self.btn_roof_tab_draw_dormer = QPushButton("Gaube zeichnen")
        self.btn_roof_tab_draw_dormer.setCheckable(True)
        self.btn_roof_tab_draw_dormer.setToolTip("CAD-Modus: Im Dachplan klicken und ziehen, um die Breite einer neuen Gaube direkt grafisch aufzuziehen.")
        self.btn_roof_tab_draw_dormer.toggled.connect(self._on_toggle_roof_editor_dormer_draw_mode)
        mode_row.addWidget(self.btn_roof_tab_draw_dormer)
        self.btn_roof_tab_place_window = QPushButton("Dachfenster platzieren")
        self.btn_roof_tab_place_window.setCheckable(True)
        self.btn_roof_tab_place_window.setToolTip("Aktiviert die grafische Dachfenster-Platzierung im Dachplan. Jeder Klick fügt ein Dachfenster auf der gewählten Dachseite hinzu.")
        self.btn_roof_tab_place_window.toggled.connect(self._on_toggle_roof_editor_window_place_mode)
        mode_row.addWidget(self.btn_roof_tab_place_window)
        dormer_lay.addLayout(mode_row)
        self.lbl_roof_dormer_place_hint = QLabel("Tipp: 'Gaube zeichnen' für Click+Drag-Erzeugung verwenden oder 'Grafisch platzieren' für Klickplatzierung, Verschieben und Resize der markierten Gaube.")
        self.lbl_roof_dormer_place_hint.setWordWrap(True)
        self.lbl_roof_dormer_place_hint.setObjectName("roofEditorText")
        dormer_lay.addWidget(self.lbl_roof_dormer_place_hint)
        self.roof_editor_param_tabs.addTab(dormer_wrap, "Gauben")

        actions_wrap = QFrame()
        actions_wrap.setObjectName("roofEditorActionsWrap")
        actions_lay = QVBoxLayout(actions_wrap)
        actions_lay.setContentsMargins(12, 12, 12, 12)
        actions_lay.setSpacing(8)
        actions_title = QLabel("Aktionen")
        actions_title.setObjectName("roofEditorSectionTitle")
        actions_lay.addWidget(actions_title)
        self.btn_roof_tab_open_settings = QPushButton("Weitere Projektparameter")
        self.btn_roof_tab_open_settings.clicked.connect(self._on_attic_project_settings)
        actions_lay.addWidget(self.btn_roof_tab_open_settings)
        self.btn_roof_tab_to_dg = QPushButton("Zum DG")
        self.btn_roof_tab_to_dg.clicked.connect(self._on_switch_to_dg_view)
        actions_lay.addWidget(self.btn_roof_tab_to_dg)
        self.btn_roof_tab_refresh = QPushButton("Vorschau aktualisieren")
        self.btn_roof_tab_refresh.clicked.connect(self._refresh_attic_preview)
        actions_lay.addWidget(self.btn_roof_tab_refresh)
        self.btn_roof_tab_help_secondary = QPushButton("Ausführliche Hilfe")
        self.btn_roof_tab_help_secondary.clicked.connect(self._open_roof_help_dialog)
        actions_lay.addWidget(self.btn_roof_tab_help_secondary)
        actions_hint = QLabel("Änderungen werden direkt in project_cfg.attic übernommen. Dachlinien und Geometrie bleiben synchron.")
        actions_hint.setWordWrap(True)
        actions_hint.setObjectName("roofEditorText")
        actions_lay.addWidget(actions_hint)
        self.roof_editor_param_tabs.addTab(actions_wrap, "Aktionen")

        right_wrap = QWidget()
        right_col = QVBoxLayout(right_wrap)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(12)
        content_splitter.addWidget(right_wrap)
        content_splitter.setStretchFactor(0, 0)
        content_splitter.setStretchFactor(1, 1)
        content_splitter.setSizes([360, 900])
        self.roof_editor_right_splitter = QSplitter(Qt.Vertical, right_wrap)
        self.roof_editor_right_splitter.setObjectName("roofEditorRightSplitter")
        self.roof_editor_right_splitter.setChildrenCollapsible(False)
        self.roof_editor_right_splitter.setOpaqueResize(True)
        right_col.addWidget(self.roof_editor_right_splitter, 1)

        preview_wrap = QFrame()
        preview_wrap.setObjectName("roofEditorPreviewWrap")
        preview_wrap.setMinimumHeight(260)
        preview_lay = QVBoxLayout(preview_wrap)
        preview_lay.setContentsMargins(12, 12, 12, 12)
        preview_lay.setSpacing(8)
        preview_title = QLabel("Live-Dachvorschau")
        preview_title.setObjectName("roofEditorSectionTitle")
        preview_lay.addWidget(preview_title)
        preview_desc = QLabel("Querschnitt und Dachplan werden aus den aktuellen Projektdaten berechnet. Bei aktivierter Gauben-Platzierung kann im Dachplan direkt per Mausklick eingefügt werden. Ausgewählte Gauben lassen sich per Drag&Drop verschieben und über Resize-Griffe direkt grafisch in Breite und Tiefe anpassen.")
        preview_desc.setWordWrap(True)
        preview_desc.setObjectName("roofEditorText")
        preview_lay.addWidget(preview_desc)
        self.roof_editor_preview_panel = AtticSketchPanel(self)
        self.roof_editor_preview_panel.planClicked.connect(self._on_roof_editor_preview_plan_clicked)
        self.roof_editor_preview_panel.dormerDrawFinished.connect(self._on_roof_editor_dormer_draw_finished)
        self.roof_editor_preview_panel.dormerDragStarted.connect(self._on_roof_editor_dormer_drag_started)
        self.roof_editor_preview_panel.dormerDragMoved.connect(self._on_roof_editor_dormer_drag_moved)
        self.roof_editor_preview_panel.dormerDragFinished.connect(self._on_roof_editor_dormer_drag_finished)
        self.roof_editor_preview_panel.dormerResizeStarted.connect(self._on_roof_editor_dormer_resize_started)
        self.roof_editor_preview_panel.dormerResizeMoved.connect(self._on_roof_editor_dormer_resize_moved)
        self.roof_editor_preview_panel.dormerResizeFinished.connect(self._on_roof_editor_dormer_resize_finished)
        self.roof_editor_preview_panel.setMinimumHeight(240)
        self.roof_editor_preview_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_lay.addWidget(self.roof_editor_preview_panel, 1)
        self.roof_editor_right_splitter.addWidget(preview_wrap)

        facet_wrap = QFrame()
        facet_wrap.setObjectName("roofEditorFacetWrap")
        facet_lay = QVBoxLayout(facet_wrap)
        facet_lay.setContentsMargins(12, 12, 12, 12)
        facet_lay.setSpacing(8)
        facet_header = QHBoxLayout()
        facet_header.setSpacing(8)
        facet_title = QLabel("Dachflächen / Facetten")
        facet_title.setObjectName("roofEditorSectionTitle")
        facet_header.addWidget(facet_title)
        facet_header.addStretch(1)
        self.lbl_roof_facet_count = QLabel("0 Facetten")
        self.lbl_roof_facet_count.setObjectName("roofEditorBadge")
        facet_header.addWidget(self.lbl_roof_facet_count)
        facet_lay.addLayout(facet_header)
        facet_desc = QLabel("Automatisch berechnete Dachflächen aus Grundform, Firstlage und zusätzlichen Dachlinien.")
        facet_desc.setWordWrap(True)
        facet_desc.setObjectName("roofEditorText")
        facet_lay.addWidget(facet_desc)
        self.lst_roof_tab_facets = QListWidget()
        self.lst_roof_tab_facets.setObjectName("roofTabFacetList")
        facet_lay.addWidget(self.lst_roof_tab_facets, 1)
        self.roof_editor_right_splitter.addWidget(facet_wrap)

        line_wrap = QFrame()
        line_wrap.setObjectName("roofEditorLineWrap")
        line_lay = QVBoxLayout(line_wrap)
        line_lay.setContentsMargins(12, 12, 12, 12)
        line_lay.setSpacing(8)

        line_header = QHBoxLayout()
        line_header.setSpacing(8)
        line_title = QLabel("Dachlinien-Editor")
        line_title.setObjectName("roofEditorSectionTitle")
        line_header.addWidget(line_title)
        line_header.addStretch(1)
        line_header.addWidget(QLabel("Linientyp:"))
        self.cb_roof_tab_line_kind = QComboBox()
        self.cb_roof_tab_line_kind.addItems(["First", "Grat", "Kehle"])
        self.cb_roof_tab_line_kind.currentTextChanged.connect(self._on_roof_editor_line_kind_changed)
        line_header.addWidget(self.cb_roof_tab_line_kind)
        line_lay.addLayout(line_header)

        self.roof_line_editor_tab = RoofLineEditorWidget(self)
        self.roof_line_editor_tab.on_lines_changed = self._on_roof_editor_lines_changed
        line_lay.addWidget(self.roof_line_editor_tab, 1)

        line_hint = QLabel("Draufsicht: erster Klick = Start, zweiter Klick = Ende. Bestehende Linien können direkt ausgewählt und gelöscht werden.")
        line_hint.setWordWrap(True)
        line_hint.setObjectName("roofEditorText")
        line_lay.addWidget(line_hint)

        self.lbl_roof_line_count = QLabel("0 Linien")
        self.lbl_roof_line_count.setObjectName("roofEditorBadge")
        line_lay.addWidget(self.lbl_roof_line_count, 0, Qt.AlignRight)

        list_row = QHBoxLayout()
        list_row.setSpacing(10)
        self.lst_roof_tab_lines = QListWidget()
        self.lst_roof_tab_lines.setObjectName("roofTabLineList")
        self.lst_roof_tab_lines.currentRowChanged.connect(self._on_roof_editor_line_selected)
        list_row.addWidget(self.lst_roof_tab_lines, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(8)
        self.btn_roof_tab_delete_line = QPushButton("Linie löschen")
        self.btn_roof_tab_delete_line.clicked.connect(self._delete_selected_roof_editor_line)
        btn_col.addWidget(self.btn_roof_tab_delete_line)
        self.btn_roof_tab_clear_lines = QPushButton("Alle löschen")
        self.btn_roof_tab_clear_lines.clicked.connect(self._clear_roof_editor_lines)
        btn_col.addWidget(self.btn_roof_tab_clear_lines)
        btn_col.addStretch(1)
        list_row.addLayout(btn_col)
        line_lay.addLayout(list_row)
        self.roof_editor_right_splitter.addWidget(line_wrap)
        self.roof_editor_right_splitter.setStretchFactor(0, 4)
        self.roof_editor_right_splitter.setStretchFactor(1, 1)
        self.roof_editor_right_splitter.setStretchFactor(2, 2)
        self.roof_editor_right_splitter.setSizes([420, 160, 260])

        if hasattr(self, "_sync_roof_editor_tab_widgets"):
            self._sync_roof_editor_tab_widgets()
        return page

    def _create_roof_editor_metric_card(self, title: str, value_label: QLabel, object_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("roofEditorMetricTitle")
        value_label.setObjectName("roofEditorMetricValue")
        lay.addWidget(title_lbl)
        lay.addWidget(value_label)
        return card

    def _open_roof_editor_dialog(self):
        dlg = getattr(self, "_roof_editor_dialog", None)
        if dlg is None:
            dlg = QDialog(self)
            dlg.setWindowTitle("Dach-Editor")
            dlg.setModal(False)
            dlg.resize(1280, 820)
            dlg.setMinimumSize(780, 560)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)

            scroll = QScrollArea(dlg)
            scroll.setObjectName("roofEditorDialogScrollArea")
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setFrameShape(QFrame.NoFrame)

            container = QWidget(scroll)
            container_lay = QVBoxLayout(container)
            container_lay.setContentsMargins(0, 0, 0, 0)
            container_lay.setSpacing(0)

            self.roof_editor_panel = self._create_roof_editor_panel(container)
            self.roof_editor_panel.setMinimumSize(720, 560)
            container_lay.addWidget(self.roof_editor_panel)
            container_lay.addStretch(1)
            scroll.setWidget(container)

            lay.addWidget(scroll)
            self._roof_editor_dialog_scroll = scroll
            self._roof_editor_dialog = dlg
        if hasattr(self, "_sync_roof_editor_tab_widgets"):
            self._sync_roof_editor_tab_widgets()
        try:
            self._roof_editor_dialog.show()
            self._roof_editor_dialog.raise_()
            self._roof_editor_dialog.activateWindow()
        except Exception:
            pass

    def _wrap_roof_editor_field_with_help(self, widget, section_key: str, tooltip: str) -> QWidget:
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(widget, 1)
        btn = QToolButton(wrap)
        btn.setText("?")
        btn.setAutoRaise(True)
        btn.setToolTip(tooltip)
        btn.clicked.connect(lambda _=False, key=section_key: self._open_roof_help_dialog(key))
        lay.addWidget(btn, 0, Qt.AlignTop)
        return wrap

    def _create_roof_type_mini_card(self, title: str, kind: str, caption: str, example_key: str | None = None) -> QFrame:
        box = RoofExampleCard()
        box.setObjectName("roofHelpMiniCard")
        box.setCursor(Qt.PointingHandCursor if example_key else Qt.ArrowCursor)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        lbl_title = QLabel(title)
        lbl_title.setObjectName("roofEditorSectionTitle")
        lbl_title.setWordWrap(True)
        lay.addWidget(lbl_title)
        img = QLabel()
        img.setAlignment(Qt.AlignCenter)
        img.setPixmap(self._make_roof_help_pixmap(kind, QSize(180, 92)))
        lay.addWidget(img)
        lbl_caption = QLabel(caption)
        lbl_caption.setObjectName("roofEditorText")
        lbl_caption.setWordWrap(True)
        lay.addWidget(lbl_caption)
        if example_key:
            hint = QLabel("Klick oder Button lädt ein Beispiel direkt in den Dach-Editor.")
            hint.setObjectName("roofEditorText")
            hint.setWordWrap(True)
            lay.addWidget(hint)
            btn = QPushButton("Beispiel laden")
            btn.clicked.connect(lambda _=False, key=example_key: self._apply_roof_example(key))
            lay.addWidget(btn)
            box.clicked.connect(lambda key=example_key: self._apply_roof_example(key))
        return box

    def _roof_example_presets(self) -> dict[str, dict]:
        return {
            "gable_standard": {
                "title": "Satteldach – Standard",
                "roof_type": "satteldach",
                "ridge_orientation": "length",
                "roof_pitch_deg": 38.0,
                "knee_wall_height_m": 1.00,
                "roof_overhang_m": 0.35,
                "help_section": "roof_types",
                "description": "Klassisches Satteldach mit mittlerer Neigung und moderatem Überstand.",
            },
            "shed_compact": {
                "title": "Pultdach – Kompakt",
                "roof_type": "pultdach",
                "ridge_orientation": "length",
                "roof_pitch_deg": 18.0,
                "knee_wall_height_m": 0.80,
                "roof_overhang_m": 0.25,
                "help_section": "roof_types",
                "description": "Einfaches Pultdach mit klarer Entwässerungsrichtung und geringer Dachhöhe.",
            },
            "hip_balanced": {
                "title": "Walmdach – Ausgewogen",
                "roof_type": "walmdach",
                "ridge_orientation": "length",
                "roof_pitch_deg": 30.0,
                "knee_wall_height_m": 0.70,
                "roof_overhang_m": 0.40,
                "help_section": "roof_types",
                "description": "Ausgewogenes Walmdach mit ruhiger Dachsilhouette und vier geneigten Seiten.",
            },
            "halfhip_family": {
                "title": "Krüppelwalmdach – Wohnhaus",
                "roof_type": "krueppelwalmdach",
                "ridge_orientation": "length",
                "roof_pitch_deg": 42.0,
                "knee_wall_height_m": 1.10,
                "roof_overhang_m": 0.38,
                "help_section": "roof_types",
                "description": "Typisches Wohnhausdach mit teilweiser Abwalmung an den Stirnseiten.",
            },
            "flat_modern": {
                "title": "Flachdach – Modern",
                "roof_type": "flachdach",
                "ridge_orientation": "length",
                "roof_pitch_deg": 2.0,
                "knee_wall_height_m": 0.00,
                "roof_overhang_m": 0.12,
                "help_section": "roof_types",
                "description": "Sehr flaches Dach für moderne Baukörper und kompakte Dachaufbauten.",
            },
            "valley_lshape": {
                "title": "Winkel-/Kehldach – L-Form",
                "roof_type": "winkeldach",
                "ridge_orientation": "length",
                "roof_pitch_deg": 35.0,
                "knee_wall_height_m": 0.95,
                "roof_overhang_m": 0.32,
                "help_section": "lines",
                "description": "Ausgangspunkt für L-förmige Baukörper mit Kehlen oder zusammengesetzten Teilflächen.",
            },
        }

    def _apply_roof_example(self, example_key: str) -> None:
        example = self._roof_example_presets().get(str(example_key))
        if not example:
            return
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        if attic is None:
            return

        attic.roof_type = str(example.get("roof_type", getattr(attic, "roof_type", "satteldach")))
        attic.ridge_orientation = str(example.get("ridge_orientation", getattr(attic, "ridge_orientation", "length")))
        attic.roof_pitch_deg = float(example.get("roof_pitch_deg", getattr(attic, "roof_pitch_deg", 35.0) or 0.0))
        attic.knee_wall_height_m = float(example.get("knee_wall_height_m", getattr(attic, "knee_wall_height_m", 1.0) or 0.0))
        overhang = float(example.get("roof_overhang_m", getattr(attic, "roof_overhang_m", 0.30) or 0.0))
        attic.roof_overhang_m = overhang
        attic.eave_overhang_m = overhang
        attic.gable_overhang_m = overhang

        if hasattr(self, "_persist_project_cfg_if_possible"):
            self._persist_project_cfg_if_possible()
        if hasattr(self, "_recompute_and_redraw"):
            self._recompute_and_redraw()
        if hasattr(self, "_refresh_attic_preview"):
            self._refresh_attic_preview()
        if hasattr(self, "_sync_roof_editor_tab_widgets"):
            self._sync_roof_editor_tab_widgets()

        try:
            self._open_roof_editor_dialog()
        except Exception:
            pass
        try:
            self._open_roof_help_dialog(str(example.get("help_section") or "roof_types"))
        except Exception:
            pass
        try:
            self.statusBar().showMessage(f"Beispiel geladen: {example.get('title', 'Dachbeispiel')}", 3200)
        except Exception:
            pass

    def _scroll_roof_help_to_section(self, section_key: str | None) -> None:
        dlg = getattr(self, "_roof_help_dialog", None)
        scroll = getattr(dlg, "_roof_help_scroll", None) if dlg is not None else None
        sections = getattr(dlg, "_roof_help_sections", None) if dlg is not None else None
        if not scroll or not sections or not section_key or section_key not in sections:
            return
        target = sections[section_key]
        scroll.ensureWidgetVisible(target, 0, 24)
        target.setProperty("roofHelpFocus", True)
        target.style().unpolish(target)
        target.style().polish(target)
        def _clear_focus():
            try:
                target.setProperty("roofHelpFocus", False)
                target.style().unpolish(target)
                target.style().polish(target)
            except Exception:
                pass
        QTimer.singleShot(1600, _clear_focus)

    def _open_roof_help_dialog(self, section_key: str | None = None):
        dlg = getattr(self, "_roof_help_dialog", None)
        if dlg is None:
            dlg = self._create_roof_help_dialog()
            self._roof_help_dialog = dlg
        try:
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            QTimer.singleShot(0, lambda key=section_key: self._scroll_roof_help_to_section(key))
        except Exception:
            pass

    def _create_roof_help_dialog(self) -> QDialog:
        dlg = QDialog(self)
        dlg.setWindowTitle("Hilfe – Dach-Editor")
        dlg.setModal(False)
        dlg.resize(1120, 860)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        intro = QFrame()
        intro.setObjectName("roofHelpHero")
        intro_lay = QVBoxLayout(intro)
        intro_lay.setContentsMargins(14, 12, 14, 12)
        intro_lay.setSpacing(4)
        title = QLabel("Ausführliche Hilfe zum Dach-Editor")
        title.setObjectName("roofEditorTitle")
        subtitle = QLabel(
            "Diese Hilfe erklärt alle Parameter und Optionen des Dach-Dialogs. "
            "Die Skizzen sind bewusst schematisch gehalten und zeigen, wie sich Eingaben auf Geometrie, Vorschau und DG-Ableitung auswirken."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("roofEditorText")
        intro_lay.addWidget(title)
        intro_lay.addWidget(subtitle)
        root.addWidget(intro)

        scroll = QScrollArea(dlg)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        dlg._roof_help_scroll = scroll
        dlg._roof_help_sections = {}
        root.addWidget(scroll, 1)

        content = QWidget(scroll)
        scroll.setWidget(content)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(12)

        sections = [
            (
                "1. Grundidee des Dach-Editors",
                "Der Dialog ist in drei Arbeitsbereiche gegliedert: links die Parameter, rechts oben die Live-Vorschau und darunter automatische Listen für Facetten und Dachlinien. "
                "Sie ändern also nicht nur numerische Werte, sondern sehen sofort die geometrische Wirkung. Die Vorschau basiert auf project_cfg.attic und bleibt mit dem DG synchron.\n\n"
                "Typischer Ablauf: Dachform wählen → Firstausrichtung prüfen → Dachneigung, Kniestock und Dachüberstand einstellen → zusätzliche First-/Grat-/Kehllinien setzen → Ergebnis in Facettenliste und Vorschau kontrollieren.",
                "overview",
            ),
            (
                "2. Dachform",
                "Mit der Dachform definieren Sie das Grundmodell des Daches. Satteldach erzeugt zwei geneigte Hauptflächen. Pultdach besitzt nur eine geneigte Hauptfläche. Walmdach zieht die Stirnseiten ebenfalls in die Dachschrägen hinein. "
                "Krüppelwalmdach ist eine Zwischenform mit teilweise abgewalmten Stirnseiten. Flachdach reduziert die Neigung praktisch auf eine horizontale Dachfläche. Winkel-/Kehldach ist für komplexere Grundrisse gedacht und wird oft zusammen mit zusätzlichen Dachlinien verwendet.\n\n"
                "Die Dachform ist der stärkste Strukturparameter: sie bestimmt, welche Flächen grundsätzlich entstehen können. Zusätzliche Dachlinien verfeinern das Ergebnis anschließend.",
                "roof_types",
            ),
            (
                "3. Firstausrichtung",
                "Die Firstausrichtung entscheidet, ob der Hauptfirst längs oder quer zum Gebäude verläuft. 'First längs' bedeutet: der First folgt der längeren Gebäuderichtung. 'First quer' dreht die Dachlogik um 90°.\n\n"
                "Das ist wichtig, weil sich damit die Fallrichtung der Dachflächen ändert. In der Vorschau sehen Sie sofort, welche Traufseiten höher bzw. niedriger ausgebildet werden. Bei Sattel- und Walmdächern ist diese Einstellung besonders relevant, weil sie die Lage des Hauptfirstes und damit auch die Facettenaufteilung beeinflusst.",
                "ridge",
            ),
            (
                "4. Dachneigung",
                "Die Dachneigung wird in Grad eingegeben. Größere Winkel machen die Dachflächen steiler und erhöhen in der Regel sowohl die Gesamthöhe als auch die geneigte Dachfläche. Kleine Winkel nähern sich einem flachen Dach an.\n\n"
                "Praktisch bedeutet das: Schon wenige Grad Unterschied verändern die Höhe des Dachaufbaus deutlich. Prüfen Sie daher nach einer Änderung immer die Kennzahlen 'Gesamthöhe' und 'Dachfläche' sowie den Querschnitt in der Vorschau. Bei sehr kleinen Winkeln sollte die gewählte Dachform weiterhin plausibel zum Baukörper passen.",
                "pitch",
            ),
            (
                "5. Kniestock",
                "Der Kniestock beschreibt die senkrechte Wandhöhe im DG, bevor die Dachschräge beginnt. Ein höherer Kniestock verschiebt den Beginn der Schräge nach oben und vergrößert meist die besser nutzbare Fläche im Dachgeschoss.\n\n"
                "Im Querschnitt erkennen Sie das daran, dass die senkrechten Außenwände höher werden, bevor die Dachfläche ansetzt. Für die Modellierung ist dieser Parameter wichtig, weil er die nutzbare Innenhöhe beeinflusst und die spätere DG-Geometrie verändert.",
                "knee",
            ),
            (
                "6. Dachüberstand",
                "Der Dachüberstand verlängert die Dachfläche über die Außenkante des Baukörpers hinaus. Ein größerer Wert vergrößert die projizierte Dachkontur und wirkt sich sichtbar auf die Dachaußenkante in der Vorschau aus.\n\n"
                "Der Überstand ist konstruktiv relevant, weil er die Hüllgeometrie verändert. In der Dachansicht sehen Sie, wie die äußere Linie über die Grundfläche hinausrückt. Bei Vergleichen der Dachfläche sollten Sie beachten, dass größere Überstände die geneigte Fläche erhöhen können.",
                "overhang",
            ),
            (
                "7. Dachlinien: First, Grat, Kehle",
                "Mit zusätzlichen Dachlinien verfeinern Sie komplexe Dächer. 'First' steht für eine obere Schnittlinie zweier Dachflächen. 'Grat' ist eine nach außen laufende Kante, typischerweise bei abgewalmten oder zusammengesetzten Dachflächen. 'Kehle' ist die nach innen laufende Einmündung zweier Dachflächen, also die typische Entwässerungslinie bei Winkeln oder Anbauten.\n\n"
                "Im Editor setzen Sie eine Linie mit zwei Klicks: Startpunkt und Endpunkt in der Draufsicht. Wählen Sie zuerst den Linientyp und platzieren Sie dann die Linie. Die Linienliste darunter dient der Kontrolle und dem gezielten Löschen. Bestehende Linien sollten nur gesetzt werden, wenn sie geometrisch sinnvoll sind, da sie direkt in die Facettenbildung eingehen.",
                "lines",
            ),
            (
                "8. Live-Vorschau, Kennzahlen und Facettenliste",
                "Die Live-Vorschau zeigt Querschnitt und Dachplan aus den aktuellen Projektdaten. Damit kontrollieren Sie sofort, ob die Dachlogik Ihrer Eingabe entspricht. Darüber hinaus liefern die Kennzahlen oben einen schnellen Plausibilitätscheck: Dachfläche, Facettenanzahl, Dachlinienanzahl und Gesamthöhe.\n\n"
                "Die Facettenliste zerlegt das Dach in einzelne Flächen. Das ist besonders hilfreich bei komplexen Dächern mit Kehlen, Graten und Teilfirsten. Wenn sich nach einer Linienänderung die Facettenanzahl sprunghaft verändert, ist das oft ein Hinweis auf eine starke topologische Änderung oder auf eine ungünstig platzierte Linie.",
                "preview",
            ),
            (
                "9. Projektparameter, Synchronisation und empfohlener Workflow",
                "Die Schaltflächen im Aktionsbereich unterstützen den Arbeitsablauf: 'Projektparameter' springt in die projektweite Konfiguration, 'Zum DG' wechselt direkt in die Dachgeschossansicht und 'Vorschau aktualisieren' erzwingt eine Neuberechnung.\n\n"
                "Empfehlung für sauberes Arbeiten: zuerst den Grundkörper im Projekt sauber definieren, dann im Dach-Editor die globale Dachform festlegen, erst danach Sonderlinien einzeichnen. Kontrollieren Sie komplexe Dächer immer über Vorschau und Facettenliste. Wenn etwas unplausibel wirkt, reduzieren Sie zunächst die Zusatzlinien und bauen die Geometrie schrittweise wieder auf.",
                "workflow",
            ),
        ]

        for section_title, section_text, image_kind in sections:
            section_widget = self._create_roof_help_section(section_title, section_text, image_kind)
            dlg._roof_help_sections[image_kind] = section_widget
            lay.addWidget(section_widget)
            if image_kind == "roof_types":
                lay.addWidget(self._create_roof_type_gallery())

        lay.addStretch(1)
        return dlg

    def _create_roof_type_gallery(self) -> QFrame:
        box = QFrame()
        box.setObjectName("roofHelpTypeGallery")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 0, 8, 4)
        lay.setSpacing(8)
        title = QLabel("Dach-Mini-Renderings je Dachtyp")
        title.setObjectName("roofEditorSectionTitle")
        lay.addWidget(title)
        subtitle = QLabel("Die Skizzen zeigen die typische Grundwirkung der verfügbaren Dachtypen im Editor. Sie dienen als schnelle Orientierung direkt in der Hilfe.")
        subtitle.setObjectName("roofEditorText")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        items = [
            ("Satteldach", "roof_type_gable", "Zwei geneigte Hauptflächen mit mittigem Hauptfirst.", "gable_standard"),
            ("Pultdach", "roof_type_shed", "Eine geneigte Hauptfläche mit eindeutiger Entwässerungsrichtung.", "shed_compact"),
            ("Walmdach", "roof_type_hip", "Alle Gebäudeseiten laufen in geneigte Dachflächen über.", "hip_balanced"),
            ("Krüppelwalmdach", "roof_type_halfhip", "Giebel bleibt teilweise erhalten, Stirnseiten sind nur teilweise abgewalmt.", "halfhip_family"),
            ("Flachdach", "roof_type_flat", "Nahezu horizontale Dachfläche mit geringer oder keiner sichtbaren Firstbildung.", "flat_modern"),
            ("Winkel-/Kehldach", "roof_type_valley", "Komplexer Dachtyp mit Einschnitt, Kehlen oder zusammengesetzten Teilflächen.", "valley_lshape"),
        ]
        for idx, item in enumerate(items):
            grid.addWidget(self._create_roof_type_mini_card(*item), idx // 2, idx % 2)
        lay.addLayout(grid)
        return box

    def _create_roof_help_section(self, title: str, text: str, image_kind: str) -> QFrame:
        box = QFrame()
        box.setObjectName("roofHelpSection")
        grid = QGridLayout(box)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("roofEditorSectionTitle")
        title_lbl.setWordWrap(True)
        grid.addWidget(title_lbl, 0, 0, 1, 2)

        image_lbl = QLabel()
        image_lbl.setObjectName("roofHelpImage")
        image_lbl.setPixmap(self._make_roof_help_pixmap(image_kind))
        image_lbl.setAlignment(Qt.AlignCenter)
        image_lbl.setMinimumHeight(180)
        grid.addWidget(image_lbl, 1, 0)

        text_lbl = QLabel(text)
        text_lbl.setObjectName("roofEditorText")
        text_lbl.setWordWrap(True)
        text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text_lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        grid.addWidget(text_lbl, 1, 1)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        return box

    def _make_roof_help_pixmap(self, kind: str, size: QSize | None = None) -> QPixmap:
        size = size or QSize(420, 190)
        pm = QPixmap(size)
        base = self.palette().base().color()
        alt = self.palette().alternateBase().color()
        text = self.palette().text().color()
        accent = self.palette().highlight().color()
        pm.fill(base)

        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(pm.rect(), alt)
        p.setPen(QPen(text, 1.4))

        margin = 18
        w = size.width() - 2 * margin
        h = size.height() - 2 * margin
        x0 = margin
        y0 = margin

        def roof_outline(points):
            poly = QPolygonF([QPointF(x0 + px * w, y0 + py * h) for px, py in points])
            p.drawPolyline(poly)

        def fill_poly(points, alpha=45):
            poly = QPolygonF([QPointF(x0 + px * w, y0 + py * h) for px, py in points])
            c = QColor(accent)
            c.setAlpha(alpha)
            p.setBrush(QBrush(c))
            p.drawPolygon(poly)
            p.setBrush(Qt.NoBrush)

        grid_pen = QPen(text, 1.0)
        grid_pen.setColor(QColor(text.red(), text.green(), text.blue(), 70))
        p.setPen(grid_pen)
        for frac in (0.25, 0.5, 0.75):
            p.drawLine(x0 + int(w * frac), y0, x0 + int(w * frac), y0 + h)
            p.drawLine(x0, y0 + int(h * frac), x0 + w, y0 + int(h * frac))

        p.setPen(QPen(text, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

        if kind == "overview":
            p.drawRoundedRect(x0 + 6, y0 + 20, int(w * 0.24), int(h * 0.68), 8, 8)
            p.drawRoundedRect(x0 + int(w * 0.34), y0 + 20, int(w * 0.62), int(h * 0.68), 8, 8)
            p.setPen(QPen(accent, 2.4))
            p.drawLine(x0 + int(w * 0.30), y0 + int(h * 0.50), x0 + int(w * 0.34), y0 + int(h * 0.50))
            p.drawLine(x0 + int(w * 0.36), y0 + int(h * 0.32), x0 + int(w * 0.82), y0 + int(h * 0.32))
            p.drawLine(x0 + int(w * 0.36), y0 + int(h * 0.56), x0 + int(w * 0.82), y0 + int(h * 0.56))
        elif kind == "roof_types":
            fill_poly([(0.05,0.72),(0.20,0.40),(0.35,0.72)])
            roof_outline([(0.05,0.72),(0.20,0.40),(0.35,0.72)])
            fill_poly([(0.42,0.72),(0.63,0.45),(0.63,0.72)])
            roof_outline([(0.42,0.72),(0.63,0.45),(0.63,0.72)])
            fill_poly([(0.70,0.72),(0.78,0.53),(0.88,0.53),(0.95,0.72)])
            roof_outline([(0.70,0.72),(0.78,0.53),(0.88,0.53),(0.95,0.72)])
        elif kind == "roof_type_gable":
            fill_poly([(0.08,0.76),(0.32,0.28),(0.56,0.76)])
            roof_outline([(0.08,0.76),(0.32,0.28),(0.56,0.76)])
            p.setPen(QPen(accent, 2.8))
            p.drawLine(x0 + int(w*0.24), y0 + int(h*0.28), x0 + int(w*0.40), y0 + int(h*0.28))
        elif kind == "roof_type_shed":
            fill_poly([(0.10,0.76),(0.54,0.30),(0.54,0.76)])
            roof_outline([(0.10,0.76),(0.54,0.30),(0.54,0.76)])
            p.setPen(QPen(accent, 2.8))
            p.drawLine(x0 + int(w*0.12), y0 + int(h*0.76), x0 + int(w*0.54), y0 + int(h*0.30))
        elif kind == "roof_type_hip":
            fill_poly([(0.10,0.74),(0.22,0.48),(0.44,0.48),(0.56,0.74),(0.33,0.24)])
            roof_outline([(0.10,0.74),(0.22,0.48),(0.44,0.48),(0.56,0.74),(0.33,0.24),(0.10,0.74)])
            p.setPen(QPen(accent, 2.8))
            p.drawLine(x0 + int(w*0.22), y0 + int(h*0.48), x0 + int(w*0.44), y0 + int(h*0.48))
        elif kind == "roof_type_halfhip":
            fill_poly([(0.08,0.74),(0.18,0.54),(0.25,0.38),(0.40,0.38),(0.48,0.54),(0.58,0.74)])
            roof_outline([(0.08,0.74),(0.18,0.54),(0.25,0.38),(0.40,0.38),(0.48,0.54),(0.58,0.74)])
            p.setPen(QPen(accent, 2.8))
            p.drawLine(x0 + int(w*0.25), y0 + int(h*0.38), x0 + int(w*0.40), y0 + int(h*0.38))
        elif kind == "roof_type_flat":
            fill_poly([(0.10,0.62),(0.58,0.62),(0.58,0.74),(0.10,0.74)], 30)
            roof_outline([(0.10,0.62),(0.58,0.62),(0.58,0.74),(0.10,0.74),(0.10,0.62)])
            p.setPen(QPen(accent, 2.8, Qt.DashLine))
            p.drawLine(x0 + int(w*0.10), y0 + int(h*0.62), x0 + int(w*0.58), y0 + int(h*0.62))
        elif kind == "roof_type_valley":
            fill_poly([(0.08,0.72),(0.22,0.42),(0.36,0.72),(0.50,0.46),(0.64,0.72)], 40)
            roof_outline([(0.08,0.72),(0.22,0.42),(0.36,0.72),(0.50,0.46),(0.64,0.72)])
            p.setPen(QPen(QColor(180, 90, 20), 2.8))
            p.drawLine(x0 + int(w*0.36), y0 + int(h*0.72), x0 + int(w*0.50), y0 + int(h*0.46))
        elif kind == "ridge":
            fill_poly([(0.10,0.70),(0.28,0.42),(0.46,0.70)])
            roof_outline([(0.10,0.70),(0.28,0.42),(0.46,0.70)])
            p.setPen(QPen(accent, 3.0))
            p.drawLine(x0 + int(w*0.20), y0 + int(h*0.36), x0 + int(w*0.36), y0 + int(h*0.36))
            p.setPen(QPen(text, 2.0))
            p.drawRect(x0 + int(w*0.58), y0 + int(h*0.28), int(w*0.24), int(h*0.44))
            p.setPen(QPen(accent, 3.0))
            p.drawLine(x0 + int(w*0.70), y0 + int(h*0.30), x0 + int(w*0.70), y0 + int(h*0.72))
        elif kind == "pitch":
            p.drawLine(x0 + int(w*0.08), y0 + int(h*0.74), x0 + int(w*0.42), y0 + int(h*0.74))
            p.drawLine(x0 + int(w*0.42), y0 + int(h*0.74), x0 + int(w*0.42), y0 + int(h*0.30))
            p.setPen(QPen(accent, 3.0))
            p.drawLine(x0 + int(w*0.14), y0 + int(h*0.74), x0 + int(w*0.42), y0 + int(h*0.42))
            p.drawArc(x0 + int(w*0.29), y0 + int(h*0.60), 44, 44, 80 * 16, 42 * 16)
        elif kind == "knee":
            p.drawRect(x0 + int(w*0.10), y0 + int(h*0.30), int(w*0.42), int(h*0.44))
            p.setPen(QPen(accent, 3.0))
            p.drawLine(x0 + int(w*0.10), y0 + int(h*0.30), x0 + int(w*0.10), y0 + int(h*0.74))
            p.drawLine(x0 + int(w*0.10), y0 + int(h*0.30), x0 + int(w*0.26), y0 + int(h*0.14))
            p.drawLine(x0 + int(w*0.52), y0 + int(h*0.30), x0 + int(w*0.36), y0 + int(h*0.14))
        elif kind == "overhang":
            p.drawRect(x0 + int(w*0.20), y0 + int(h*0.38), int(w*0.28), int(h*0.30))
            p.setPen(QPen(accent, 3.0))
            p.drawLine(x0 + int(w*0.12), y0 + int(h*0.34), x0 + int(w*0.34), y0 + int(h*0.12))
            p.drawLine(x0 + int(w*0.56), y0 + int(h*0.34), x0 + int(w*0.34), y0 + int(h*0.12))
            p.drawLine(x0 + int(w*0.05), y0 + int(h*0.34), x0 + int(w*0.12), y0 + int(h*0.34))
            p.drawLine(x0 + int(w*0.56), y0 + int(h*0.34), x0 + int(w*0.64), y0 + int(h*0.34))
        elif kind == "lines":
            p.drawRect(x0 + int(w*0.12), y0 + int(h*0.18), int(w*0.64), int(h*0.56))
            p.setPen(QPen(QColor(30, 120, 200), 3.0))
            p.drawLine(x0 + int(w*0.18), y0 + int(h*0.32), x0 + int(w*0.70), y0 + int(h*0.32))
            p.setPen(QPen(QColor(0, 150, 90), 3.0))
            p.drawLine(x0 + int(w*0.44), y0 + int(h*0.32), x0 + int(w*0.66), y0 + int(h*0.56))
            p.setPen(QPen(QColor(180, 90, 20), 3.0))
            p.drawLine(x0 + int(w*0.30), y0 + int(h*0.56), x0 + int(w*0.44), y0 + int(h*0.32))
        elif kind == "preview":
            p.drawRoundedRect(x0 + int(w*0.04), y0 + int(h*0.14), int(w*0.42), int(h*0.62), 8, 8)
            p.drawRoundedRect(x0 + int(w*0.54), y0 + int(h*0.14), int(w*0.36), int(h*0.62), 8, 8)
            p.setPen(QPen(accent, 2.6))
            p.drawLine(x0 + int(w*0.10), y0 + int(h*0.58), x0 + int(w*0.25), y0 + int(h*0.28))
            p.drawLine(x0 + int(w*0.25), y0 + int(h*0.28), x0 + int(w*0.40), y0 + int(h*0.58))
            for i in range(4):
                yy = y0 + int(h*(0.24 + i*0.12))
                p.drawLine(x0 + int(w*0.58), yy, x0 + int(w*0.84), yy)
        elif kind == "workflow":
            p.setPen(QPen(accent, 2.8))
            xs = [0.10, 0.30, 0.50, 0.70, 0.88]
            labels_y = [0.55, 0.35, 0.55, 0.35, 0.55]
            prev = None
            for xf, yf in zip(xs, labels_y):
                cx = x0 + int(w*xf)
                cy = y0 + int(h*yf)
                p.drawEllipse(QPointF(cx, cy), 18, 18)
                if prev is not None:
                    p.drawLine(prev[0] + 18, prev[1], cx - 18, cy)
                prev = (cx, cy)
        else:
            p.drawRoundedRect(x0 + 8, y0 + 8, w - 16, h - 16, 10, 10)

        p.end()
        return pm

    def _create_docks(self):
        """Erstellt echte DockWidgets für Eigenschaften und Elemente."""
        dock_features = (
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        # Projekt-Dashboard
        self.dock_dashboard = QDockWidget("Projekt-Dashboard", self)
        self.dock_dashboard.setObjectName("dock_dashboard")
        self.dock_dashboard.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_dashboard.setFeatures(dock_features)
        self.dock_dashboard.setTitleBarWidget(DockTitleBar(self.dock_dashboard, "Projekt-Dashboard", "Status, DIN und offene Punkte", "Projekt"))
        dashboard_widget = QWidget()
        dashboard_widget.setMinimumWidth(0)
        dashboard_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        dashboard_lay = QVBoxLayout(dashboard_widget)
        dashboard_lay.setContentsMargins(8, 8, 8, 8)
        dashboard_lay.setSpacing(8)
        self.lbl_dashboard_project = QLabel("Projekt: —")
        self.lbl_dashboard_project.setWordWrap(True)
        self.lbl_dashboard_din = QLabel("DIN: —")
        self.lbl_dashboard_din.setWordWrap(True)
        self.lbl_dashboard_counts = QLabel("Räume: 0 · Bauteile: 0")
        self.lbl_dashboard_counts.setWordWrap(True)
        self.lbl_dashboard_saved = QLabel("Status: —")
        self.lbl_dashboard_saved.setWordWrap(True)
        self.lbl_dashboard_workflow = QLabel("Arbeits-Checkliste")
        self.lbl_dashboard_workflow.setObjectName("panelSectionTitle")
        self.list_dashboard_workflow = QListWidget()
        self.list_dashboard_workflow.setObjectName("projectDashboardWorkflow")
        self.list_dashboard_workflow.setToolTip("Zentrale Projektführung mit direktem Sprung zur passenden Eingabe.")
        self.list_dashboard_workflow.setMaximumHeight(130)
        self.list_dashboard_checks = QListWidget()
        self.list_dashboard_checks.setObjectName("projectDashboardChecks")
        self.list_dashboard_checks.setToolTip("Projektweite offene Punkte und nächste Korrekturen.")
        self.lbl_dashboard_room_matrix = QLabel("Raum-Nachweis-Matrix")
        self.lbl_dashboard_room_matrix.setObjectName("panelSectionTitle")
        self.tbl_room_norm_matrix = QTableWidget(0, 10)
        self.tbl_room_norm_matrix.setObjectName("roomNormProofMatrix")
        self.tbl_room_norm_matrix.setToolTip("Raumweise DIN-Prüfpunkte für Geometrie, Transmission, Lüftung und Nachbarzonen.")
        self.tbl_room_norm_matrix.setHorizontalHeaderLabels([
            "Raum", "AW", "Fen.", "Dach", "Decke", "Boden", "WB", "Luft", "Temp.", "Nachbar",
        ])
        self.tbl_room_norm_matrix.verticalHeader().setVisible(False)
        self.tbl_room_norm_matrix.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_room_norm_matrix.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_room_norm_matrix.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl_room_norm_matrix.setMaximumHeight(180)
        self.lbl_dashboard_heat_audit = QLabel("Heizlast-Audit")
        self.lbl_dashboard_heat_audit.setObjectName("panelSectionTitle")
        self.list_dashboard_heat_audit = QListWidget()
        self.list_dashboard_heat_audit.setObjectName("heatloadAuditList")
        self.list_dashboard_heat_audit.setToolTip("Top-Lasttreiber und Auffälligkeiten bei DG-Dach-/Giebelflächen.")
        self.list_dashboard_heat_audit.setMaximumHeight(190)
        btn_row = QWidget()
        btn_row_lay = QHBoxLayout(btn_row)
        btn_row_lay.setContentsMargins(0, 0, 0, 0)
        btn_row_lay.setSpacing(6)
        self.btn_dashboard_norm = QPushButton("Normprüfung")
        self.btn_dashboard_save_version = QPushButton("Version speichern")
        btn_row_lay.addWidget(self.btn_dashboard_norm)
        btn_row_lay.addWidget(self.btn_dashboard_save_version)
        dashboard_lay.addWidget(self.lbl_dashboard_project)
        dashboard_lay.addWidget(self.lbl_dashboard_din)
        dashboard_lay.addWidget(self.lbl_dashboard_counts)
        dashboard_lay.addWidget(self.lbl_dashboard_saved)
        dashboard_lay.addWidget(self.lbl_dashboard_workflow)
        dashboard_lay.addWidget(self.list_dashboard_workflow)
        dashboard_lay.addWidget(self.lbl_dashboard_room_matrix)
        dashboard_lay.addWidget(self.tbl_room_norm_matrix)
        dashboard_lay.addWidget(self.lbl_dashboard_heat_audit)
        dashboard_lay.addWidget(self.list_dashboard_heat_audit)
        dashboard_lay.addWidget(self.list_dashboard_checks, 1)
        dashboard_lay.addWidget(btn_row)
        self.dock_dashboard.setWidget(dashboard_widget)
        self._configure_side_dock(self.dock_dashboard, 240)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_dashboard)

        # Eigenschaften
        self.dock_properties = QDockWidget("Eigenschaften", self)
        self.dock_properties.setObjectName("dock_properties")
        self.dock_properties.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_properties.setFeatures(dock_features)
        self.dock_properties.setTitleBarWidget(DockTitleBar(self.dock_properties, "Eigenschaften", "Raumdaten und Bezugsfläche", "Raum"))
        prop_scroll = QScrollArea()
        prop_scroll.setWidgetResizable(True)
        prop_scroll.setFrameShape(QFrame.NoFrame)
        prop_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        prop_scroll.setMinimumWidth(0)
        prop_scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        prop_widget = QWidget()
        prop_widget.setMinimumWidth(0)
        prop_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        prop_layout = QVBoxLayout(prop_widget)
        prop_layout.setContentsMargins(8, 8, 8, 8)
        prop_layout.addWidget(QLabel("Raum-Eigenschaften (Auswahl):"))

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
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
        self.lbl_room_norm_status = QLabel("Raumstatus: —")
        self.lbl_room_norm_status.setWordWrap(True)
        prop_layout.addWidget(self.lbl_room_norm_status)
        prop_layout.addStretch(1)
        prop_scroll.setWidget(prop_widget)
        self.dock_properties.setWidget(prop_scroll)
        self._configure_side_dock(self.dock_properties, 220)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_properties)
        self.splitDockWidget(self.dock_dashboard, self.dock_properties, Qt.Vertical)

        # Elemente
        self.dock_elements = QDockWidget("Elemente", self)
        self.dock_elements.setObjectName("dock_elements")
        self.dock_elements.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_elements.setFeatures(dock_features)
        self.dock_elements.setTitleBarWidget(DockTitleBar(self.dock_elements, "Elemente", "Bauteile des aktiven Raums", "Liste"))
        elem_widget = QWidget()
        elem_widget.setMinimumWidth(0)
        elem_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        elem_layout = QVBoxLayout(elem_widget)
        elem_layout.setContentsMargins(8, 8, 8, 8)
        elem_layout.addWidget(QLabel("Elemente des selektierten Raums:"))
        self.ed_element_filter = QLineEdit()
        self.ed_element_filter.setPlaceholderText("Elemente filtern…")
        self.ed_element_filter.setToolTip("Filtert nach Bauteiltyp, Auto-DG-Marker, Fläche oder U-Wert.")
        self.ed_element_filter.textChanged.connect(self._filter_room_elements_list)
        elem_layout.addWidget(self.ed_element_filter)
        self.btn_element_assistant = QPushButton("Bauteil-Assistent")
        self.btn_element_assistant.setToolTip("Geführte Eingabe für Bauteiltyp, Randbedingung, U-Wert, Fläche und Quelle.")
        elem_layout.addWidget(self.btn_element_assistant)

        self.list_room_elements = QListWidget()
        self.list_room_elements.setMinimumHeight(200)
        self.list_room_elements.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_room_elements.itemSelectionChanged.connect(self._on_room_element_selected)
        self.list_room_elements.itemDoubleClicked.connect(self._on_room_element_double_clicked)
        self.list_room_elements.setToolTip("Klick: Element in Grafik hervorheben\nEntf: Element löschen")
        elem_layout.addWidget(self.list_room_elements)

        self.dock_elements.setWidget(elem_widget)
        self._configure_side_dock(self.dock_elements, 220)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_elements)
        self.splitDockWidget(self.dock_properties, self.dock_elements, Qt.Vertical)

        self.dock_attic = QDockWidget("DG Dach / Giebel", self)
        self.dock_attic.setObjectName("dock_attic")
        self.dock_attic.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_attic.setFeatures(dock_features)
        self.dock_attic.setTitleBarWidget(DockTitleBar(self.dock_attic, "DG Dach / Giebel", "Live-Skizze und Dachstatus", "Dach"))
        self.attic_sketch_panel = AtticSketchPanel(self)
        self.attic_sketch_panel.setMinimumHeight(260)
        self.dock_attic.setWidget(self.attic_sketch_panel)
        self._configure_side_dock(self.dock_attic, 220)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_attic)
        self.splitDockWidget(self.dock_elements, self.dock_attic, Qt.Vertical)

        self.dock_plausibility = QDockWidget("Plausibilität", self)
        self.dock_plausibility.setObjectName("dock_plausibility")
        self.dock_plausibility.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_plausibility.setFeatures(dock_features)
        self.dock_plausibility.setTitleBarWidget(DockTitleBar(self.dock_plausibility, "Plausibilität", "Hinweise und Prüfungen", "Check"))
        plaus_widget = QWidget()
        plaus_widget.setMinimumWidth(0)
        plaus_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        plaus_lay = QVBoxLayout(plaus_widget)
        plaus_lay.setContentsMargins(8, 8, 8, 8)
        self.list_plausibility = QListWidget()
        self.list_plausibility.setToolTip("Hinweise und Prüfungen; Klick auf einen Eintrag dient als Merkliste für die nächste Korrektur.")
        plaus_lay.addWidget(self.list_plausibility)
        self.dock_plausibility.setWidget(plaus_widget)
        self._configure_side_dock(self.dock_plausibility, 220)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_plausibility)
        self.splitDockWidget(self.dock_attic, self.dock_plausibility, Qt.Vertical)
        self.tabifyDockWidget(self.dock_elements, self.dock_plausibility)
        self.tabifyDockWidget(self.dock_dashboard, self.dock_properties)
        self.dock_dashboard.raise_()
        self.dock_elements.raise_()
        QTimer.singleShot(0, self._release_side_dock_width_limits)

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
        self.lbl_status_din = QLabel("DIN: —")

        sb.addWidget(self.lbl_status_project, 1)
        sb.addPermanentWidget(self.lbl_status_recent)
        sb.addPermanentWidget(self.lbl_status_rooms)
        sb.addPermanentWidget(self.lbl_status_heat)
        sb.addPermanentWidget(self.lbl_status_din)

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
            dirty = " *" if getattr(self, "_dirty", False) else ""
            self.lbl_status_project.setText(f"Projekt: {project_path}{dirty}")
            self.lbl_status_recent.setText(f"Ordner: {last_dir}")
            self.lbl_status_rooms.setText(f"Räume: {len(self.rooms)}")
            self.lbl_status_heat.setText(f"Heizlast gesamt: {total_q:,.0f} W".replace(",", "."))
            din_status = getattr(self, "_last_din_status", None)
            if isinstance(din_status, tuple) and len(din_status) >= 2:
                symbol, summary = din_status[0], din_status[1]
                label = {"✓": "Grün", "△": "Gelb", "✗": "Rot"}.get(str(symbol), "—")
                self.lbl_status_din.setText(f"DIN: {label}")
                self.lbl_status_din.setToolTip(str(summary))
            else:
                self.lbl_status_din.setText("DIN: —")
                self.lbl_status_din.setToolTip("DIN-Prüfstatus wird nach der Berechnung angezeigt.")
            if hasattr(self, "_refresh_project_dashboard"):
                self._refresh_project_dashboard()
        except Exception:
            pass

    def _show_project_dashboard(self):
        dock = getattr(self, "dock_dashboard", None)
        if dock is None:
            return
        dock.show()
        dock.raise_()
        if hasattr(self, "_refresh_project_dashboard"):
            self._refresh_project_dashboard()

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
        self.cb_usage_type = QComboBox()
        self.cb_usage_type.addItem("Individuell", "")
        for usage in sorted(ROOM_USAGE_DEFAULTS.keys()):
            label = str(usage).title().replace("Kueche", "Küche").replace("Hwr", "HWR").replace("Wc", "WC")
            self.cb_usage_type.addItem(label, usage)
        self.sp_tin = QDoubleSpinBox()
        self.sp_tin.setRange(5, 30)
        self.sp_tin.setDecimals(1)
        self.sp_tin.setSingleStep(0.5)
        self.sp_n = QDoubleSpinBox()
        self.sp_n.setRange(0.0, 5.0)
        self.sp_n.setDecimals(2)
        self.sp_n.setSingleStep(0.05)

        for editor in (
            self.ed_id,
            self.ed_name,
            self.cb_floor,
            self.sp_x,
            self.sp_y,
            self.sp_w,
            self.sp_h,
            self.sp_height,
            self.cb_usage_type,
            self.sp_tin,
            self.sp_n,
        ):
            editor.setMinimumWidth(0)
            editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        form.addRow("ID", self.ed_id)
        form.addRow("Name", self.ed_name)
        form.addRow("Geschoss", self.cb_floor)
        form.addRow("x [m]", self.sp_x)
        form.addRow("y [m]", self.sp_y)
        form.addRow("Länge w [m]", self.sp_w)
        form.addRow("Breite h [m]", self.sp_h)
        form.addRow("Raumhöhe [m]", self.sp_height)
        form.addRow("Nutzung", self.cb_usage_type)
        form.addRow("T innen [°C]", self.sp_tin)
        form.addRow("n [1/h]", self.sp_n)

    def _connect_signals(self):
        """Verbindet die UI-Signale mit den Slots."""
        self.act_heatmap.toggled.connect(self._on_heat_toggle)
        self.act_autowalls_enabled.toggled.connect(self._on_autow_toggle)
        self.act_auto_attic_markers.toggled.connect(self._on_toggle_auto_attic_markers)
        if hasattr(self, "act_show_attic_dock"):
            self.act_show_attic_dock.toggled.connect(self._on_toggle_attic_dock)
        if hasattr(self, "dock_attic"):
            self.dock_attic.visibilityChanged.connect(self._sync_attic_dock_action)
        if getattr(self, "cb_area_ref_outer", None) is not None:
            self.cb_area_ref_outer.toggled.connect(self._on_toggle_area_ref_outer_action)
        if getattr(self, "cb_usage_type", None) is not None:
            self.cb_usage_type.currentIndexChanged.connect(self._on_room_usage_preset_changed)
        if getattr(self, "btn_dashboard_norm", None) is not None:
            self.btn_dashboard_norm.clicked.connect(self._on_project_settings_norm)
        if getattr(self, "btn_dashboard_save_version", None) is not None:
            self.btn_dashboard_save_version.clicked.connect(self._on_save_version)
        if getattr(self, "list_dashboard_workflow", None) is not None:
            self.list_dashboard_workflow.itemClicked.connect(self._on_dashboard_workflow_item_clicked)
        if getattr(self, "tbl_room_norm_matrix", None) is not None:
            self.tbl_room_norm_matrix.cellClicked.connect(self._on_room_norm_matrix_cell_clicked)
        if getattr(self, "list_dashboard_heat_audit", None) is not None:
            self.list_dashboard_heat_audit.itemClicked.connect(self._on_heat_audit_item_clicked)
        if getattr(self, "btn_element_assistant", None) is not None:
            self.btn_element_assistant.clicked.connect(self._on_element_assistant)
        self.btn_apply.clicked.connect(self._apply_room_form)

        # Auswahländerungen in den Szenen
        self.scene_KG.selectionChanged.connect(self._on_scene_selection_changed_kg)
        self.scene_EG.selectionChanged.connect(self._on_scene_selection_changed_eg)
        self.scene_DG.selectionChanged.connect(self._on_scene_selection_changed_dg)


        #
        # Shortcut für Element löschen in der Liste
        self._sc_del_elem = QShortcut(QKeySequence.Delete, self.list_room_elements)
        self._sc_del_elem.activated.connect(self._delete_selected_room_element)

    def _on_switch_to_dg_view(self):
        try:
            if hasattr(self, "tabs") and hasattr(self, "view_DG"):
                self.tabs.setCurrentWidget(self.view_DG)
            if hasattr(self, "dock_attic"):
                self.dock_attic.show()
                self.dock_attic.raise_()
            self._refresh_attic_preview()
            self._fit_current_plan_view()
        except Exception:
            pass

    def _on_toggle_attic_dock(self, checked: bool):
        dock = getattr(self, "dock_attic", None)
        if dock is None:
            return
        dock.setVisible(bool(checked))
        if checked:
            try:
                dock.raise_()
            except Exception:
                pass

    def _sync_attic_dock_action(self, visible: bool):
        if hasattr(self, "act_show_attic_dock"):
            self.act_show_attic_dock.blockSignals(True)
            self.act_show_attic_dock.setChecked(bool(visible))
            self.act_show_attic_dock.blockSignals(False)

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
            aa_on = self._settings.value("auto_attic_markers", True, type=bool)
            self.show_auto_attic_markers = bool(aa_on)
            if hasattr(self, "act_auto_attic_markers"):
                self.act_auto_attic_markers.blockSignals(True)
                self.act_auto_attic_markers.setChecked(bool(aa_on))
                self.act_auto_attic_markers.blockSignals(False)
            if hasattr(self, "dock_attic") and hasattr(self, "act_show_attic_dock"):
                self._sync_attic_dock_action(self.dock_attic.isVisible())
        except Exception:
            pass

        try:
            self._last_project_dir = self._settings.value("last_project_dir", "", type=str) or ""
        except Exception:
            self._last_project_dir = ""

        try:
            was_maximized = self._settings.value("main_was_maximized", True, type=bool)
            geom = self._settings.value("main_geometry")
            if geom and not was_maximized:
                self.restoreGeometry(geom)
            state = self._settings.value("main_state")
            if state:
                self.restoreState(state)
            if was_maximized:
                self.showMaximized()
            QTimer.singleShot(0, self._release_side_dock_width_limits)
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
            self._settings.setValue("auto_attic_markers", bool(getattr(self, "show_auto_attic_markers", True)))
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
            background: #ffffff;
            border: 1px solid #d7dbe0;
            border-radius: 8px;
            margin: 4px;
        }
        QDockWidget::title {
            background: #ffffff;
            border-bottom: 1px solid #d7dbe0;
            padding: 8px 10px;
            text-align: left;
            font-weight: 600;
        }
        QFrame#dockTitleBar {
            background: #ffffff;
            border-bottom: 1px solid #d7dbe0;
        }
        QLabel#dockTitle {
            color: #1f2937;
            font-weight: 700;
            font-size: 12px;
        }
        QLabel#dockSubtitle {
            color: #64748b;
            font-size: 10px;
        }
        QLabel#dockBadge {
            color: #365f8d;
            background: #edf3fb;
            border: 1px solid #c9d8ea;
            border-radius: 8px;
            padding: 2px 7px;
            font-size: 10px;
            font-weight: 700;
        }
        QToolButton#dockTitleButton {
            background: #f8fafc;
            border: 1px solid #d7dbe0;
            border-radius: 7px;
            padding: 2px 6px;
            min-width: 18px;
            color: #334155;
        }
        QToolButton#dockTitleButton:hover {
            background: #edf3fb;
            border-color: #a8c2df;
        }
        QMainWindow::separator {
            background: #d7dbe0;
            width: 5px;
            height: 5px;
        }
        QMainWindow::separator:hover {
            background: #a8c2df;
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
        QFrame#roofEditorHero,
        QFrame#roofEditorFormWrap,
        QFrame#roofEditorActionsWrap,
        QFrame#roofEditorPreviewWrap,
        QFrame#roofEditorLineWrap,
        QFrame#roofEditorFacetWrap,
        QFrame#roofMetricAreaCard,
        QFrame#roofMetricFacetCard,
        QFrame#roofMetricLineCard,
        QFrame#roofMetricHeightCard {
            background: #ffffff;
            border: 1px solid #d7dbe0;
            border-radius: 12px;
        }
        QLabel#roofEditorTitle {
            font-size: 18px;
            font-weight: 700;
            color: #243447;
        }
        QLabel#roofEditorSectionTitle {
            font-size: 13px;
            font-weight: 700;
            color: #243447;
        }
        QLabel#roofEditorText, QLabel#roofEditorMetricTitle {
            color: #607080;
        }
        QLabel#roofEditorMetricValue {
            font-size: 18px;
            font-weight: 700;
            color: #1f3b5b;
        }
        QLabel#roofEditorBadge {
            background: #edf3fb;
            border: 1px solid #c9d8ea;
            border-radius: 10px;
            padding: 3px 8px;
            color: #32506f;
            font-weight: 600;
        }
        QSplitter#roofEditorSplitter::handle {
            background: #e6ebf1;
            width: 8px;
        }
        QListWidget#roofTabFacetList, QListWidget#roofTabLineList {
            min-height: 120px;
        }
        QFrame#roofHelpSection, QFrame#roofHelpMiniCard {
            background: #ffffff;
            border: 1px solid #d7dbe0;
            border-radius: 12px;
        }
        QFrame#roofHelpSection[roofHelpFocus="true"] {
            border: 2px solid #4f87c2;
        }
        """)
