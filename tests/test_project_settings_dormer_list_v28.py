from pathlib import Path

from heizlast import PROJECT_SCHEMA_VERSION
from heizlast.configs.project_config import ProjectCfg

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIALOG = ROOT / "src" / "heizlast" / "ui" / "dialogs" / "project_settings_dialog.py"


def test_project_settings_contains_dormer_list_ui_hooks():
    src = PROJECT_DIALOG.read_text(encoding="utf-8")
    assert 'class DormerEditDialog(QDialog):' in src
    assert 'self.lst_dormers = QListWidget(); self.lst_dormers.setObjectName("dormerListWidget")' in src
    assert 'self.btn_dormer_add = QPushButton("Hinzufügen")' in src
    assert 'self.gb_attic_dormers = self._group("Gaubenliste"' in src
    assert 'self.btn_dormer_add.clicked.connect(self._add_dormer)' in src
    assert 'self.lst_dormers.itemDoubleClicked.connect(lambda _item: self._edit_selected_dormer())' in src
    assert 'cfg.attic.dormers = [DormerCfgDTO(**{k: getattr(d, k) for k in DormerCfgDTO.__dataclass_fields__.keys()}) for d in self._dormers]' in src


def test_project_cfg_v28_schema_upgrade_keeps_dormers_list():
    cfg = ProjectCfg.from_json_dict({
        "cfg_version": 12,
        "attic": {
            "enabled": True,
            "dormers": [
                {
                    "id": "gaube_1",
                    "dormer_type": "schleppgaube",
                    "roof_side": "right",
                    "center_along_m": 4.5,
                    "width_m": 2.0,
                    "depth_m": 1.5,
                    "front_height_m": 1.2,
                }
            ],
        },
    })
    assert cfg.cfg_version == PROJECT_SCHEMA_VERSION
    assert len(cfg.attic.dormers) == 1
    assert cfg.attic.dormers[0].id == "gaube_1"
