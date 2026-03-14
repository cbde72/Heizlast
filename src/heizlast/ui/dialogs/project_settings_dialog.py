from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
    QDoubleSpinBox, QComboBox, QTabWidget, QWidget, QCheckBox
)
from ...configs.project_config import ProjectCfg


class ProjectSettingsDialog(QDialog):
    def __init__(self, parent, cfg: ProjectCfg):
        super().__init__(parent)
        self.setWindowTitle("Projektparameter – Heizlast")
        self._cfg = cfg

        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # --- Tab: Randbedingungen ---
        w1 = QWidget(); f1 = QFormLayout(w1)
        self.sp_t_out = QDoubleSpinBox(); self.sp_t_out.setRange(-50, 50); self.sp_t_out.setDecimals(1); self.sp_t_out.setValue(cfg.t_out_c)
        self.sp_t_keller = QDoubleSpinBox(); self.sp_t_keller.setRange(-50, 50); self.sp_t_keller.setDecimals(1); self.sp_t_keller.setValue(cfg.t_keller_c)
        self.sp_t_oben = QDoubleSpinBox(); self.sp_t_oben.setRange(-50, 50); self.sp_t_oben.setDecimals(1); self.sp_t_oben.setValue(cfg.t_oben_c)
        f1.addRow("Norm-Außentemp. t_out [°C]", self.sp_t_out)
        f1.addRow("Keller temp. t_keller [°C]", self.sp_t_keller)
        f1.addRow("Oben temp. t_oben [°C]", self.sp_t_oben)
        tabs.addTab(w1, "Randbedingungen")

        # --- Tab: Geometrie ---
        w2 = QWidget(); f2 = QFormLayout(w2)
        self.cb_thickness = QComboBox(); self.cb_thickness.addItems(["full", "half"]); self.cb_thickness.setCurrentText(cfg.thickness_mode)
        self.sp_shrink = QDoubleSpinBox(); self.sp_shrink.setRange(0.50, 1.00); self.sp_shrink.setDecimals(3); self.sp_shrink.setSingleStep(0.005); self.sp_shrink.setValue(cfg.area_shrink_factor)
        self.cb_area_mode = QComboBox(); self.cb_area_mode.addItems(["inner", "outer"]); self.cb_area_mode.setCurrentText(cfg.floor_area_mode)
        self.sp_tw_out = QDoubleSpinBox(); self.sp_tw_out.setRange(0.01, 2.0); self.sp_tw_out.setDecimals(3); self.sp_tw_out.setValue(cfg.wall_thickness_outer_m)
        self.sp_tw_in = QDoubleSpinBox(); self.sp_tw_in.setRange(0.01, 2.0); self.sp_tw_in.setDecimals(3); self.sp_tw_in.setValue(cfg.wall_thickness_inner_m)
        f2.addRow("Wanddicken-Modus", self.cb_thickness)
        f2.addRow("Flächen-Faktor (shrink)", self.sp_shrink)
        f2.addRow("Bezugs-/Flächenmodus", self.cb_area_mode)
        f2.addRow("Außenwanddicke [m]", self.sp_tw_out)
        f2.addRow("Innenwanddicke [m]", self.sp_tw_in)
        tabs.addTab(w2, "Geometrie")

        # --- Tab: Lüftung ---
        w3 = QWidget(); f3 = QFormLayout(w3)
        self.sp_c_air = QDoubleSpinBox(); self.sp_c_air.setRange(0.0, 5.0); self.sp_c_air.setDecimals(3); self.sp_c_air.setValue(cfg.c_air)
        f3.addRow("c_air [Wh/(m³·K)]", self.sp_c_air)
        tabs.addTab(w3, "Lüftung")

        # --- Tab: Auto-Decken U-Werte ---
        w4 = QWidget(); f4 = QFormLayout(w4)
        self.sp_u_kd = QDoubleSpinBox(); self.sp_u_kd.setRange(0.0, 5.0); self.sp_u_kd.setDecimals(3); self.sp_u_kd.setValue(cfg.u_kellerdecke_w_m2k)
        self.sp_u_eg = QDoubleSpinBox(); self.sp_u_eg.setRange(0.0, 5.0); self.sp_u_eg.setDecimals(3); self.sp_u_eg.setValue(cfg.u_eg_geschossdecke_w_m2k)
        self.sp_u_dg = QDoubleSpinBox(); self.sp_u_dg.setRange(0.0, 5.0); self.sp_u_dg.setDecimals(3); self.sp_u_dg.setValue(cfg.u_dg_geschossdecke_w_m2k)
        f4.addRow("U Kellerdecke [W/m²K]", self.sp_u_kd)
        f4.addRow("U EG-Geschossdecke [W/m²K]", self.sp_u_eg)
        f4.addRow("U DG-Geschossdecke [W/m²K]", self.sp_u_dg)
        tabs.addTab(w4, "Auto-Decken")

        # --- Tab: Wärmebrücken ---
        w5 = QWidget(); f5 = QFormLayout(w5)
        self.cb_tb_mode = QComboBox(); self.cb_tb_mode.addItems(["none","delta_u","psi","percent"]); self.cb_tb_mode.setCurrentText(cfg.tb.mode)
        self.sp_tb_du = QDoubleSpinBox(); self.sp_tb_du.setRange(0.0, 1.0); self.sp_tb_du.setDecimals(3); self.sp_tb_du.setValue(cfg.tb.delta_u_w_m2k)
        self.sp_tb_psi = QDoubleSpinBox(); self.sp_tb_psi.setRange(0.0, 5.0); self.sp_tb_psi.setDecimals(3); self.sp_tb_psi.setValue(cfg.tb.psi_default_w_mk)
        self.sp_tb_p = QDoubleSpinBox(); self.sp_tb_p.setRange(0.0, 2.0); self.sp_tb_p.setDecimals(3); self.sp_tb_p.setValue(cfg.tb.percent_of_trans)
        self.cb_tb_meta = QCheckBox("ψ aus Element-meta nutzen (psi_w_mk / psi_L_m)"); self.cb_tb_meta.setChecked(bool(cfg.tb.use_element_meta_psi))
        self.cb_tb_out = QCheckBox("WB für Außen"); self.cb_tb_out.setChecked(bool(cfg.tb.include_out))
        self.cb_tb_k = QCheckBox("WB für Keller"); self.cb_tb_k.setChecked(bool(cfg.tb.include_keller))
        self.cb_tb_o = QCheckBox("WB für Oben"); self.cb_tb_o.setChecked(bool(cfg.tb.include_oben))

        f5.addRow("Modus", self.cb_tb_mode)
        f5.addRow("ΔU [W/m²K] (delta_u)", self.sp_tb_du)
        f5.addRow("ψ default [W/mK] (psi)", self.sp_tb_psi)
        f5.addRow("p (percent)", self.sp_tb_p)
        f5.addRow(self.cb_tb_meta)
        f5.addRow(self.cb_tb_out)
        f5.addRow(self.cb_tb_k)
        f5.addRow(self.cb_tb_o)
        tabs.addTab(w5, "Wärmebrücken")

        # --- Tab: Erdreich ---
        w6 = QWidget(); f6 = QFormLayout(w6)
        self.cb_ground_mode = QComboBox(); self.cb_ground_mode.addItems(["none", "simplified", "perimeter"]); self.cb_ground_mode.setCurrentText(getattr(cfg.ground, "mode", "simplified"))
        self.sp_ground_temp = QDoubleSpinBox(); self.sp_ground_temp.setRange(-20.0, 30.0); self.sp_ground_temp.setDecimals(2); self.sp_ground_temp.setValue(float(getattr(cfg.ground, "ground_temp_c", 10.0)))
        self.sp_ground_f_slab = QDoubleSpinBox(); self.sp_ground_f_slab.setRange(0.0, 1.0); self.sp_ground_f_slab.setDecimals(3); self.sp_ground_f_slab.setSingleStep(0.05); self.sp_ground_f_slab.setValue(float(getattr(cfg.ground, "f_slab", 0.40)))
        self.sp_ground_f_wall = QDoubleSpinBox(); self.sp_ground_f_wall.setRange(0.0, 1.0); self.sp_ground_f_wall.setDecimals(3); self.sp_ground_f_wall.setSingleStep(0.05); self.sp_ground_f_wall.setValue(float(getattr(cfg.ground, "f_wall", 0.60)))
        self.sp_ground_psi = QDoubleSpinBox(); self.sp_ground_psi.setRange(0.0, 5.0); self.sp_ground_psi.setDecimals(3); self.sp_ground_psi.setSingleStep(0.01); self.sp_ground_psi.setValue(float(getattr(cfg.ground, "psi_perimeter_w_mk", 0.0)))
        f6.addRow("Modell", self.cb_ground_mode)
        f6.addRow("Feste Erdtemperatur [°C]", self.sp_ground_temp)
        f6.addRow("f_ground Bodenplatte", self.sp_ground_f_slab)
        f6.addRow("f_ground Kellerwand", self.sp_ground_f_wall)
        f6.addRow("ψ Perimeter [W/mK]", self.sp_ground_psi)
        tabs.addTab(w6, "Erdreich")

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

    def apply_to_cfg(self, cfg: ProjectCfg) -> None:
        cfg.t_out_c = float(self.sp_t_out.value())
        cfg.t_keller_c = float(self.sp_t_keller.value())
        cfg.t_oben_c = float(self.sp_t_oben.value())

        cfg.thickness_mode = self.cb_thickness.currentText()
        cfg.area_shrink_factor = float(self.sp_shrink.value())
        cfg.floor_area_mode = self.cb_area_mode.currentText()

        cfg.wall_thickness_outer_m = float(self.sp_tw_out.value())
        cfg.wall_thickness_inner_m = float(self.sp_tw_in.value())

        cfg.c_air = float(self.sp_c_air.value())

        cfg.u_kellerdecke_w_m2k = float(self.sp_u_kd.value())
        cfg.u_eg_geschossdecke_w_m2k = float(self.sp_u_eg.value())
        cfg.u_dg_geschossdecke_w_m2k = float(self.sp_u_dg.value())

        cfg.tb.mode = self.cb_tb_mode.currentText()
        cfg.tb.delta_u_w_m2k = float(self.sp_tb_du.value())
        cfg.tb.psi_default_w_mk = float(self.sp_tb_psi.value())
        cfg.tb.percent_of_trans = float(self.sp_tb_p.value())
        cfg.tb.use_element_meta_psi = bool(self.cb_tb_meta.isChecked())
        cfg.tb.include_out = bool(self.cb_tb_out.isChecked())
        cfg.tb.include_keller = bool(self.cb_tb_k.isChecked())
        cfg.tb.include_oben = bool(self.cb_tb_o.isChecked())

        cfg.ground.mode = self.cb_ground_mode.currentText()
        cfg.ground.ground_temp_c = float(self.sp_ground_temp.value())
        cfg.ground.f_slab = float(self.sp_ground_f_slab.value())
        cfg.ground.f_wall = float(self.sp_ground_f_wall.value())
        cfg.ground.psi_perimeter_w_mk = float(self.sp_ground_psi.value())