from pathlib import Path

from heizlast.configs.project_config import ProjectCfg

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIALOG = ROOT / "src" / "heizlast" / "ui" / "dialogs" / "project_settings_dialog.py"


def test_project_settings_contains_roof_line_editor_ui_hooks():
    src = PROJECT_DIALOG.read_text(encoding="utf-8")
    assert 'class RoofLineEditorWidget(QWidget):' in src
    assert 'self.cb_roof_line_kind = QComboBox(); self.cb_roof_line_kind.addItems(["First", "Grat", "Kehle"])' in src
    assert 'self.lst_roof_lines = QListWidget(); self.lst_roof_lines.setObjectName("roofLineListWidget")' in src
    assert 'self.gb_attic_roof_lines = self._group("Dachlinien-Editor"' in src
    assert 'self.btn_roof_line_delete.clicked.connect(self._delete_selected_roof_line)' in src
    assert 'cfg.attic.roof_lines = [RoofLineCfgDTO(**{k: getattr(line, k) for k in RoofLineCfgDTO.__dataclass_fields__.keys()}) for line in self.roof_line_editor.current_lines()]' in src


def test_project_cfg_v30_schema_upgrade_keeps_roof_lines_list():
    cfg = ProjectCfg.from_json_dict({
        "cfg_version": 14,
        "attic": {
            "enabled": True,
            "roof_type": "winkeldach",
            "roof_lines": [
                {"kind": "first", "x1_ratio": 0.1, "y1_ratio": 0.2, "x2_ratio": 0.9, "y2_ratio": 0.2},
                {"kind": "kehle", "x1_ratio": 0.5, "y1_ratio": 0.2, "x2_ratio": 0.7, "y2_ratio": 0.8},
            ],
        },
    })
    assert cfg.cfg_version == 16
    assert len(cfg.attic.roof_lines) == 2
    assert cfg.attic.roof_lines[1].kind == "kehle"
