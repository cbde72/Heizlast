from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class InfoDialog(QDialog):
    def __init__(
        self,
        parent,
        *,
        app_name: str,
        app_version: str,
        internal_app_version: str,
        project_schema_version: int | str,
        internal_project_version: str,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Info – {app_name}")
        self.setModal(True)
        self.resize(760, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("infoHero")
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(16, 14, 16, 14)
        hero_lay.setSpacing(4)

        title = QLabel(app_name)
        title.setObjectName("infoTitle")
        subtitle = QLabel("Versionen, Hauptfunktionen und DIN-Hinweise")
        subtitle.setObjectName("infoSubtitle")
        hero_lay.addWidget(title)
        hero_lay.addWidget(subtitle)
        root.addWidget(hero)

        content = QHBoxLayout()
        content.setSpacing(12)
        root.addLayout(content, 1)

        left = QFrame()
        left.setObjectName("infoPanel")
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(14, 14, 14, 14)
        left_lay.setSpacing(8)

        versions_title = QLabel("Versionen")
        versions_title.setObjectName("infoSectionTitle")
        left_lay.addWidget(versions_title)

        for label, value in (
            ("Anwendungsversion", app_version),
            ("Interne Versionsnummer", internal_app_version),
            ("Projekt-Schema", str(project_schema_version)),
            ("Interne Projektversion", internal_project_version),
        ):
            row = QWidget()
            row_lay = QVBoxLayout(row)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(1)
            lb = QLabel(label)
            lb.setObjectName("infoFieldLabel")
            val = QLabel(str(value))
            val.setObjectName("infoFieldValue")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row_lay.addWidget(lb)
            row_lay.addWidget(val)
            left_lay.addWidget(row)

        left_lay.addStretch(1)
        content.addWidget(left, 0)

        right = QFrame()
        right.setObjectName("infoPanel")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(14, 14, 14, 14)
        right_lay.setSpacing(10)

        features_title = QLabel("Hauptfunktionen")
        features_title.setObjectName("infoSectionTitle")
        right_lay.addWidget(features_title)

        features = QListWidget()
        features.setObjectName("infoFeatureList")
        for text in (
            "Mehrgeschossiger Grundriss-Editor für KG / EG / DG",
            "Automatische Erzeugung von Außen- und Innenwänden sowie Auto-Keller",
            "Projektparameter für Randbedingungen, Geometrie, Lüftung, Wärmebrücken, Erdreich und DG-Dach",
            "Heizlastberechnung mit Reports, CSV- und Grundriss-Export",
            "3D-Hausansicht, Beschriftungs-Overlays und Attika-/Dachvorschau",
        ):
            QListWidgetItem(text, features)
        features.setMinimumHeight(190)
        right_lay.addWidget(features)

        din_title = QLabel("DIN-Konformität")
        din_title.setObjectName("infoSectionTitle")
        right_lay.addWidget(din_title)

        din_text = QTextBrowser()
        din_text.setObjectName("infoDinText")
        din_text.setOpenExternalLinks(False)
        din_text.setHtml(
            "<p>Das Werkzeug ist auf eine Auslegung nach <b>DIN EN 12831</b> ausgelegt.</p>"
            "<p>Unterstützt werden wesentliche Eingangsgrößen und Rechenbausteine wie "
            "Norm-Außentemperatur, Lüftungsansatz, Wärmebrückenansatz, Erdreichmodell "
            "und bauteilbezogene U-Werte.</p>"
            "<p>Die finale normative Verantwortung bleibt beim Anwender und bei der "
            "projektspezifischen Parametrierung.</p>"
        )
        right_lay.addWidget(din_text, 1)

        content.addWidget(right, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.Close).setDefault(True)
        root.addWidget(buttons)

        self.setStyleSheet(
            """
            QDialog { background: #f4f7fb; }
            QFrame#infoHero {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #114e72, stop:1 #1c7ea4);
                border-radius: 10px;
            }
            QLabel#infoTitle {
                color: white;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#infoSubtitle {
                color: rgba(255,255,255,0.92);
                font-size: 12px;
            }
            QFrame#infoPanel {
                background: white;
                border: 1px solid #d6e0ea;
                border-radius: 10px;
            }
            QLabel#infoSectionTitle {
                font-size: 14px;
                font-weight: 700;
                color: #16384a;
            }
            QLabel#infoFieldLabel {
                color: #607080;
                font-size: 11px;
            }
            QLabel#infoFieldValue {
                color: #0f2230;
                font-size: 13px;
                font-weight: 600;
            }
            QListWidget#infoFeatureList, QTextBrowser#infoDinText {
                background: #fbfdff;
                border: 1px solid #dbe5ee;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget#infoFeatureList::item {
                padding: 6px 4px;
            }
            """
        )
