from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QDialogButtonBox,
    QVBoxLayout,
    QWidget,
)


class NewProjectDialog(QDialog):
    def __init__(self, parent=None, *, default_dir: str = '', suggested_name: str = 'heizlast_projekt', guided_default: bool = True):
        super().__init__(parent)
        self.setWindowTitle('Neues Projekt')
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        intro = QLabel('Neues Heizlast-Projekt anlegen')
        intro.setObjectName('newProjectTitle')
        sub = QLabel('Projektname, Speicherort und Startoptionen festlegen. Auf Wunsch wird direkt ein leerer Projektstand gespeichert.')
        sub.setWordWrap(True)
        root.addWidget(intro)
        root.addWidget(sub)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setContentsMargins(0, 6, 0, 6)

        self.ed_name = QLineEdit(suggested_name)
        self.ed_name.setPlaceholderText('z. B. einfamilienhaus_muster')
        form.addRow('Projektname', self.ed_name)

        row_dir = QHBoxLayout()
        row_dir.setContentsMargins(0, 0, 0, 0)
        self.ed_dir = QLineEdit(default_dir or str(Path.cwd()))
        self.btn_browse = QPushButton('Ordner…')
        self.btn_browse.clicked.connect(self._browse_dir)
        row_dir.addWidget(self.ed_dir, 1)
        row_dir.addWidget(self.btn_browse)
        form.addRow('Projektordner', row_dir)

        self.cb_floor = QComboBox()
        self.cb_floor.addItems(['KG', 'EG', 'DG'])
        self.cb_floor.setCurrentText('EG')
        form.addRow('Startgeschoss', self.cb_floor)

        self.chk_open_settings = QCheckBox('Projektparameter nach dem Anlegen direkt öffnen')
        self.chk_open_settings.setChecked(True)
        form.addRow('', self.chk_open_settings)

        self.chk_guided_setup = QCheckBox('Geführten Normstart verwenden')
        self.chk_guided_setup.setChecked(bool(guided_default))
        form.addRow('', self.chk_guided_setup)

        self.cb_setup_scope = QComboBox()
        self.cb_setup_scope.addItems([
            'Normprüfung, U-Werte, Lüftung, Erdreich',
            'Nur Normprüfung und U-Werte',
            'Nur Projektparameter öffnen',
        ])
        form.addRow('Start-Assistent', self.cb_setup_scope)

        self.chk_save_now = QCheckBox('Leeres Projekt sofort als CSV/JSON anlegen')
        self.chk_save_now.setChecked(True)
        form.addRow('', self.chk_save_now)

        root.addWidget(form_host)

        note = QLabel('Dateien werden als <Projektname>_rooms.csv, <Projektname>_elements.csv und <Projektname>_rooms.project.json gespeichert.')
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.resize(560, 260)

    def _browse_dir(self):
        start = self.ed_dir.text().strip() or str(Path.cwd())
        path = QFileDialog.getExistingDirectory(self, 'Projektordner wählen', start)
        if path:
            self.ed_dir.setText(path)

    def _accept(self):
        name = self.project_name()
        folder = self.project_dir()
        if not name:
            QMessageBox.warning(self, 'Neues Projekt', 'Bitte einen Projektnamen eingeben.')
            return
        if not folder:
            QMessageBox.warning(self, 'Neues Projekt', 'Bitte einen Projektordner angeben.')
            return
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.critical(self, 'Neues Projekt', f'Projektordner konnte nicht erstellt werden:\n{exc}')
            return
        self.accept()

    def project_name(self) -> str:
        raw = (self.ed_name.text() or '').strip()
        safe = ''.join(ch if ch.isalnum() or ch in ('_', '-') else '_' for ch in raw).strip('_')
        return safe or 'heizlast_projekt'

    def project_dir(self) -> str:
        return (self.ed_dir.text() or '').strip()

    def values(self) -> dict:
        name = self.project_name()
        folder = Path(self.project_dir())
        rooms_path = folder / f'{name}_rooms.csv'
        return {
            'project_name': name,
            'project_dir': str(folder),
            'rooms_path': str(rooms_path),
            'elements_path': str(rooms_path.with_name(f'{name}_elements.csv')),
            'start_floor': self.cb_floor.currentText(),
            'open_settings': self.chk_open_settings.isChecked(),
            'guided_setup': self.chk_guided_setup.isChecked(),
            'setup_scope': self.cb_setup_scope.currentText(),
            'save_now': self.chk_save_now.isChecked(),
        }
