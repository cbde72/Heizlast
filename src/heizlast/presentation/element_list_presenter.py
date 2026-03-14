from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from ..domain.models import ElementModel
from ..core.element_metrics import ElementMetricsService
from .viewmodels import build_element_rows


@dataclass
class ElementListPresenter:
    """Presenter for the right-side element list. Qt widgets only, no domain logic."""

    list_widget: QListWidget
    metrics: ElementMetricsService

    def populate(self, elements: Iterable[ElementModel]) -> None:
        self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            rows = build_element_rows(elements, metrics=self.metrics)
            for r in rows:
                it = QListWidgetItem(r.label)
                it.setData(Qt.UserRole, r.uid)
                if r.tooltip:
                    it.setToolTip(r.tooltip)
                self.list_widget.addItem(it)
        finally:
            self.list_widget.blockSignals(False)

    def selected_uid(self) -> Optional[str]:
        items = self.list_widget.selectedItems()
        if not items:
            return None
        uid = items[0].data(Qt.UserRole)
        return str(uid) if uid else None