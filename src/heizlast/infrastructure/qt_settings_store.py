from __future__ import annotations

from PySide6.QtCore import QSettings


class QtSettingsStore:
    def __init__(self, org: str = "Heizlast", app: str = "HouseTool") -> None:
        self._s = QSettings(org, app)

    def get_bool(self, key: str, default: bool = False) -> bool:
        try:
            return bool(self._s.value(key, default, type=bool))
        except Exception:
            return bool(default)

    def set_bool(self, key: str, value: bool) -> None:
        try:
            self._s.setValue(key, bool(value))
        except Exception:
            pass