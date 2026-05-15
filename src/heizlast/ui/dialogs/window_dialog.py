from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QDoubleSpinBox, QVBoxLayout
)

class WindowDialog(QDialog):
    """Dialog for entering window parameters.

    Returns values via getters after accept().
    """

    def __init__(
        self,
        parent=None,
        *,
        length_m: float = 1.20,
        height_m: float = 1.30,
        u_w_m2k: float = 2.8,
        factor: float = 1.0,
        center_x_m: float = 0.0,
        center_y_m: float = 0.0,
        orient: str = "H",
    ):
        super().__init__(parent)
        self.setWindowTitle("Fenster anlegen")
        self.setModal(True)

        root = QVBoxLayout(self)

        info = QLabel(f"Orientierung: {'horizontal' if orient=='H' else 'vertikal'} (automatisch von der Wand)")
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        self.sp_len = QDoubleSpinBox(); self.sp_len.setRange(0.20, 10.0); self.sp_len.setDecimals(2); self.sp_len.setSingleStep(0.05); self.sp_len.setValue(length_m)
        self.sp_h   = QDoubleSpinBox(); self.sp_h.setRange(0.20, 5.0);  self.sp_h.setDecimals(2);   self.sp_h.setSingleStep(0.05);   self.sp_h.setValue(height_m)
        self.sp_u   = QDoubleSpinBox(); self.sp_u.setRange(0.0, 10.0);  self.sp_u.setDecimals(3);   self.sp_u.setSingleStep(0.10);   self.sp_u.setValue(u_w_m2k)
        self.sp_f   = QDoubleSpinBox(); self.sp_f.setRange(0.0, 5.0);   self.sp_f.setDecimals(3);   self.sp_f.setSingleStep(0.05);   self.sp_f.setValue(factor)

        self.sp_cx  = QDoubleSpinBox(); self.sp_cx.setRange(-1000, 1000); self.sp_cx.setDecimals(2); self.sp_cx.setSingleStep(0.05); self.sp_cx.setValue(center_x_m)
        self.sp_cy  = QDoubleSpinBox(); self.sp_cy.setRange(-1000, 1000); self.sp_cy.setDecimals(2); self.sp_cy.setSingleStep(0.05); self.sp_cy.setValue(center_y_m)

        form.addRow("Breite / Länge [m]:", self.sp_len)
        form.addRow("Höhe [m]:", self.sp_h)
        form.addRow("U-Wert [W/(m²K)]:", self.sp_u)
        form.addRow("Faktor [-]:", self.sp_f)
        form.addRow("Position Zentrum X [m]:", self.sp_cx)
        form.addRow("Position Zentrum Y [m]:", self.sp_cy)

        root.addLayout(form)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def values(self) -> dict:
        return {
            "length_m": float(self.sp_len.value()),
            "height_m": float(self.sp_h.value()),
            "u_w_m2k": float(self.sp_u.value()),
            "factor": float(self.sp_f.value()),
            "center_x_m": float(self.sp_cx.value()),
            "center_y_m": float(self.sp_cy.value()),
        }